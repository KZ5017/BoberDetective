from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.analysis_modules import AnalysisModuleMissingItemCandidate, AnalysisModuleRunRequest, AnalysisModuleRunResponse
from app.schemas.missing_item import MissingItemSourceCreate
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
from app.services.analysis_deduplication import find_duplicate_missing_item_candidate
from app.services.analysis_runs import add_analysis_run_input, add_analysis_run_output, finish_analysis_run, start_analysis_run
from app.services.llm import LLMChatMessage, LMStudioNativeProvider
from app.services.missing_items import create_missing_item_candidate
from app.services.source_references import create_source_reference_for_run


SUPPORTED_MISSING_ITEM_TYPES = {
    "attachment",
    "video",
    "expert_report",
    "protocol",
    "image",
    "document_reference",
    "other",
}

EXTRACT_MISSING_ITEMS_SYSTEM_PROMPT = """Te egy forrashu hianyzo-irat-jelolt azonosito komponens vagy.
Csak a megadott SOURCE chunkokbol dolgozhatsz.
Nem hasznalhatsz kulso tudast es nem egeszitheted ki a hianyzo tenyeket.
Csak ellenorizendo missing_item_candidates elemeket adhatsz vissza.
Nem allithatod, hogy egy hivatkozott irat biztosan hianyzik; csak azt jelezheted, hogy a forras hivatkozik egy ellenorizendo elemre.
Nem donthetsz bunossegrol, jogi minositesrol, kockazatrol vagy szemelyi felelossegrol.
Valaszolj kizarolag ervenyes JSON objektummal.
A JSON stringekben minden belso dupla idezojelet kotelezo backslash karakterrel escape-elni.
Minden missing_item_candidates elemhez kotelezo a source_label es quote_text.
quote_text mezot karakterpontosan masold ki a megfelelo SOURCE chunkbol: ne fordisd, ne javitsd, ne ekezetesitsd, ne normalizald.
quote_text legyen rovid, legfeljebb 300 karakteres, pontos, osszefuggo idezet; ne masolj teljes bekezdeseket.
Ha a valasztott idezet dupla idezojelet tartalmazna, inkabb valassz rovidebb, dupla idezojel nelkuli pontos idezetet ugyanabbol a forrasbol.
missing_item_type csak ezek egyike lehet: attachment, video, expert_report, protocol, image, document_reference, other.
Csak akkor adj jeloltet, ha a forras konkretan hivatkozik egy mellekletre, videora, kepre, szakertoi velemenyre, jegyzokonyvre vagy mas kulon iratra/targyra.
Ha nincs eleg forras egy jelolthez, ne tedd missing_item_candidates koze; tedd az unsupported_missing_item_candidates listaba.
Elvart JSON alak:
{"missing_item_candidates":[{"missing_item_type":"attachment","referenced_item_text":"...","description":"...","expected_document_type":"...","quote_text":"...","source_label":"chunk_1","confidence":"medium"}],"unsupported_missing_item_candidates":["..."]}
"""


def run_detect_missing_items(db: Session, case_id: UUID, payload: AnalysisModuleRunRequest) -> AnalysisModuleRunResponse:
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
        "detect_missing_items",
        provider_type="lm_studio_native",
        model_name=settings.llm_chat_model,
        input_parameters=input_parameters,
        prompt_template_name="detect_missing_items_v1",
        prompt_template_version="1",
        output_schema_name="detect_missing_items",
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
        response_candidates: list[AnalysisModuleMissingItemCandidate] = []
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
                        LLMChatMessage(role="system", content=EXTRACT_MISSING_ITEMS_SYSTEM_PROMPT),
                        LLMChatMessage(
                            role="user",
                            content=build_detect_missing_items_user_prompt(payload.query, batch, batch_index, len(batches)),
                        ),
                    ],
                    temperature=0.1,
                    max_tokens=1600,
                )
                parsed = parse_llm_json_object(completion.content)
                valid_candidates, batch_unsupported = validate_extracted_missing_item_candidates(parsed, batch)
                unsupported_items.extend(batch_unsupported)
                processed_batch_count += 1
            except Exception as exc:
                failed_batch_count += 1
                unsupported_items.append(f"batch_{batch_index}: {exc}")
                continue

            for candidate in valid_candidates:
                dedup_key = _missing_item_dedup_key(candidate)
                if dedup_key in dedup_keys:
                    duplicate_skipped_count += 1
                    continue
                dedup_keys.add(dedup_key)
                existing_candidate = find_duplicate_missing_item_candidate(
                    db,
                    case_id=case_id,
                    missing_item_type=candidate["missing_item_type"],
                    referenced_item_text=candidate["referenced_item_text"],
                    expected_document_type=candidate["expected_document_type"],
                    document_id=candidate["chunk"].document_id,
                    chunk_id=candidate["chunk"].id,
                    quote_text=candidate["quote_text"],
                )
                if existing_candidate is not None:
                    historical_duplicate_skipped_count += 1
                    continue
                output_position = len(response_candidates)
                source_reference = create_source_reference_for_run(
                    db,
                    case_id,
                    SourceReferenceCreate(
                        document_id=candidate["chunk"].document_id,
                        chunk_id=candidate["chunk"].id,
                        quote_text=candidate["quote_text"],
                        source_kind="chunk_quote",
                        citation_label=f"{candidate['document_name']}, chunk {candidate['chunk'].chunk_index}",
                    ),
                    extraction_run_id=run.id,
                )
                add_analysis_run_output(db, run.id, "source_reference", source_reference.id, output_position)
                persisted_candidate = create_missing_item_candidate(
                    db,
                    case_id=case_id,
                    missing_item_type=candidate["missing_item_type"],
                    referenced_item_text=candidate["referenced_item_text"],
                    description=candidate["description"],
                    expected_document_type=candidate["expected_document_type"],
                    confidence=candidate["confidence"],
                    analysis_run_id=run.id,
                    sources=[MissingItemSourceCreate(source_reference_id=source_reference.id, relevance_rank=output_position)],
                )
                add_analysis_run_output(db, run.id, "missing_item_candidate", persisted_candidate.id, output_position)
                response_candidates.append(
                    AnalysisModuleMissingItemCandidate(
                        missing_item_candidate_id=persisted_candidate.id,
                        missing_item_type=persisted_candidate.missing_item_type,
                        referenced_item_text=persisted_candidate.referenced_item_text,
                        description=persisted_candidate.description,
                        expected_document_type=persisted_candidate.expected_document_type,
                        quote_text=candidate["quote_text"],
                        source_label=candidate["source_label"],
                        source_reference_id=source_reference.id,
                        document_id=candidate["chunk"].document_id,
                        chunk_id=candidate["chunk"].id,
                    )
                )

        if failed_batch_count == len(batches):
            detail = "; ".join(unsupported_items[:3])
            message = f"All missing item extraction batches failed: {detail}" if detail else "All missing item extraction batches failed"
            finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=message)
            raise AnalysisModuleError(message)

        validation_status = "passed"
        if failed_batch_count > 0 or unsupported_items or not response_candidates:
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
                "created_missing_item_candidate_count": len(response_candidates),
                "duplicate_skipped_count": duplicate_skipped_count,
                "historical_duplicate_skipped_count": historical_duplicate_skipped_count,
                "unsupported_count": len(unsupported_items),
            },
        )
        return AnalysisModuleRunResponse(
            analysis_run_id=run.id,
            module_key="detect_missing_items",
            model=settings.llm_chat_model,
            claims=[],
            events=[],
            entities=[],
            summary_items=[],
            contradiction_candidates=[],
            missing_item_candidates=response_candidates,
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


def _missing_item_dedup_key(candidate: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _normalize_for_dedup(candidate["missing_item_type"]),
        _normalize_for_dedup(candidate["referenced_item_text"]),
        _normalize_for_dedup(candidate["expected_document_type"] or ""),
    )


def _normalize_for_dedup(value: str) -> str:
    return " ".join(value.casefold().split())


def build_detect_missing_items_user_prompt(
    query: str | None,
    retrieved_chunks: list[RetrievedChunk],
    batch_index: int = 1,
    batch_count: int = 1,
) -> str:
    focus_text = query.strip() if isinstance(query, str) and query.strip() else "Nincs kulon fokusz; a megadott forraschunkok ellenorizendo irat/targy hivatkozasait kell kinyerni."
    return (
        f"QUERY:\n{focus_text}\n\n"
        f"BATCH:\n{batch_index}/{batch_count}\n\n"
        f"SOURCE:\n{build_source_blocks(retrieved_chunks)}\n\n"
        "FELADAT:\n"
        "Keress legfeljebb 5 ellenorizendo hianyzo vagy kulon bekerendo irat/targy jeloltet ebbol a batchbol. "
        "Csak forrasidezettel alatamasztott jeloltet adj vissza. "
        "Ne allitsd, hogy az elem tenylegesen hianyzik; csak azt rogzitsd, hogy a forras kulon ellenorizendo elemre hivatkozik. "
        "Az idezetek legyenek rovidek, pontosak, es teljes egeszukben szerepeljenek a megadott SOURCE chunkban. "
        "Keruld a dupla idezojelet tartalmazo idezeteket; ha megis kell ilyen karakter, ervenyes JSON modon escape-eld."
    )


def validate_extracted_missing_item_candidates(
    payload: dict[str, Any],
    retrieved_chunks: list[RetrievedChunk],
) -> tuple[list[dict[str, Any]], list[str]]:
    candidates_value = payload.get("missing_item_candidates", [])
    unsupported_value = payload.get("unsupported_missing_item_candidates", [])
    if not isinstance(candidates_value, list) or not isinstance(unsupported_value, list):
        raise AnalysisModuleError("LLM JSON has invalid missing_item_candidates or unsupported_missing_item_candidates fields")

    chunks_by_label = {retrieved.label: retrieved for retrieved in retrieved_chunks}
    valid_candidates: list[dict[str, Any]] = []
    for item in candidates_value:
        if not isinstance(item, dict):
            continue
        missing_item_type = item.get("missing_item_type", "other")
        referenced_item_text = item.get("referenced_item_text")
        description = item.get("description")
        expected_document_type = item.get("expected_document_type")
        quote_text = item.get("quote_text")
        source_label = item.get("source_label")
        confidence = _normalized_confidence(item.get("confidence"))
        if missing_item_type not in SUPPORTED_MISSING_ITEM_TYPES:
            missing_item_type = "other"
        if expected_document_type is not None and not isinstance(expected_document_type, str):
            expected_document_type = None
        if not all(isinstance(value, str) for value in [referenced_item_text, description, quote_text, source_label]):
            continue
        if referenced_item_text.strip() == "" or description.strip() == "" or quote_text.strip() == "":
            continue
        retrieved = chunks_by_label.get(source_label)
        if retrieved is None or quote_text not in retrieved.chunk.chunk_text:
            continue
        valid_candidates.append(
            {
                "missing_item_type": missing_item_type,
                "referenced_item_text": referenced_item_text,
                "description": description,
                "expected_document_type": expected_document_type,
                "quote_text": quote_text,
                "source_label": source_label,
                "confidence": confidence,
                "chunk": retrieved.chunk,
                "document_name": retrieved.document_name,
            }
        )

    unsupported_items = [item for item in unsupported_value if isinstance(item, str)]
    return valid_candidates[:5], unsupported_items


def _normalized_confidence(value: Any) -> Decimal | None:
    if isinstance(value, int | float):
        if 0 <= value <= 1:
            return Decimal(str(value))
        return None
    if isinstance(value, str):
        mapping = {"low": Decimal("0.3000"), "medium": Decimal("0.6000"), "high": Decimal("0.9000")}
        return mapping.get(value.strip().lower())
    return None
