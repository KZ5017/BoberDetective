from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.analysis_modules import AnalysisModuleRunRequest, AnalysisModuleRunResponse, AnalysisModuleSummaryItem
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
from app.services.analysis_deduplication import find_duplicate_summary_item
from app.services.analysis_runs import add_analysis_run_input, add_analysis_run_output, finish_analysis_run, start_analysis_run
from app.services.llm import LLMChatMessage, LMStudioNativeProvider
from app.services.source_references import create_source_reference_for_run
from app.services.summary_items import create_summary_item_with_source


SUPPORTED_SUMMARY_TYPES = {
    "case_overview",
    "document_summary",
    "timeline_summary",
    "entity_summary",
    "caution_note",
    "other",
}

EXTRACT_SUMMARY_ITEMS_SYSTEM_PROMPT = """Te egy forrashu ugyosszefoglalo komponens vagy.
Csak a megadott SOURCE chunkokbol dolgozhatsz.
Nem hasznalhatsz kulso tudast es nem egeszitheted ki a hianyzo tenyeket.
Nem donthetsz bunossegrol, jogi minositesrol, kockazatrol vagy szemelyi felelossegrol.
Nem keszithetsz kockazati pontszamot es nem jelolhetsz meg gyanusitottat.
Nem vonhatsz le olyan kovetkeztetest, amely nincs kozvetlenul a quote_text idezetben.
Rovid, kulon review-zhato summary_items elemeket adj vissza, nem egyetlen szabad szovegu osszefoglalot.
Valaszolj kizarolag ervenyes JSON objektummal.
A JSON stringekben minden belso dupla idezojelet kotelezo backslash karakterrel escape-elni.
Minden summary_items elemhez kotelezo a source_label es quote_text.
quote_text mezot karakterpontosan masold ki a megfelelo SOURCE chunkbol: ne fordisd, ne javitsd, ne ekezetesitsd, ne normalizald.
quote_text legyen rovid, legfeljebb 300 karakteres, pontos, osszefuggo idezet; ne masolj teljes bekezdeseket.
Ha a valasztott idezet dupla idezojelet tartalmazna, inkabb valassz rovidebb, dupla idezojel nelkuli pontos idezetet ugyanabbol a forrasbol.
summary_type csak ezek egyike lehet: case_overview, document_summary, timeline_summary, entity_summary, caution_note, other.
support_type csak ezek egyike lehet: direct, indirect, contextual.
Ha nincs eleg forras egy osszefoglalo elemhez, ne tedd summary_items koze; tedd az unsupported_summary_items listaba.
Elvart JSON alak:
{"summary_items":[{"summary_type":"case_overview","title":"...","body_text":"...","quote_text":"...","source_label":"chunk_1","support_type":"direct"}],"unsupported_summary_items":["..."]}
"""


def run_summarize_case(db: Session, case_id: UUID, payload: AnalysisModuleRunRequest) -> AnalysisModuleRunResponse:
    settings = get_settings()
    input_parameters = {
        "query": payload.query,
        "limit": payload.limit,
        "source_mode": payload.source_mode,
        "document_id": str(payload.document_id) if payload.document_id is not None else None,
        "max_chunks": payload.max_chunks,
        "batch_size": payload.batch_size,
    }
    run = start_analysis_run(
        db,
        case_id,
        "summarize_case",
        provider_type="lm_studio_native",
        model_name=settings.llm_chat_model,
        input_parameters=input_parameters,
        prompt_template_name="summarize_case_v1",
        prompt_template_version="1",
        output_schema_name="summarize_case",
        output_schema_version="1",
        retrieval_strategy=f"{payload.source_mode}_chunks_batch_v1",
    )
    try:
        add_analysis_run_input(db, run.id, "query_text", 0, payload_json={"query": payload.query})
        retrieved_chunks = select_source_chunks(db, case_id, payload)
        if not retrieved_chunks:
            message = "No source chunks selected for analysis"
            finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=message)
            raise AnalysisModuleError(message)

        batches = split_retrieved_chunks(retrieved_chunks, payload.batch_size)
        add_retrieved_chunk_inputs(db, run.id, retrieved_chunks, chunk_batch_lookup(batches))
        response_items: list[AnalysisModuleSummaryItem] = []
        unsupported_items: list[str] = []
        duplicate_skipped_count = 0
        historical_duplicate_skipped_count = 0
        failed_batch_count = 0
        processed_batch_count = 0
        dedup_keys: set[tuple[UUID, str, str, str]] = set()

        for batch_index, batch in enumerate(batches, start=1):
            try:
                completion = LMStudioNativeProvider(settings).chat_completion(
                    settings.llm_chat_model,
                    [
                        LLMChatMessage(role="system", content=EXTRACT_SUMMARY_ITEMS_SYSTEM_PROMPT),
                        LLMChatMessage(
                            role="user",
                            content=build_summarize_case_user_prompt(payload.query, batch, batch_index, len(batches)),
                        ),
                    ],
                    temperature=0.1,
                    max_tokens=1600,
                )
                parsed = parse_llm_json_object(completion.content)
                valid_items, batch_unsupported = validate_extracted_summary_items(parsed, batch)
                unsupported_items.extend(batch_unsupported)
                processed_batch_count += 1
            except Exception as exc:
                failed_batch_count += 1
                unsupported_items.append(f"batch_{batch_index}: {exc}")
                continue

            for item in valid_items:
                dedup_key = _summary_item_dedup_key(item)
                if dedup_key in dedup_keys:
                    duplicate_skipped_count += 1
                    continue
                dedup_keys.add(dedup_key)
                existing_summary_item = find_duplicate_summary_item(
                    db,
                    case_id=case_id,
                    summary_type=item["summary_type"],
                    title=item["title"],
                    body_text=item["body_text"],
                    document_id=item["chunk"].document_id,
                    chunk_id=item["chunk"].id,
                    quote_text=item["quote_text"],
                )
                if existing_summary_item is not None:
                    historical_duplicate_skipped_count += 1
                    continue
                output_position = len(response_items)
                source_reference = create_source_reference_for_run(
                    db,
                    case_id,
                    SourceReferenceCreate(
                        document_id=item["chunk"].document_id,
                        chunk_id=item["chunk"].id,
                        quote_text=item["quote_text"],
                        source_kind="chunk_quote",
                        citation_label=f"{item['document_name']}, chunk {item['chunk'].chunk_index}",
                    ),
                    extraction_run_id=run.id,
                )
                add_analysis_run_output(db, run.id, "source_reference", source_reference.id, output_position)
                summary_item = create_summary_item_with_source(
                    db,
                    case_id=case_id,
                    summary_type=item["summary_type"],
                    title=item["title"],
                    body_text=item["body_text"],
                    source_reference_id=source_reference.id,
                    analysis_run_id=run.id,
                    confidence=item["confidence"],
                    support_type=item["support_type"],
                    relevance_rank=output_position,
                )
                add_analysis_run_output(db, run.id, "summary_item", summary_item.id, output_position)
                response_items.append(
                    AnalysisModuleSummaryItem(
                        summary_item_id=summary_item.id,
                        summary_type=summary_item.summary_type,
                        title=summary_item.title,
                        body_text=summary_item.body_text,
                        quote_text=item["quote_text"],
                        source_label=item["source_label"],
                        source_reference_id=source_reference.id,
                        document_id=item["chunk"].document_id,
                        chunk_id=item["chunk"].id,
                    )
                )

        if failed_batch_count == len(batches):
            detail = "; ".join(unsupported_items[:3])
            message = f"All summary extraction batches failed: {detail}" if detail else "All summary extraction batches failed"
            finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=message)
            raise AnalysisModuleError(message)

        validation_status = "passed"
        if failed_batch_count > 0 or unsupported_items or not response_items:
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
                "created_summary_item_count": len(response_items),
                "duplicate_skipped_count": duplicate_skipped_count,
                "historical_duplicate_skipped_count": historical_duplicate_skipped_count,
                "unsupported_count": len(unsupported_items),
            },
        )
        return AnalysisModuleRunResponse(
            analysis_run_id=run.id,
            module_key="summarize_case",
            model=settings.llm_chat_model,
            claims=[],
            events=[],
            entities=[],
            summary_items=response_items,
            contradiction_candidates=[],
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


def _summary_item_dedup_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _normalize_for_dedup(item["summary_type"]),
        _normalize_for_dedup(item["title"]),
        _normalize_for_dedup(item["body_text"]),
    )


def _normalize_for_dedup(value: str) -> str:
    return " ".join(value.casefold().split())


def build_summarize_case_user_prompt(
    query: str | None,
    retrieved_chunks: list[RetrievedChunk],
    batch_index: int = 1,
    batch_count: int = 1,
) -> str:
    focus_text = query.strip() if isinstance(query, str) and query.strip() else "Nincs kulon fokusz; a megadott forraschunkok review-zhato osszefoglalo elemeit kell kinyerni."
    return (
        f"QUERY:\n{focus_text}\n\n"
        f"BATCH:\n{batch_index}/{batch_count}\n\n"
        f"SOURCE:\n{build_source_blocks(retrieved_chunks)}\n\n"
        "FELADAT:\n"
        "Keszits rovid, forrassal alatamasztott osszefoglalo elemeket a QUERY szempontjabol. "
        "Ha nincs kulon fokusz, a batch forraschunkjaiban szereplo lenyeges, ellenorizheto osszefoglalo elemeket nyerd ki. "
        "Legfeljebb 3 summary_items elemet adj vissza ebbol a batchbol. "
        "Minden elem legyen kulon review-zhato, ne keszits teljes ugyosszefoglalot. "
        "A title es body_text csak azt foglalja ossze, amit a quote_text kozvetlenul alatamaszt. "
        "Ne irj magyarazatot, kovetkeztetest vagy jelentestulajdonitast, ha az nincs benne az idezetben. "
        "Az idezetek legyenek rovidek, pontosak, es teljes egeszukben szerepeljenek a megadott SOURCE chunkban. "
        "Keruld a dupla idezojelet tartalmazo idezeteket; ha megis kell ilyen karakter, ervenyes JSON modon escape-eld."
    )


def validate_extracted_summary_items(
    payload: dict[str, Any],
    retrieved_chunks: list[RetrievedChunk],
) -> tuple[list[dict[str, Any]], list[str]]:
    items_value = payload.get("summary_items", [])
    unsupported_value = payload.get("unsupported_summary_items", [])
    if not isinstance(items_value, list) or not isinstance(unsupported_value, list):
        raise AnalysisModuleError("LLM JSON has invalid summary_items or unsupported_summary_items fields")

    chunks_by_label = {retrieved.label: retrieved for retrieved in retrieved_chunks}
    valid_items: list[dict[str, Any]] = []
    for item in items_value:
        if not isinstance(item, dict):
            continue
        summary_type = item.get("summary_type", "other")
        title = item.get("title")
        body_text = item.get("body_text")
        quote_text = item.get("quote_text")
        source_label = item.get("source_label")
        support_type = item.get("support_type", "direct")
        confidence = _normalized_confidence(item.get("confidence"))
        if summary_type not in SUPPORTED_SUMMARY_TYPES:
            summary_type = "other"
        if support_type not in {"direct", "indirect", "contextual"}:
            support_type = "direct"
        if not isinstance(title, str) or not isinstance(body_text, str) or not isinstance(quote_text, str) or not isinstance(source_label, str):
            continue
        if title.strip() == "" or body_text.strip() == "" or quote_text.strip() == "":
            continue
        retrieved = chunks_by_label.get(source_label)
        if retrieved is None or quote_text not in retrieved.chunk.chunk_text:
            continue
        valid_items.append(
            {
                "summary_type": summary_type,
                "title": title,
                "body_text": body_text,
                "quote_text": quote_text,
                "source_label": source_label,
                "support_type": support_type,
                "confidence": confidence,
                "chunk": retrieved.chunk,
                "document_name": retrieved.document_name,
            }
        )

    unsupported_items = [item for item in unsupported_value if isinstance(item, str)]
    return valid_items[:3], unsupported_items


def _normalized_confidence(value: Any) -> Decimal | None:
    if isinstance(value, int | float):
        if 0 <= value <= 1:
            return Decimal(str(value))
        return None
    if isinstance(value, str):
        mapping = {"low": Decimal("0.3000"), "medium": Decimal("0.6000"), "high": Decimal("0.9000")}
        return mapping.get(value.strip().lower())
    return None
