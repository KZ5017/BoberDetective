from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.analysis_modules import AnalysisModuleClaim, AnalysisModuleRunRequest, AnalysisModuleRunResponse
from app.schemas.source_reference import SourceReferenceCreate
from app.services.analysis_module_common import (
    AnalysisModuleError,
    RetrievedChunk,
    add_retrieved_chunk_inputs,
    build_source_blocks,
    parse_llm_json_object,
    retrieve_chunks,
)
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


def run_extract_claims(db: Session, case_id: UUID, payload: AnalysisModuleRunRequest) -> AnalysisModuleRunResponse:
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
        retrieved_chunks = retrieve_chunks(db, case_id, payload)
        if not retrieved_chunks:
            finish_analysis_run(db, run, status="failed", validation_status="failed", error_message="No chunk retrieval hit for query")
            raise AnalysisModuleError("No chunk retrieval hit for query")

        add_retrieved_chunk_inputs(db, run.id, retrieved_chunks)
        completion = LMStudioNativeProvider(settings).chat_completion(
            settings.llm_chat_model,
            [
                LLMChatMessage(role="system", content=EXTRACT_CLAIMS_SYSTEM_PROMPT),
                LLMChatMessage(role="user", content=build_extract_claims_user_prompt(payload.query, retrieved_chunks)),
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


def build_extract_claims_user_prompt(query: str, retrieved_chunks: list[RetrievedChunk]) -> str:
    return (
        f"QUERY:\n{query}\n\n"
        f"SOURCE:\n{build_source_blocks(retrieved_chunks)}\n\n"
        "FELADAT:\n"
        "Nyerd ki a QUERY szempontjabol relevans, forrassal alatamasztott allitasokat. "
        "Legfeljebb 5 claims elemet adj vissza."
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
