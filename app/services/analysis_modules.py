from dataclasses import dataclass
from typing import Any
from uuid import UUID
import json
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import DocumentChunkModel
from app.schemas.analysis_modules import AnalysisModuleClaim, AnalysisModuleEvent, AnalysisModuleRunRequest, AnalysisModuleRunResponse
from app.schemas.search import KeywordSearchRequest, SearchFilters
from app.schemas.source_reference import SourceReferenceCreate
from app.services.analysis_runs import (
    add_analysis_run_input,
    add_analysis_run_output,
    finish_analysis_run,
    start_analysis_run,
)
from app.services.claims import create_claim_with_source
from app.services.events import create_event_with_source
from app.services.llm import LLMChatMessage, LMStudioNativeProvider
from app.services.search import keyword_search
from app.services.source_references import create_source_reference_for_run


SUPPORTED_CLAIM_TYPES = {
    "witness_statement",
    "document_fact",
    "expert_opinion",
    "administrative_fact",
    "inference_candidate",
    "unknown",
}
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
SUPPORTED_MODULES = {"extract_claims", "extract_events"}

EXTRACT_CLAIMS_SYSTEM_PROMPT = """Te egy forrashu iratelemzo komponens vagy.
Csak a megadott SOURCE chunkokbol dolgozhatsz.
Nem hasznalhatsz kulso tudast es nem egeszitheted ki a hianyzo tenyeket.
Nem donthetsz bunossegrol, jogi minositesrol, kockazatrol vagy szemelyi felelossegrol.
Nem allapithatod meg, hogy egy allitas igaz; csak azt rogzitheted, hogy a forras mit allit vagy tartalmaz.
Valaszolj kizarolag ervenyes JSON objektummal.
Minden claims elemhez kotelezo a source_label es quote_text.
quote_text mezot karakterpontosan masold ki a megfelelo SOURCE chunkbol: ne fordisd, ne javitsd, ne ekezetesitsd, ne normalizald.
Ha nincs eleg forras egy allitashoz, ne tedd claims koze; tedd az unsupported_claims listaba.
Elvart JSON alak:
{"claims":[{"claim_type":"document_fact","claim_text":"...","quote_text":"...","source_label":"chunk_1"}],"unsupported_claims":["..."]}
"""

EXTRACT_EVENTS_SYSTEM_PROMPT = """Te egy forrashu iratelemzo komponens vagy.
Csak a megadott SOURCE chunkokbol dolgozhatsz.
Nem hasznalhatsz kulso tudast es nem egeszitheted ki a hianyzo tenyeket.
Csak esemenyjelolteket adhatsz vissza; nem allithatod, hogy az esemeny bizonyosan megtortent, ha a forras csak allitja vagy hivatkozza.
Nem donthetsz bunossegrol, jogi minositesrol, kockazatrol vagy szemelyi felelossegrol.
Valaszolj kizarolag ervenyes JSON objektummal.
Minden events elemhez kotelezo a source_label es quote_text.
quote_text mezot karakterpontosan masold ki a megfelelo SOURCE chunkbol: ne fordisd, ne javitsd, ne ekezetesitsd, ne normalizald.
Ha nincs eleg forras egy esemenyhez, ne tedd events koze; tedd az unsupported_events listaba.
Elvart JSON alak:
{"events":[{"event_type":"call","event_title":"...","event_description":"...","event_time_raw":"...","time_precision":"minute","location_text":null,"quote_text":"...","source_label":"chunk_1"}],"unsupported_events":["..."]}
"""


class AnalysisModuleError(ValueError):
    pass


@dataclass(frozen=True)
class RetrievedChunk:
    label: str
    document_name: str
    chunk: DocumentChunkModel
    retrieval_score: float


def run_analysis_module(
    db: Session,
    case_id: UUID,
    module_key: str,
    payload: AnalysisModuleRunRequest,
) -> AnalysisModuleRunResponse:
    if module_key not in SUPPORTED_MODULES:
        raise AnalysisModuleError("Unsupported analysis module")
    if module_key == "extract_events":
        return _run_extract_events(db, case_id, payload)
    return _run_extract_claims(db, case_id, payload)


def _run_extract_claims(
    db: Session,
    case_id: UUID,
    payload: AnalysisModuleRunRequest,
) -> AnalysisModuleRunResponse:
    settings = get_settings()
    run = start_analysis_run(
        db,
        case_id,
        "extract_claims",
        provider_type="lm_studio_native",
        model_name=settings.llm_chat_model,
        input_parameters={"query": payload.query, "limit": payload.limit},
        prompt_template_name="extract_claims_v1",
        prompt_template_version="1",
        output_schema_name="extract_claims",
        output_schema_version="1",
        retrieval_strategy="keyword_chunks_v1",
    )
    try:
        add_analysis_run_input(db, run.id, "query_text", 0, payload_json={"query": payload.query})
        retrieved_chunks = _retrieve_chunks(db, case_id, payload)
        if not retrieved_chunks:
            finish_analysis_run(
                db,
                run,
                status="failed",
                validation_status="failed",
                error_message="No chunk retrieval hit for query",
            )
            raise AnalysisModuleError("No chunk retrieval hit for query")

        for index, retrieved in enumerate(retrieved_chunks, start=1):
            add_analysis_run_input(
                db,
                run.id,
                "chunk",
                index,
                document_id=retrieved.chunk.document_id,
                chunk_id=retrieved.chunk.id,
                payload_json={"source_label": retrieved.label, "retrieval_score": retrieved.retrieval_score},
            )

        completion = LMStudioNativeProvider(settings).chat_completion(
            settings.llm_chat_model,
            [
                LLMChatMessage(role="system", content=EXTRACT_CLAIMS_SYSTEM_PROMPT),
                LLMChatMessage(role="user", content=_build_extract_claims_user_prompt(payload.query, retrieved_chunks)),
            ],
            temperature=0.1,
            max_tokens=1600,
        )
        parsed = parse_llm_json_object(completion.content)
        valid_claims, unsupported_items = validate_extracted_claims(parsed, retrieved_chunks)

        response_claims: list[AnalysisModuleClaim] = []
        for index, claim in enumerate(valid_claims):
            source_reference = create_source_reference_for_run(
                db,
                case_id,
                SourceReferenceCreate(
                    document_id=claim["chunk"].document_id,
                    chunk_id=claim["chunk"].id,
                    quote_text=claim["quote_text"],
                    source_kind="chunk_quote",
                    citation_label=f"{claim['document_name']}, chunk {claim['chunk'].chunk_index}",
                ),
                extraction_run_id=run.id,
            )
            add_analysis_run_output(db, run.id, "source_reference", source_reference.id, index)
            persisted_claim = create_claim_with_source(
                db,
                case_id=case_id,
                claim_text=claim["claim_text"],
                source_reference_id=source_reference.id,
                analysis_run_id=run.id,
                claim_type=claim["claim_type"],
            )
            add_analysis_run_output(db, run.id, "claim", persisted_claim.id, index)
            response_claims.append(
                AnalysisModuleClaim(
                    claim_id=persisted_claim.id,
                    claim_type=persisted_claim.claim_type,
                    claim_text=persisted_claim.claim_text,
                    quote_text=claim["quote_text"],
                    source_label=claim["source_label"],
                    source_reference_id=source_reference.id,
                    document_id=claim["chunk"].document_id,
                    chunk_id=claim["chunk"].id,
                )
            )

        validation_status = "passed" if response_claims or unsupported_items else "warning"
        finish_analysis_run(
            db,
            run,
            status="succeeded",
            validation_status=validation_status,
            output_summary={"claim_count": len(response_claims), "unsupported_count": len(unsupported_items)},
        )
        return AnalysisModuleRunResponse(
            analysis_run_id=run.id,
            module_key="extract_claims",
            model=settings.llm_chat_model,
            claims=response_claims,
            events=[],
            unsupported_items=unsupported_items,
            selected_chunk_ids=[retrieved.chunk.id for retrieved in retrieved_chunks],
            validation_status=validation_status,
        )
    except Exception as exc:
        if run.status == "running":
            finish_analysis_run(
                db,
                run,
                status="failed",
                validation_status="failed",
                error_message=str(exc),
            )
        if isinstance(exc, AnalysisModuleError):
            raise
        raise AnalysisModuleError(str(exc)) from exc


def _run_extract_events(
    db: Session,
    case_id: UUID,
    payload: AnalysisModuleRunRequest,
) -> AnalysisModuleRunResponse:
    settings = get_settings()
    run = start_analysis_run(
        db,
        case_id,
        "extract_events",
        provider_type="lm_studio_native",
        model_name=settings.llm_chat_model,
        input_parameters={"query": payload.query, "limit": payload.limit},
        prompt_template_name="extract_events_v1",
        prompt_template_version="1",
        output_schema_name="extract_events",
        output_schema_version="1",
        retrieval_strategy="keyword_chunks_v1",
    )
    try:
        add_analysis_run_input(db, run.id, "query_text", 0, payload_json={"query": payload.query})
        retrieved_chunks = _retrieve_chunks(db, case_id, payload)
        if not retrieved_chunks:
            finish_analysis_run(db, run, status="failed", validation_status="failed", error_message="No chunk retrieval hit for query")
            raise AnalysisModuleError("No chunk retrieval hit for query")

        for index, retrieved in enumerate(retrieved_chunks, start=1):
            add_analysis_run_input(
                db,
                run.id,
                "chunk",
                index,
                document_id=retrieved.chunk.document_id,
                chunk_id=retrieved.chunk.id,
                payload_json={"source_label": retrieved.label, "retrieval_score": retrieved.retrieval_score},
            )

        completion = LMStudioNativeProvider(settings).chat_completion(
            settings.llm_chat_model,
            [
                LLMChatMessage(role="system", content=EXTRACT_EVENTS_SYSTEM_PROMPT),
                LLMChatMessage(role="user", content=_build_extract_events_user_prompt(payload.query, retrieved_chunks)),
            ],
            temperature=0.1,
            max_tokens=1600,
        )
        parsed = parse_llm_json_object(completion.content)
        valid_events, unsupported_items = validate_extracted_events(parsed, retrieved_chunks)

        response_events: list[AnalysisModuleEvent] = []
        for index, event in enumerate(valid_events):
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
            add_analysis_run_output(db, run.id, "source_reference", source_reference.id, index)
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
            add_analysis_run_output(db, run.id, "event", persisted_event.id, index)
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

        validation_status = "passed" if response_events or unsupported_items else "warning"
        finish_analysis_run(
            db,
            run,
            status="succeeded",
            validation_status=validation_status,
            output_summary={"event_count": len(response_events), "unsupported_count": len(unsupported_items)},
        )
        return AnalysisModuleRunResponse(
            analysis_run_id=run.id,
            module_key="extract_events",
            model=settings.llm_chat_model,
            claims=[],
            events=response_events,
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


def _retrieve_chunks(db: Session, case_id: UUID, payload: AnalysisModuleRunRequest) -> list[RetrievedChunk]:
    hits = keyword_search(
        db,
        case_id,
        KeywordSearchRequest(
            query=payload.query,
            filters=SearchFilters(),
            limit=payload.limit,
            include_quotes=False,
            target="chunks",
        ),
    )
    retrieved_chunks: list[RetrievedChunk] = []
    seen_chunk_ids: set[UUID] = set()
    for hit in hits:
        if hit.chunk_id is None or hit.chunk_id in seen_chunk_ids:
            continue
        chunk = db.get(DocumentChunkModel, hit.chunk_id)
        if chunk is None:
            continue
        seen_chunk_ids.add(chunk.id)
        retrieved_chunks.append(
            RetrievedChunk(
                label=f"chunk_{len(retrieved_chunks) + 1}",
                document_name=hit.document_name,
                chunk=chunk,
                retrieval_score=hit.score,
            )
        )
    return retrieved_chunks


def _build_extract_claims_user_prompt(query: str, retrieved_chunks: list[RetrievedChunk]) -> str:
    source_blocks = []
    for retrieved in retrieved_chunks:
        source_blocks.append(
            f"{retrieved.label}:\n"
            f"document_id: {retrieved.chunk.document_id}\n"
            f"document_name: {retrieved.document_name}\n"
            f"page_start: {retrieved.chunk.page_start}\n"
            f"page_end: {retrieved.chunk.page_end}\n"
            f"text:\n{retrieved.chunk.chunk_text}"
        )
    return (
        f"QUERY:\n{query}\n\n"
        f"SOURCE:\n{chr(10).join(source_blocks)}\n\n"
        "FELADAT:\n"
        "Nyerd ki a QUERY szempontjabol relevans, forrassal alatamasztott allitasokat. "
        "Legfeljebb 5 claims elemet adj vissza."
    )


def _build_extract_events_user_prompt(query: str, retrieved_chunks: list[RetrievedChunk]) -> str:
    source_blocks = []
    for retrieved in retrieved_chunks:
        source_blocks.append(
            f"{retrieved.label}:\n"
            f"document_id: {retrieved.chunk.document_id}\n"
            f"document_name: {retrieved.document_name}\n"
            f"page_start: {retrieved.chunk.page_start}\n"
            f"page_end: {retrieved.chunk.page_end}\n"
            f"text:\n{retrieved.chunk.chunk_text}"
        )
    return (
        f"QUERY:\n{query}\n\n"
        f"SOURCE:\n{chr(10).join(source_blocks)}\n\n"
        "FELADAT:\n"
        "Nyerd ki a QUERY szempontjabol relevans, forrassal alatamasztott esemenyjelolteket. "
        "Legfeljebb 5 events elemet adj vissza."
    )


def parse_llm_json_object(raw_content: str) -> dict[str, Any]:
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AnalysisModuleError("LLM returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise AnalysisModuleError("LLM returned a non-object JSON value")
    return payload


def validate_extracted_claims(
    payload: dict[str, Any],
    retrieved_chunks: list[RetrievedChunk],
) -> tuple[list[dict[str, Any]], list[str]]:
    claims_value = payload.get("claims", [])
    unsupported_value = payload.get("unsupported_claims", [])
    if not isinstance(claims_value, list) or not isinstance(unsupported_value, list):
        raise AnalysisModuleError("LLM JSON has invalid claims or unsupported_claims fields")

    chunks_by_label = {retrieved.label: retrieved for retrieved in retrieved_chunks}
    valid_claims: list[dict[str, Any]] = []
    for item in claims_value:
        if not isinstance(item, dict):
            continue
        claim_type = item.get("claim_type", "document_fact")
        claim_text = item.get("claim_text")
        quote_text = item.get("quote_text")
        source_label = item.get("source_label")
        if claim_type not in SUPPORTED_CLAIM_TYPES:
            claim_type = "unknown"
        if not isinstance(claim_text, str) or not isinstance(quote_text, str) or not isinstance(source_label, str):
            continue
        if claim_text.strip() == "" or quote_text.strip() == "":
            continue
        retrieved = chunks_by_label.get(source_label)
        if retrieved is None:
            continue
        if quote_text not in retrieved.chunk.chunk_text:
            continue
        valid_claims.append(
            {
                "claim_type": claim_type,
                "claim_text": claim_text,
                "quote_text": quote_text,
                "source_label": source_label,
                "chunk": retrieved.chunk,
                "document_name": retrieved.document_name,
            }
        )

    unsupported_items = [item for item in unsupported_value if isinstance(item, str)]
    return valid_claims[:5], unsupported_items


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
