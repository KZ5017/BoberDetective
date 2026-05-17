from typing import Any
from uuid import UUID
import json
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.analysis_modules import AnalysisModuleClaim, AnalysisModuleRunRequest, AnalysisModuleRunResponse
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
from app.services.analysis_deduplication import find_duplicate_claim
from app.services.analysis_runs import add_analysis_run_input, add_analysis_run_output, finish_analysis_run, start_analysis_run
from app.services.claims import create_claim_with_source
from app.services.llm import LLMChatMessage, LMStudioNativeProvider
from app.services.source_references import create_source_reference_for_run


SUPPORTED_CLAIM_TYPES = {
    "witness_statement",
    "document_fact",
    "expert_opinion",
    "administrative_fact",
    "inference_candidate",
    "unknown",
}

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

CLAIMS_JSON_REPAIR_SYSTEM_PROMPT = """Te egy szigoruan technikai JSON-javito komponens vagy.
Feladatod csak az, hogy a kapott, hibas JSON-szeru szoveget ervenyes JSON objektumma javitsd.
Nem adhatsz hozza uj allitast, nem torolhetsz forrasmegjelolest, nem egeszitheted ki a tartalmat kulso tudassal.
Kulonosen figyelj arra, hogy a quote_text mezokben levo idezojeleket JSON szerint escape-eld.
Valaszolj kizarolag ervenyes JSON objektummal ebben az alakban:
{"claims":[{"claim_type":"document_fact","claim_text":"...","quote_text":"...","source_label":"chunk_1"}],"unsupported_claims":["..."]}
"""


def run_extract_claims(db: Session, case_id: UUID, payload: AnalysisModuleRunRequest) -> AnalysisModuleRunResponse:
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
        "extract_claims",
        provider_type="lm_studio_native",
        model_name=settings.llm_chat_model,
        input_parameters=input_parameters,
        prompt_template_name="extract_claims_v1",
        prompt_template_version="1",
        output_schema_name="extract_claims",
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
        response_claims: list[AnalysisModuleClaim] = []
        unsupported_items: list[str] = []
        duplicate_skipped_count = 0
        historical_duplicate_skipped_count = 0
        failed_batch_count = 0
        processed_batch_count = 0
        dedup_keys: set[tuple[UUID, str, str]] = set()

        for batch_index, batch in enumerate(batches, start=1):
            try:
                provider = LMStudioNativeProvider(settings)
                completion = provider.chat_completion(
                    settings.llm_chat_model,
                    [
                        LLMChatMessage(role="system", content=EXTRACT_CLAIMS_SYSTEM_PROMPT),
                        LLMChatMessage(
                            role="user",
                            content=build_extract_claims_user_prompt(payload.query, batch, batch_index, len(batches)),
                        ),
                    ],
                    temperature=0.1,
                    max_tokens=1600,
                )
                parsed = parse_claims_json_with_repair(completion.content, provider, settings.llm_chat_model)
                valid_claims, batch_unsupported = validate_extracted_claims(parsed, batch)
                unsupported_items.extend(batch_unsupported)
                processed_batch_count += 1
            except Exception as exc:
                failed_batch_count += 1
                unsupported_items.append(f"batch_{batch_index}: {exc}")
                continue

            for claim in valid_claims:
                dedup_key = _claim_dedup_key(claim)
                if dedup_key in dedup_keys:
                    duplicate_skipped_count += 1
                    continue
                dedup_keys.add(dedup_key)
                existing_claim = find_duplicate_claim(
                    db,
                    case_id=case_id,
                    claim_type=claim["claim_type"],
                    claim_text=claim["claim_text"],
                    document_id=claim["chunk"].document_id,
                    chunk_id=claim["chunk"].id,
                    quote_text=claim["quote_text"],
                )
                if existing_claim is not None:
                    historical_duplicate_skipped_count += 1
                    continue
                output_position = len(response_claims)
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
                add_analysis_run_output(db, run.id, "source_reference", source_reference.id, output_position)
                persisted_claim = create_claim_with_source(
                    db,
                    case_id=case_id,
                    claim_text=claim["claim_text"],
                    source_reference_id=source_reference.id,
                    analysis_run_id=run.id,
                    claim_type=claim["claim_type"],
                )
                add_analysis_run_output(db, run.id, "claim", persisted_claim.id, output_position)
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

        if failed_batch_count == len(batches):
            message = "Az osszes allitaskinyeresi batch sikertelen volt"
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
        if failed_batch_count > 0 or unsupported_items or not response_claims:
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
                "created_claim_count": len(response_claims),
                "duplicate_skipped_count": duplicate_skipped_count,
                "historical_duplicate_skipped_count": historical_duplicate_skipped_count,
                "unsupported_count": len(unsupported_items),
            },
        )
        return AnalysisModuleRunResponse(
            analysis_run_id=run.id,
            module_key="extract_claims",
            model=settings.llm_chat_model,
            claims=response_claims,
            events=[],
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


def _claim_dedup_key(claim: dict[str, Any]) -> tuple[str, str]:
    return (
        _normalize_for_dedup(claim["claim_type"]),
        _normalize_for_dedup(claim["claim_text"]),
    )


def parse_claims_json_with_repair(raw_content: str, provider: LMStudioNativeProvider, model: str) -> dict[str, Any]:
    try:
        return parse_llm_json_object(raw_content)
    except AnalysisModuleError as first_error:
        lenient_payload = parse_claims_json_lenient(raw_content)
        if lenient_payload is not None:
            return lenient_payload
        repair_completion = provider.chat_completion(
            model,
            [
                LLMChatMessage(role="system", content=CLAIMS_JSON_REPAIR_SYSTEM_PROMPT),
                LLMChatMessage(
                    role="user",
                    content=(
                        "HIBAS JSON-SZERU VALASZ:\n"
                        f"{raw_content}\n\n"
                        "Javitsd ervenyes JSON objektumma. Csak a JSON-t add vissza."
                    ),
                ),
            ],
            temperature=0.0,
            max_tokens=2200,
        )
        try:
            return parse_llm_json_object(repair_completion.content)
        except AnalysisModuleError as repair_error:
            lenient_payload = parse_claims_json_lenient(repair_completion.content)
            if lenient_payload is not None:
                return lenient_payload
            raise AnalysisModuleError(f"{first_error}; JSON repair failed: {repair_error}") from repair_error


def parse_claims_json_lenient(raw_content: str) -> dict[str, Any] | None:
    claim_objects = _extract_claim_like_objects(raw_content)
    claims = []
    for item in claim_objects:
        claim_type = _extract_json_like_string_field(item, "claim_type")
        claim_text = _extract_json_like_string_field(item, "claim_text")
        quote_text = _extract_json_like_string_field(item, "quote_text")
        source_label = _extract_json_like_string_field(item, "source_label")
        if claim_text is None or quote_text is None or source_label is None:
            continue
        claims.append(
            {
                "claim_type": claim_type or "document_fact",
                "claim_text": claim_text,
                "quote_text": quote_text,
                "source_label": source_label,
            }
        )
    if not claims:
        return None
    return {"claims": claims, "unsupported_claims": _extract_unsupported_claims_lenient(raw_content)}


def _extract_claim_like_objects(raw_content: str) -> list[str]:
    claims_match = re.search(r'"claims"\s*:\s*\[', raw_content)
    if claims_match is None:
        return []
    index = claims_match.end()
    depth = 0
    object_start: int | None = None
    objects: list[str] = []
    while index < len(raw_content):
        char = raw_content[index]
        if char == "]" and depth == 0:
            break
        if char == "{":
            if depth == 0:
                object_start = index
            depth += 1
        elif char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and object_start is not None:
                objects.append(raw_content[object_start : index + 1])
                object_start = None
        index += 1
    return objects


def _extract_json_like_string_field(object_text: str, field_name: str) -> str | None:
    pattern = rf'"{re.escape(field_name)}"\s*:\s*"(?P<value>.*?)"\s*(?=,\s*"[a-zA-Z_]+":|\s*}})'
    match = re.search(pattern, object_text, flags=re.DOTALL)
    if match is None:
        return None
    value = match.group("value")
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value


def _extract_unsupported_claims_lenient(raw_content: str) -> list[str]:
    match = re.search(r'"unsupported_claims"\s*:\s*(\[[\s\S]*?\])', raw_content)
    if match is None:
        return []
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    return [item for item in value if isinstance(item, str)]


def _normalize_for_dedup(value: str) -> str:
    return " ".join(value.casefold().split())


def build_extract_claims_user_prompt(
    query: str | None,
    retrieved_chunks: list[RetrievedChunk],
    batch_index: int = 1,
    batch_count: int = 1,
) -> str:
    focus_text = query.strip() if isinstance(query, str) and query.strip() else "Nincs kulon fokusz; a megadott forraschunkok fontos allitasait kell kinyerni."
    return (
        f"QUERY:\n{focus_text}\n\n"
        f"BATCH:\n{batch_index}/{batch_count}\n\n"
        f"SOURCE:\n{build_source_blocks(retrieved_chunks)}\n\n"
        "FELADAT:\n"
        "Nyerd ki a QUERY szempontjabol relevans, forrassal alatamasztott allitasokat. "
        "Ha nincs kulon fokusz, a batch forraschunkjaiban szereplo lenyeges, ellenorizheto allitasokat nyerd ki. "
        "Legfeljebb 5 claims elemet adj vissza ebbol a batchbol."
    )


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
