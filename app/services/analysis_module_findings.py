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

SEARCH_FINDINGS_SYSTEM_PROMPT = """Te egy forráshű kutatási találatkereső komponens vagy.
Csak a megadott SOURCE chunkokból dolgozhatsz.
Nem használhatsz külső tudást és nem egészítheted ki a hiányzó tényeket.
Nem dönthetsz bűnösségről, jogi minősítésről, kockázatról vagy személyi felelősségről.
Nem kell minden találatot állításnak, eseménynek vagy entitásnak minősítened.
Ha a találat nem sorolható biztosan egy konkrét típusba, használd az other suggested_type értéket.
Válaszolj kizárólag érvényes JSON objektummal.
Minden findings elemhez kötelező a source_label és quote_text.
quote_text mezőt karakterpontosan másold ki a megfelelő SOURCE chunkból: ne fordítsd, ne javítsd, ne ékezetesítsd, ne normalizáld.
quote_text legyen pontos, összefüggő idézet, amely önmagában is ellenőrizhetővé teszi a találat lényegét.
Ha nincs elég forrás egy találathoz, ne tedd findings közé; tedd az unsupported_findings listába.
Elvárt JSON alak:
{"findings":[{"title":"...","finding_text":"...","suggested_type":"other","suggested_type_reason":"...","relevance_reason":"...","quote_text":"...","source_label":"chunk_1"}],"unsupported_findings":["..."]}
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
        duplicate_skipped_count = 0
        dedup_keys: set[tuple[str, str, str]] = set()

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
                    max_tokens=1800,
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
                dedup_key = (
                    _normalize_for_dedup(finding["title"]),
                    _normalize_for_dedup(finding["finding_text"]),
                    _normalize_for_dedup(finding["quote_text"]),
                )
                if dedup_key in dedup_keys:
                    duplicate_skipped_count += 1
                    continue
                dedup_keys.add(dedup_key)

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
                "duplicate_skipped_count": duplicate_skipped_count,
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
        "FELADAT:\n"
        "Keresd meg a QUERY szempontjából releváns, forrással alátámasztott kutatási találatokat. "
        "Minden lehetséges találatot külön-külön vizsgálj meg a QUERY szempontjából. "
        "Csak olyan találatot adj vissza, amely önmagában és közvetlenül kapcsolódik a QUERY-ben megadott fókuszhoz. "
        "Önmagában az, hogy egy SOURCE chunk bekerült a batchbe, nem elég ok találat kinyerésére. "
        "Ne erőltesd, hogy a találat állítás, esemény vagy entitás legyen. "
        "Ha a találat típusa nem egyértelmű, suggested_type értéke legyen other. "
        "A suggested_type csak javaslat, nem döntés. "
        "A relevance_reason röviden magyarázza meg, hogy a találat miért kapcsolódik közvetlenül a QUERY fókuszához. "
        "A quote_text ne legyen túl szűk: önmagában is tegye ellenőrizhetővé, hogy a finding_text kire vagy mire vonatkozik, és mi a találat lényege. "
        "Ha a találat alanya, tárgya vagy oka csak az előző vagy következő mondatból derül ki, akkor a quote_text tartalmazza együtt ezeket a szükséges mondatokat is."
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
    for item in findings_value:
        if not isinstance(item, dict):
            continue
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
            continue
        if title.strip() == "" or finding_text.strip() == "" or relevance_reason.strip() == "" or quote_text.strip() == "":
            continue
        retrieved = chunks_by_label.get(source_label)
        if retrieved is None or quote_text not in retrieved.chunk.chunk_text:
            continue
        valid_findings.append(
            {
                "title": title,
                "finding_text": finding_text,
                "suggested_type": suggested_type,
                "suggested_type_reason": suggested_type_reason if isinstance(suggested_type_reason, str) and suggested_type_reason.strip() else None,
                "relevance_reason": relevance_reason,
                "quote_text": quote_text,
                "source_label": source_label,
                "chunk": retrieved.chunk,
                "document_name": retrieved.document_name,
            }
        )

    unsupported_items = [item for item in unsupported_value if isinstance(item, str)]
    return valid_findings, unsupported_items


def _normalize_for_dedup(value: str) -> str:
    return " ".join(value.casefold().split())
