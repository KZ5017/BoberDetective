from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.analysis_modules import AnalysisModuleResearchFinding, AnalysisModuleRunRequest, AnalysisModuleRunResponse
from app.schemas.source_reference import SourceReferenceCreate
from app.services.analysis_module_common import (
    AnalysisModuleError,
    RetrievedChunk,
    add_retrieved_chunk_inputs,
    build_source_blocks,
    chunk_batch_lookup,
    parse_llm_json_object,
    select_source_chunks,
    split_retrieved_chunks,
)
from app.services.analysis_runs import add_analysis_run_input, add_analysis_run_output, finish_analysis_run, start_analysis_run
from app.services.llm import LLMChatMessage, LMStudioNativeProvider
from app.services.research_findings import create_research_finding
from app.services.source_references import create_source_reference_for_run


SUPPORTED_FINDING_TYPES = {"claim", "event", "entity", "document_reference", "other"}
SEARCH_FINDINGS_MAX_OUTPUT_TOKENS = 6000

SEARCH_FINDINGS_SYSTEM_PROMPT = """You are a source-faithful research finding extraction component.
You are analyzing Hungarian source text.
You may only use the provided SOURCE texts.
You must not use external knowledge and must not fill in missing facts.
Stay factual: do not assume, do not infer, and do not add any interpretation that is not directly supported by the source.
Do not decide guilt, legal classification, risk, or personal responsibility.
Return all user-facing textual fields in Hungarian.
Return quote_text exactly as copied from the Hungarian SOURCE text: do not translate it and do not rewrite it.
Respond only with a valid JSON object.
Expected JSON shape:
{"findings":[{"title":"...","finding_text":"...","suggested_type":"other","suggested_type_reason":"...","relevance_reason":"...","quote_text":"...","source_label":"chunk_1"}],"unsupported_findings":[{"title":"...","finding_text":"...","suggested_type":"other","suggested_type_reason":"...","relevance_reason":"...","quote_text":"...","source_label":"chunk_1","unsupported_reason":"..."}]}
"""


def run_search_findings(db: Session, case_id: UUID, payload: AnalysisModuleRunRequest) -> AnalysisModuleRunResponse:
    settings = get_settings()
    input_parameters = {
        "query": payload.query,
        "source_mode": payload.source_mode,
        "document_id": str(payload.document_id) if payload.document_id is not None else None,
        "document_ids": [str(document_id) for document_id in payload.document_ids],
        "document_group_code": payload.document_group_code,
        "document_type_code": payload.document_type_code,
        "page_start": payload.page_start,
        "page_end": payload.page_end,
        "max_chunks": payload.max_chunks,
        "batch_size": payload.batch_size,
        "retrieval_strategy": payload.retrieval_strategy,
    }
    run = start_analysis_run(
        db,
        case_id,
        "search_findings",
        provider_type="lm_studio_native",
        model_name=settings.llm_chat_model,
        input_parameters=input_parameters,
        prompt_template_name="search_findings_v1",
        prompt_template_version="1",
        output_schema_name="search_findings",
        output_schema_version="1",
        retrieval_strategy=f"{payload.source_mode}_chunks_batch_v1",
    )
    try:
        add_analysis_run_input(db, run.id, "query_text", 0, payload_json={"query": payload.query})
        retrieved_chunks = select_source_chunks(db, case_id, payload)
        if not retrieved_chunks:
            message = "No source chunks selected for finding search"
            finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=message)
            raise AnalysisModuleError(message)

        batches = split_retrieved_chunks(retrieved_chunks, payload.batch_size)
        add_retrieved_chunk_inputs(db, run.id, retrieved_chunks, chunk_batch_lookup(batches))
        response_findings: list[AnalysisModuleResearchFinding] = []
        unsupported_items: list[str] = []
        failed_batch_count = 0
        processed_batch_count = 0

        for batch_index, batch in enumerate(batches, start=1):
            try:
                provider = LMStudioNativeProvider(settings)
                completion = provider.chat_completion(
                    settings.llm_chat_model,
                    [
                        LLMChatMessage(role="system", content=SEARCH_FINDINGS_SYSTEM_PROMPT),
                        LLMChatMessage(
                            role="user",
                            content=build_search_findings_user_prompt(payload.query, batch, batch_index, len(batches)),
                        ),
                    ],
                    temperature=0.1,
                    max_tokens=SEARCH_FINDINGS_MAX_OUTPUT_TOKENS,
                )
                parsed = parse_llm_json_object(completion.content)
                valid_findings, batch_unsupported = validate_extracted_findings(parsed, batch)
                unsupported_items.extend(batch_unsupported)
                processed_batch_count += 1
            except Exception as exc:
                failed_batch_count += 1
                unsupported_items.append(f"batch_{batch_index}: {exc}")
                continue

            for finding in valid_findings:
                output_position = len(response_findings)
                source_reference = create_source_reference_for_run(
                    db,
                    case_id,
                    SourceReferenceCreate(
                        document_id=finding["chunk"].document_id,
                        chunk_id=finding["chunk"].id,
                        quote_text=finding["quote_text"],
                        source_kind="chunk_quote",
                        citation_label=f"{finding['document_name']}, chunk {finding['chunk'].chunk_index}",
                    ),
                    extraction_run_id=run.id,
                )
                add_analysis_run_output(db, run.id, "source_reference", source_reference.id, output_position)
                persisted_finding = create_research_finding(
                    db,
                    case_id=case_id,
                    title=finding["title"],
                    finding_text=finding["finding_text"],
                    suggested_type=finding["suggested_type"],
                    suggested_type_reason=finding["suggested_type_reason"],
                    relevance_reason=finding["relevance_reason"],
                    source_reference_id=source_reference.id,
                    analysis_run_id=run.id,
                    llm_support_status=finding["llm_support_status"],
                )
                add_analysis_run_output(db, run.id, "research_finding", persisted_finding.id, output_position)
                response_findings.append(
                    AnalysisModuleResearchFinding(
                        research_finding_id=persisted_finding.id,
                        title=persisted_finding.title,
                        finding_text=persisted_finding.finding_text,
                        suggested_type=persisted_finding.suggested_type,
                        suggested_type_reason=persisted_finding.suggested_type_reason,
                        relevance_reason=persisted_finding.relevance_reason,
                        llm_support_status=persisted_finding.llm_support_status,
                        quote_text=finding["quote_text"],
                        source_label=finding["source_label"],
                        source_reference_id=source_reference.id,
                        document_id=finding["chunk"].document_id,
                        chunk_id=finding["chunk"].id,
                    )
                )

        if failed_batch_count == len(batches):
            message = "Az osszes talalatkeresesi batch sikertelen volt"
            if unsupported_items:
                message = f"{message}: {unsupported_items[0]}"
            finish_analysis_run(
                db,
                run,
                status="failed",
                validation_status="failed",
                error_message=message,
                output_summary={
                    "batch_count": len(batches),
                    "processed_batch_count": processed_batch_count,
                    "failed_batch_count": failed_batch_count,
                    "unsupported_items": unsupported_items[:5],
                },
            )
            raise AnalysisModuleError(message)

        validation_status = "passed"
        if failed_batch_count > 0 or unsupported_items or not response_findings:
            validation_status = "warning"
        finish_analysis_run(
            db,
            run,
            status="succeeded",
            validation_status=validation_status,
            output_summary={
                "batch_count": len(batches),
                "processed_batch_count": processed_batch_count,
                "failed_batch_count": failed_batch_count,
                "created_research_finding_count": len(response_findings),
                "unsupported_count": len(unsupported_items),
            },
        )
        return AnalysisModuleRunResponse(
            analysis_run_id=run.id,
            module_key="search_findings",
            model=settings.llm_chat_model,
            research_findings=response_findings,
            unsupported_items=unsupported_items,
            selected_chunk_ids=[retrieved.chunk.id for retrieved in retrieved_chunks],
            validation_status=validation_status,
        )
    except Exception as exc:
        if run.status == "running":
            finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=str(exc))
        if isinstance(exc, AnalysisModuleError):
            raise
        raise AnalysisModuleError(str(exc)) from exc


def build_search_findings_user_prompt(
    query: str | None,
    retrieved_chunks: list[RetrievedChunk],
    batch_index: int = 1,
    batch_count: int = 1,
) -> str:
    focus_text = query.strip() if isinstance(query, str) and query.strip() else "Nincs külön fókusz."
    return (
        f"QUERY:\n{focus_text}\n\n"
        f"BATCH:\n{batch_index}/{batch_count}\n\n"
        f"SOURCE:\n{build_source_blocks(retrieved_chunks)}\n\n"
        "TASK:\n"
        "Find research findings that are relevant to the QUERY and supported by source text. "
        "The SOURCE texts are Hungarian. Return title, finding_text, suggested_type_reason, relevance_reason, and unsupported_reason in Hungarian. "
        "Evaluate every possible finding separately from the perspective of the QUERY. "
        "Return only a finding that is independently and directly related to the focus given in the QUERY. "
        "If the connection is only loose, indirect, contextual, or requires explanation, do not return it as a finding; put it into unsupported_findings. "
        "If there are multiple separate, directly sourced findings, return them as separate items. "
        "Do not stop at a single finding if the batch contains multiple relevant source locations. "
        "The title must be short, factual, and source-faithful: it may name only the relationship or fact directly supported by quote_text. "
        "The finding_text must not assume, infer, or say more than what quote_text directly supports. "
        "If the source only supports a relationship, reaction, presence, knowledge, or statement, then the title and finding_text must record only that. "
        "Do not call anyone a perpetrator, killer, guilty person, or responsible person unless quote_text states this literally and directly. "
        "Do not classify a speaker as a witness, deponent, expert, victim, or other procedural role unless quote_text directly supports this. "
        "If the QUERY concerns witnesses, statements, or procedural roles, do not return mere dialogue, narrator comments, or background scenes as findings only because they are loosely related to the topic. "
        "The relevance_reason must not mention general context; it must specifically explain which part of quote_text is directly related to the QUERY focus. "
        "The fact that a SOURCE chunk was included in the batch is not enough reason to extract a finding. "
        "If the SOURCE chunk does not contain direct information about the QUERY focus, do not create a finding that only states the absence of information. "
        "Do not return as a finding the fact that the source contains no information about the searched person, object, or topic. "
        "If the QUERY contains a specific person name, return a finding about that person only if quote_text directly contains that name, or if quote_text itself clearly identifies the same person. "
        "Do not identify another person in the source as the person named in the QUERY. "
        "If quote_text does not contain or directly identify the person named in the QUERY, do not create a finding about that person. "
        "If it is clear that a finding is a claim, event, or entity, set suggested_type to claim, event, or entity accordingly, but do not force this classification; if the finding type is unclear, set suggested_type to other. "
        "Every findings item must have source_label and quote_text. "
        "Copy quote_text character-exactly from the corresponding SOURCE chunk: do not translate, fix, add accents, or normalize it. "
        "The quote_text must not be too narrow: by itself, it must make it possible to verify who or what finding_text is about and what the core finding is. "
        "If the subject, object, or reason of the finding is clear only from the previous or next sentence, quote_text must include those necessary sentences together. "
        "Do not copy a full chunk or an unnecessarily long passage into quote_text; provide a focused, coherent quote, usually 1-4 sentences."
    )


def validate_extracted_findings(
    payload: dict[str, Any],
    retrieved_chunks: list[RetrievedChunk],
) -> tuple[list[dict[str, Any]], list[str]]:
    findings_value = payload.get("findings", [])
    unsupported_value = payload.get("unsupported_findings", [])
    if not isinstance(findings_value, list) or not isinstance(unsupported_value, list):
        raise AnalysisModuleError("LLM JSON has invalid findings or unsupported_findings fields")

    chunks_by_label = {retrieved.label: retrieved for retrieved in retrieved_chunks}
    valid_findings: list[dict[str, Any]] = []
    unsupported_items: list[str] = []
    for item in findings_value:
        finding = _validated_finding_item(item, chunks_by_label, llm_support_status="confirmed")
        if finding is None:
            source_label = item.get("source_label") if isinstance(item, dict) else None
            unsupported_items.append(f"Skipped finding with invalid source_label or quote_text from {source_label}")
            continue
        valid_findings.append(finding)

    for item in unsupported_value:
        if isinstance(item, str):
            unsupported_items.append(item)
            continue
        finding = _validated_finding_item(item, chunks_by_label, llm_support_status="unconfirmed")
        if finding is None:
            source_label = item.get("source_label") if isinstance(item, dict) else None
            unsupported_items.append(f"Skipped unsupported finding with invalid source_label or quote_text from {source_label}")
            continue
        valid_findings.append(finding)
    return valid_findings, unsupported_items


def _validated_finding_item(
    item: Any,
    chunks_by_label: dict[str, RetrievedChunk],
    *,
    llm_support_status: str,
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    title = item.get("title")
    finding_text = item.get("finding_text")
    suggested_type = item.get("suggested_type", "other")
    suggested_type_reason = item.get("suggested_type_reason")
    relevance_reason = item.get("relevance_reason")
    quote_text = item.get("quote_text")
    source_label = item.get("source_label")
    if suggested_type not in SUPPORTED_FINDING_TYPES:
        suggested_type = "other"
    if not all(isinstance(value, str) for value in [title, finding_text, relevance_reason, quote_text, source_label]):
        return None
    if title.strip() == "" or finding_text.strip() == "" or relevance_reason.strip() == "" or quote_text.strip() == "":
        return None
    retrieved = chunks_by_label.get(source_label)
    if retrieved is None:
        return None
    resolved_quote = _resolve_quote_text(retrieved.chunk.chunk_text, quote_text)
    if resolved_quote is None:
        return None
    return {
        "title": title,
        "finding_text": finding_text,
        "suggested_type": suggested_type,
        "suggested_type_reason": suggested_type_reason if isinstance(suggested_type_reason, str) and suggested_type_reason.strip() else None,
        "relevance_reason": relevance_reason,
        "quote_text": resolved_quote,
        "source_label": source_label,
        "chunk": retrieved.chunk,
        "document_name": retrieved.document_name,
        "llm_support_status": llm_support_status,
    }


def _resolve_quote_text(source_text: str, quote_text: str) -> str | None:
    if quote_text in source_text:
        return quote_text
    normalized_quote = " ".join(quote_text.split())
    if normalized_quote == "":
        return None
    if normalized_quote in source_text:
        return normalized_quote
    return None
