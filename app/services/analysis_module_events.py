from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.analysis_modules import AnalysisModuleEvent, AnalysisModuleRunRequest, AnalysisModuleRunResponse
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
from app.services.analysis_deduplication import find_duplicate_event
from app.services.analysis_runs import add_analysis_run_input, add_analysis_run_output, finish_analysis_run, start_analysis_run
from app.services.events import create_event_with_source
from app.services.llm import LLMChatMessage, LMStudioNativeProvider
from app.services.source_references import create_source_reference_for_run


SUPPORTED_EVENT_TYPES = {
    "call",
    "meeting",
    "statement",
    "transfer",
    "search",
    "seizure",
    "document_created",
    "document_received",
    "other",
}
SUPPORTED_TIME_PRECISIONS = {"exact", "minute", "hour", "day", "month", "unknown"}
MAX_EVENT_EXTRACTION_BATCH_SIZE = 2

EXTRACT_EVENTS_SYSTEM_PROMPT = """Te egy forrashu iratelemzo komponens vagy.
Csak a megadott SOURCE chunkokbol dolgozhatsz.
Nem hasznalhatsz kulso tudast es nem egeszitheted ki a hianyzo tenyeket.
Csak esemenyjelolteket adhatsz vissza; nem allithatod, hogy az esemeny bizonyosan megtortent, ha a forras csak allitja vagy hivatkozza.
Nem donthetsz bunossegrol, jogi minositesrol, kockazatrol vagy szemelyi felelossegrol.
Valaszolj kizarolag ervenyes JSON objektummal.
A JSON stringekben minden belso dupla idezojelet kotelezo backslash karakterrel escape-elni.
Minden events elemhez kotelezo a source_label es quote_text.
quote_text mezot karakterpontosan masold ki a megfelelo SOURCE chunkbol: ne fordisd, ne javitsd, ne ekezetesitsd, ne normalizald.
quote_text legyen rovid, legfeljebb 400 karakteres, pontos, osszefuggo idezet; ne masolj teljes bekezdeseket.
Ha a valasztott idezet dupla idezojelet tartalmazna, inkabb valassz rovidebb, dupla idezojel nelkuli pontos idezetet ugyanabbol a forrasbol.
event_type csak ezek egyike lehet: call, meeting, statement, transfer, search, seizure, document_created, document_received, other.
time_precision csak ezek egyike lehet: exact, minute, hour, day, month, unknown.
Ha nincs eleg forras egy esemenyhez, ne tedd events koze; tedd az unsupported_events listaba.
Elvart JSON alak:
{"events":[{"event_type":"call","event_title":"...","event_description":"...","event_time_raw":"...","time_precision":"minute","location_text":null,"quote_text":"...","source_label":"chunk_1"}],"unsupported_events":["..."]}
"""


def run_extract_events(db: Session, case_id: UUID, payload: AnalysisModuleRunRequest) -> AnalysisModuleRunResponse:
    settings = get_settings()
    effective_batch_size = _effective_event_batch_size(payload.batch_size)
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
        "batch_size": effective_batch_size,
        "requested_batch_size": payload.batch_size,
        "module_batch_size_cap": MAX_EVENT_EXTRACTION_BATCH_SIZE,
        "retrieval_strategy": payload.retrieval_strategy,
    }
    run = start_analysis_run(
        db,
        case_id,
        "extract_events",
        provider_type="lm_studio_native",
        model_name=settings.llm_chat_model,
        input_parameters=input_parameters,
        prompt_template_name="extract_events_v1",
        prompt_template_version="1",
        output_schema_name="extract_events",
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

        batches = split_retrieved_chunks(retrieved_chunks, effective_batch_size)
        add_retrieved_chunk_inputs(db, run.id, retrieved_chunks, chunk_batch_lookup(batches))
        response_events: list[AnalysisModuleEvent] = []
        unsupported_items: list[str] = []
        duplicate_skipped_count = 0
        historical_duplicate_skipped_count = 0
        failed_batch_count = 0
        processed_batch_count = 0
        dedup_keys: set[tuple[UUID, str, str]] = set()

        for batch_index, batch in enumerate(batches, start=1):
            try:
                completion = LMStudioNativeProvider(settings).chat_completion(
                    settings.llm_chat_model,
                    [
                        LLMChatMessage(role="system", content=EXTRACT_EVENTS_SYSTEM_PROMPT),
                        LLMChatMessage(
                            role="user",
                            content=build_extract_events_user_prompt(payload.query, batch, batch_index, len(batches)),
                        ),
                    ],
                    temperature=0.1,
                    max_tokens=1600,
                )
                parsed = parse_llm_json_object(completion.content)
                valid_events, batch_unsupported = validate_extracted_events(parsed, batch)
                unsupported_items.extend(batch_unsupported)
                processed_batch_count += 1
            except Exception as exc:
                failed_batch_count += 1
                unsupported_items.append(f"batch_{batch_index}: {exc}")
                continue

            for event in valid_events:
                dedup_key = _event_dedup_key(event)
                if dedup_key in dedup_keys:
                    duplicate_skipped_count += 1
                    continue
                dedup_keys.add(dedup_key)
                existing_event = find_duplicate_event(
                    db,
                    case_id=case_id,
                    event_type=event["event_type"],
                    event_title=event["event_title"],
                    event_time_raw=event["event_time_raw"],
                    location_text=event["location_text"],
                    document_id=event["chunk"].document_id,
                    chunk_id=event["chunk"].id,
                    quote_text=event["quote_text"],
                )
                if existing_event is not None:
                    historical_duplicate_skipped_count += 1
                    continue
                output_position = len(response_events)
                source_reference = create_source_reference_for_run(
                    db,
                    case_id,
                    SourceReferenceCreate(
                        document_id=event["chunk"].document_id,
                        chunk_id=event["chunk"].id,
                        quote_text=event["quote_text"],
                        source_kind="chunk_quote",
                        citation_label=f"{event['document_name']}, chunk {event['chunk'].chunk_index}",
                    ),
                    extraction_run_id=run.id,
                )
                add_analysis_run_output(db, run.id, "source_reference", source_reference.id, output_position)
                persisted_event = create_event_with_source(
                    db,
                    case_id=case_id,
                    event_type=event["event_type"],
                    event_title=event["event_title"],
                    event_description=event["event_description"],
                    event_time_raw=event["event_time_raw"],
                    time_precision=event["time_precision"],
                    location_text=event["location_text"],
                    source_reference_id=source_reference.id,
                    analysis_run_id=run.id,
                )
                add_analysis_run_output(db, run.id, "event", persisted_event.id, output_position)
                response_events.append(
                    AnalysisModuleEvent(
                        event_id=persisted_event.id,
                        event_type=persisted_event.event_type,
                        event_title=persisted_event.event_title,
                        event_description=persisted_event.event_description,
                        event_time_raw=persisted_event.event_time_raw,
                        time_precision=persisted_event.time_precision,
                        location_text=persisted_event.location_text,
                        quote_text=event["quote_text"],
                        source_label=event["source_label"],
                        source_reference_id=source_reference.id,
                        document_id=event["chunk"].document_id,
                        chunk_id=event["chunk"].id,
                    )
                )

        if failed_batch_count == len(batches):
            detail = "; ".join(unsupported_items[:3])
            message = f"All event extraction batches failed: {detail}" if detail else "All event extraction batches failed"
            finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=message)
            raise AnalysisModuleError(message)

        validation_status = "passed"
        if failed_batch_count > 0 or unsupported_items or not response_events:
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
                "created_event_count": len(response_events),
                "duplicate_skipped_count": duplicate_skipped_count,
                "historical_duplicate_skipped_count": historical_duplicate_skipped_count,
                "unsupported_count": len(unsupported_items),
            },
        )
        return AnalysisModuleRunResponse(
            analysis_run_id=run.id,
            module_key="extract_events",
            model=settings.llm_chat_model,
            claims=[],
            events=response_events,
            entities=[],
            summary_items=[],
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


def _event_dedup_key(event: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _normalize_for_dedup(event["event_type"]),
        _normalize_for_dedup(event["event_title"]),
        _normalize_for_dedup(event["event_time_raw"] or ""),
        _normalize_for_dedup(event["location_text"] or ""),
    )


def _effective_event_batch_size(requested_batch_size: int) -> int:
    if requested_batch_size < 1:
        return 1
    return min(requested_batch_size, MAX_EVENT_EXTRACTION_BATCH_SIZE)


def _normalize_for_dedup(value: str) -> str:
    return " ".join(value.casefold().split())


def build_extract_events_user_prompt(
    query: str | None,
    retrieved_chunks: list[RetrievedChunk],
    batch_index: int = 1,
    batch_count: int = 1,
) -> str:
    focus_text = query.strip() if isinstance(query, str) and query.strip() else "Nincs kulon fokusz; a megadott forraschunkok esemenyjeloltjeit kell kinyerni."
    return (
        f"QUERY:\n{focus_text}\n\n"
        f"BATCH:\n{batch_index}/{batch_count}\n\n"
        f"SOURCE:\n{build_source_blocks(retrieved_chunks)}\n\n"
        "FELADAT:\n"
        "Nyerd ki a QUERY szempontjabol relevans, forrassal alatamasztott esemenyjelolteket. "
        "Ha nincs kulon fokusz, a batch forraschunkjaiban szereplo lenyeges, ellenorizheto esemenyjelolteket nyerd ki. "
        "Legfeljebb 5 events elemet adj vissza ebbol a batchbol. "
        "Az idezetek legyenek rovidek, pontosak, es teljes egeszukben szerepeljenek a megadott SOURCE chunkban. "
        "Keruld a dupla idezojelet tartalmazo idezeteket; ha megis kell ilyen karakter, ervenyes JSON modon escape-eld."
    )


def validate_extracted_events(
    payload: dict[str, Any],
    retrieved_chunks: list[RetrievedChunk],
) -> tuple[list[dict[str, Any]], list[str]]:
    events_value = payload.get("events", [])
    unsupported_value = payload.get("unsupported_events", [])
    if not isinstance(events_value, list) or not isinstance(unsupported_value, list):
        raise AnalysisModuleError("LLM JSON has invalid events or unsupported_events fields")

    chunks_by_label = {retrieved.label: retrieved for retrieved in retrieved_chunks}
    valid_events: list[dict[str, Any]] = []
    for item in events_value:
        if not isinstance(item, dict):
            continue
        event_type = item.get("event_type", "other")
        event_title = item.get("event_title")
        event_description = item.get("event_description")
        event_time_raw = item.get("event_time_raw")
        time_precision = item.get("time_precision", "unknown")
        location_text = item.get("location_text")
        quote_text = item.get("quote_text")
        source_label = item.get("source_label")
        if event_type not in SUPPORTED_EVENT_TYPES:
            event_type = "other"
        if time_precision not in SUPPORTED_TIME_PRECISIONS:
            time_precision = "unknown"
        if not isinstance(event_title, str) or not isinstance(quote_text, str) or not isinstance(source_label, str):
            continue
        if event_title.strip() == "" or quote_text.strip() == "":
            continue
        retrieved = chunks_by_label.get(source_label)
        if retrieved is None or quote_text not in retrieved.chunk.chunk_text:
            continue
        valid_events.append(
            {
                "event_type": event_type,
                "event_title": event_title,
                "event_description": event_description if isinstance(event_description, str) else None,
                "event_time_raw": event_time_raw if isinstance(event_time_raw, str) else None,
                "time_precision": time_precision,
                "location_text": location_text if isinstance(location_text, str) else None,
                "quote_text": quote_text,
                "source_label": source_label,
                "chunk": retrieved.chunk,
                "document_name": retrieved.document_name,
            }
        )

    unsupported_items = [item for item in unsupported_value if isinstance(item, str)]
    return valid_events[:5], unsupported_items
