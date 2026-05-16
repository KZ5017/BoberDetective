from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.analysis_modules import AnalysisModuleEntity, AnalysisModuleRunRequest, AnalysisModuleRunResponse
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
from app.services.entities import create_entity_with_mention
from app.services.llm import LLMChatMessage, LMStudioNativeProvider
from app.services.source_references import create_source_reference_for_run


SUPPORTED_ENTITY_TYPES = {
    "person",
    "organization",
    "location",
    "phone",
    "email",
    "license_plate",
    "case_reference",
    "money_amount",
    "document_reference",
    "other",
}

EXTRACT_ENTITIES_SYSTEM_PROMPT = """Te egy forrashu iratelemzo komponens vagy.
Csak a megadott SOURCE chunkokbol dolgozhatsz.
Nem hasznalhatsz kulso tudast es nem egeszitheted ki a hianyzo tenyeket.
Azonosithatsz szemelyeket, szervezeteket, helyszineket es strukturalt azonosito jellegu ertekeket.
Nem adhatsz szerep-, felelosseg-, bunosseg- vagy kockazati minositest.
Valaszolj kizarolag ervenyes JSON objektummal.
A JSON stringekben minden belso dupla idezojelet kotelezo backslash karakterrel escape-elni.
Minden entities elemhez legalabb egy mention kell.
Minden mentionhoz kotelezo a source_label es quote_text.
quote_text mezot karakterpontosan masold ki a megfelelo SOURCE chunkbol: ne fordisd, ne javitsd, ne ekezetesitsd, ne normalizald.
quote_text legyen rovid, legfeljebb 300 karakteres, pontos, osszefuggo idezet; ne masolj teljes bekezdeseket.
Ha a valasztott idezet dupla idezojelet tartalmazna, inkabb valassz rovidebb, dupla idezojel nelkuli pontos idezetet ugyanabbol a forrasbol.
entity_type csak ezek egyike lehet: person, organization, location, phone, email, license_plate, case_reference, money_amount, document_reference, other.
Ha nincs eleg forras egy entitashoz, ne tedd entities koze; tedd az unsupported_entities listaba.
Elvart JSON alak:
{"entities":[{"entity_type":"person","canonical_name":"...","normalized_value":null,"description":null,"mentions":[{"surface_text":"...","quote_text":"...","source_label":"chunk_1"}]}],"unsupported_entities":["..."]}
"""


def run_extract_entities(db: Session, case_id: UUID, payload: AnalysisModuleRunRequest) -> AnalysisModuleRunResponse:
    settings = get_settings()
    input_parameters = {
        "query": payload.query,
        "source_mode": payload.source_mode,
        "document_id": str(payload.document_id) if payload.document_id is not None else None,
        "page_start": payload.page_start,
        "page_end": payload.page_end,
        "max_chunks": payload.max_chunks,
        "batch_size": payload.batch_size,
        "retrieval_strategy": payload.retrieval_strategy,
    }
    run = start_analysis_run(
        db,
        case_id,
        "extract_entities",
        provider_type="lm_studio_native",
        model_name=settings.llm_chat_model,
        input_parameters=input_parameters,
        prompt_template_name="extract_entities_v1",
        prompt_template_version="1",
        output_schema_name="extract_entities",
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
        response_entities: list[AnalysisModuleEntity] = []
        unsupported_items: list[str] = []
        duplicate_skipped_count = 0
        failed_batch_count = 0
        processed_batch_count = 0
        dedup_keys: set[tuple[UUID, str, str, str, str, str]] = set()

        for batch_index, batch in enumerate(batches, start=1):
            try:
                completion = LMStudioNativeProvider(settings).chat_completion(
                    settings.llm_chat_model,
                    [
                        LLMChatMessage(role="system", content=EXTRACT_ENTITIES_SYSTEM_PROMPT),
                        LLMChatMessage(
                            role="user",
                            content=build_extract_entities_user_prompt(payload.query, batch, batch_index, len(batches)),
                        ),
                    ],
                    temperature=0.1,
                    max_tokens=1600,
                )
                parsed = parse_llm_json_object(completion.content)
                valid_entities, batch_unsupported = validate_extracted_entities(parsed, batch)
                unsupported_items.extend(batch_unsupported)
                processed_batch_count += 1
            except Exception as exc:
                failed_batch_count += 1
                unsupported_items.append(f"batch_{batch_index}: {exc}")
                continue

            for entity in valid_entities:
                dedup_key = _entity_dedup_key(entity)
                if dedup_key in dedup_keys:
                    duplicate_skipped_count += 1
                    continue
                dedup_keys.add(dedup_key)
                output_position = len(response_entities)
                source_reference = create_source_reference_for_run(
                    db,
                    case_id,
                    SourceReferenceCreate(
                        document_id=entity["chunk"].document_id,
                        chunk_id=entity["chunk"].id,
                        quote_text=entity["quote_text"],
                        source_kind="chunk_quote",
                        citation_label=f"{entity['document_name']}, chunk {entity['chunk'].chunk_index}",
                    ),
                    extraction_run_id=run.id,
                )
                add_analysis_run_output(db, run.id, "source_reference", source_reference.id, output_position)
                persisted_entity, mention = create_entity_with_mention(
                    db,
                    case_id=case_id,
                    entity_type=entity["entity_type"],
                    canonical_name=entity["canonical_name"],
                    normalized_value=entity["normalized_value"],
                    description=entity["description"],
                    surface_text=entity["surface_text"],
                    source_reference_id=source_reference.id,
                    analysis_run_id=run.id,
                )
                add_analysis_run_output(db, run.id, "entity", persisted_entity.id, output_position)
                add_analysis_run_output(db, run.id, "mention", mention.id, output_position)
                response_entities.append(
                    AnalysisModuleEntity(
                        entity_id=persisted_entity.id,
                        mention_id=mention.id,
                        entity_type=persisted_entity.entity_type,
                        canonical_name=persisted_entity.canonical_name,
                        normalized_value=persisted_entity.normalized_value,
                        description=persisted_entity.description,
                        surface_text=mention.surface_text,
                        quote_text=entity["quote_text"],
                        source_label=entity["source_label"],
                        source_reference_id=source_reference.id,
                        document_id=entity["chunk"].document_id,
                        chunk_id=entity["chunk"].id,
                    )
                )

        if failed_batch_count == len(batches):
            detail = "; ".join(unsupported_items[:3])
            message = f"All entity extraction batches failed: {detail}" if detail else "All entity extraction batches failed"
            finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=message)
            raise AnalysisModuleError(message)

        validation_status = "passed"
        if failed_batch_count > 0 or unsupported_items or not response_entities:
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
                "created_or_linked_entity_mention_count": len(response_entities),
                "duplicate_skipped_count": duplicate_skipped_count,
                "unsupported_count": len(unsupported_items),
            },
        )
        return AnalysisModuleRunResponse(
            analysis_run_id=run.id,
            module_key="extract_entities",
            model=settings.llm_chat_model,
            claims=[],
            events=[],
            entities=response_entities,
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


def _entity_dedup_key(entity: dict[str, Any]) -> tuple[UUID, str, str, str, str, str]:
    return (
        entity["chunk"].id,
        _normalize_for_dedup(entity["quote_text"]),
        _normalize_for_dedup(entity["entity_type"]),
        _normalize_for_dedup(entity["canonical_name"]),
        _normalize_for_dedup(entity["normalized_value"] or ""),
        _normalize_for_dedup(entity["surface_text"]),
    )


def _normalize_for_dedup(value: str) -> str:
    return " ".join(value.casefold().split())


def build_extract_entities_user_prompt(
    query: str | None,
    retrieved_chunks: list[RetrievedChunk],
    batch_index: int = 1,
    batch_count: int = 1,
) -> str:
    focus_text = query.strip() if isinstance(query, str) and query.strip() else "Nincs kulon fokusz; a megadott forraschunkok entitasjeloltjeit kell kinyerni."
    return (
        f"QUERY:\n{focus_text}\n\n"
        f"BATCH:\n{batch_index}/{batch_count}\n\n"
        f"SOURCE:\n{build_source_blocks(retrieved_chunks)}\n\n"
        "FELADAT:\n"
        "Nyerd ki a QUERY szempontjabol relevans, forrassal alatamasztott entitasjelolteket. "
        "Ha nincs kulon fokusz, a batch forraschunkjaiban szereplo lenyeges, ellenorizheto entitasjelolteket nyerd ki. "
        "Legfeljebb 5 entities elemet adj vissza ebbol a batchbol, entitasonkent egy mentionnel. "
        "Az idezetek legyenek rovidek, pontosak, es teljes egeszukben szerepeljenek a megadott SOURCE chunkban. "
        "Keruld a dupla idezojelet tartalmazo idezeteket; ha megis kell ilyen karakter, ervenyes JSON modon escape-eld."
    )


def validate_extracted_entities(
    payload: dict[str, Any],
    retrieved_chunks: list[RetrievedChunk],
) -> tuple[list[dict[str, Any]], list[str]]:
    entities_value = payload.get("entities", [])
    unsupported_value = payload.get("unsupported_entities", [])
    if not isinstance(entities_value, list) or not isinstance(unsupported_value, list):
        raise AnalysisModuleError("LLM JSON has invalid entities or unsupported_entities fields")

    chunks_by_label = {retrieved.label: retrieved for retrieved in retrieved_chunks}
    valid_entities: list[dict[str, Any]] = []
    for item in entities_value:
        if not isinstance(item, dict):
            continue
        entity_type = item.get("entity_type", "other")
        canonical_name = item.get("canonical_name")
        normalized_value = item.get("normalized_value")
        description = item.get("description")
        mentions = item.get("mentions", [])
        if entity_type not in SUPPORTED_ENTITY_TYPES:
            entity_type = "other"
        if not isinstance(canonical_name, str) or canonical_name.strip() == "" or not isinstance(mentions, list) or not mentions:
            continue
        mention = mentions[0]
        if not isinstance(mention, dict):
            continue
        surface_text = mention.get("surface_text")
        quote_text = mention.get("quote_text")
        source_label = mention.get("source_label")
        if not isinstance(surface_text, str) or not isinstance(quote_text, str) or not isinstance(source_label, str):
            continue
        if surface_text.strip() == "" or quote_text.strip() == "":
            continue
        retrieved = chunks_by_label.get(source_label)
        if retrieved is None or quote_text not in retrieved.chunk.chunk_text:
            continue
        valid_entities.append(
            {
                "entity_type": entity_type,
                "canonical_name": canonical_name,
                "normalized_value": normalized_value if isinstance(normalized_value, str) else None,
                "description": description if isinstance(description, str) else None,
                "surface_text": surface_text,
                "quote_text": quote_text,
                "source_label": source_label,
                "chunk": retrieved.chunk,
                "document_name": retrieved.document_name,
            }
        )

    unsupported_items = [item for item in unsupported_value if isinstance(item, str)]
    return valid_entities[:5], unsupported_items
