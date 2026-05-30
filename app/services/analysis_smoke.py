from typing import Any
from uuid import UUID
import json
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import DocumentChunkModel
from app.schemas.analysis_smoke import SmokeClaim, SourceCitedAnalysisSmokeRequest, SourceCitedAnalysisSmokeResponse
from app.schemas.search import KeywordSearchRequest, SearchFilters
from app.schemas.source_reference import SourceReferenceCreate
from app.services.analysis_runs import (
    add_analysis_run_input,
    add_analysis_run_output,
    finish_analysis_run,
    start_analysis_run,
)
from app.services.claims import create_claim_with_source
from app.services.llm import LLMChatMessage, LMStudioNativeProvider
from app.services.search import keyword_search
from app.services.source_references import create_source_reference_for_run
from app.services.text_store import read_chunk_text_from_store


SMOKE_PROMPT_TEMPLATE_NAME = "source_cited_smoke"
SMOKE_PROMPT_TEMPLATE_VERSION = "1"
SMOKE_OUTPUT_SCHEMA_NAME = "source_cited_smoke_claims"
SMOKE_OUTPUT_SCHEMA_VERSION = "1"

SMOKE_SYSTEM_PROMPT = """You are a source-faithful document analysis component.
You are analyzing Hungarian source text.
You may rely only on the provided SOURCE text.
Do not infer and do not fill in missing facts.
Return only a valid JSON object.
Return claim_text and unsupported_claims in Hungarian.
Every claims item must include quote_text, and quote_text must appear literally in the SOURCE text.
Copy quote_text character-exactly from the SOURCE text: do not translate, fix, add accents, or normalize it.
If there is not enough source support for a claim, do not put it into claims; put it into unsupported_claims.
Expected JSON shape:
{"claims":[{"claim_text":"...","quote_text":"...","source_label":"chunk_1"}],"unsupported_claims":["..."]}
"""


class SourceCitedAnalysisSmokeError(ValueError):
    pass


def run_source_cited_analysis_smoke(
    db: Session,
    case_id: UUID,
    payload: SourceCitedAnalysisSmokeRequest,
) -> SourceCitedAnalysisSmokeResponse:
    settings = get_settings()
    run = start_analysis_run(
        db,
        case_id,
        "answer_with_citations",
        provider_type="lm_studio_native",
        model_name=settings.llm_chat_model,
        input_parameters={"query": payload.query, "limit": payload.limit},
        prompt_template_name=SMOKE_PROMPT_TEMPLATE_NAME,
        prompt_template_version=SMOKE_PROMPT_TEMPLATE_VERSION,
        output_schema_name=SMOKE_OUTPUT_SCHEMA_NAME,
        output_schema_version=SMOKE_OUTPUT_SCHEMA_VERSION,
        retrieval_strategy="keyword_chunks_v1",
    )
    try:
        add_analysis_run_input(db, run.id, "query_text", 0, payload_json={"query": payload.query})
        hits = keyword_search(
            db,
            case_id,
            KeywordSearchRequest(
                query=payload.query,
                filters=SearchFilters(),
                limit=payload.limit,
                include_quotes=True,
                target="chunks",
            ),
        )
        chunk_hit = next((hit for hit in hits if hit.chunk_id is not None), None)
        if chunk_hit is None:
            finish_analysis_run(
                db,
                run,
                status="failed",
                validation_status="failed",
                error_message="No chunk retrieval hit for query",
            )
            raise SourceCitedAnalysisSmokeError("No chunk retrieval hit for query")

        chunk = db.get(DocumentChunkModel, chunk_hit.chunk_id)
        if chunk is None:
            finish_analysis_run(
                db,
                run,
                status="failed",
                validation_status="failed",
                error_message="Retrieved chunk not found",
            )
            raise SourceCitedAnalysisSmokeError("Retrieved chunk not found")

        add_analysis_run_input(
            db,
            run.id,
            "chunk",
            1,
            document_id=chunk.document_id,
            chunk_id=chunk.id,
            payload_json={"retrieval_score": chunk_hit.score},
        )

        chunk_text = read_chunk_text_from_store(db, chunk)
        completion = LMStudioNativeProvider(settings).chat_completion(
            settings.llm_chat_model,
            [
                LLMChatMessage(role="system", content=SMOKE_SYSTEM_PROMPT),
                LLMChatMessage(role="user", content=_build_user_prompt(payload.query, chunk_text)),
            ],
            temperature=0.1,
            max_tokens=1200,
        )
        parsed = _parse_smoke_json(completion.content)
        valid_claims, unsupported_claims = _validate_claims(parsed, chunk_text)

        response_claims: list[SmokeClaim] = []
        for index, claim in enumerate(valid_claims):
            source_reference = create_source_reference_for_run(
                db,
                case_id,
                SourceReferenceCreate(
                    document_id=chunk.document_id,
                    chunk_id=chunk.id,
                    quote_text=claim["quote_text"],
                    source_kind="chunk_quote",
                    citation_label=f"{chunk_hit.document_name}, chunk {chunk.chunk_index}",
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
            )
            add_analysis_run_output(db, run.id, "claim", persisted_claim.id, index)
            response_claims.append(
                SmokeClaim(
                    claim_id=persisted_claim.id,
                    claim_text=claim["claim_text"],
                    quote_text=claim["quote_text"],
                    source_label=claim.get("source_label", "chunk_1"),
                    source_reference_id=source_reference.id,
                )
            )

        validation_status = "passed" if response_claims or unsupported_claims else "warning"
        finish_analysis_run(
            db,
            run,
            status="succeeded",
            validation_status=validation_status,
            output_summary={"claim_count": len(response_claims), "unsupported_count": len(unsupported_claims)},
        )
        return SourceCitedAnalysisSmokeResponse(
            analysis_run_id=run.id,
            model=settings.llm_chat_model,
            claims=response_claims,
            unsupported_claims=unsupported_claims,
            selected_document_id=chunk.document_id,
            selected_chunk_id=chunk.id,
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
        if isinstance(exc, SourceCitedAnalysisSmokeError):
            raise
        raise SourceCitedAnalysisSmokeError(str(exc)) from exc


def _build_user_prompt(query: str, chunk_text: str) -> str:
    return f"QUERY:\n{query}\n\nSOURCE:\nchunk_1:\n{chunk_text}\n\nTASK:\nReturn at most one source-supported claim based on the QUERY."


def _parse_smoke_json(raw_content: str) -> dict[str, Any]:
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SourceCitedAnalysisSmokeError("LLM returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise SourceCitedAnalysisSmokeError("LLM returned a non-object JSON value")
    return payload


def _validate_claims(payload: dict[str, Any], source_text: str) -> tuple[list[dict[str, str]], list[str]]:
    claims_value = payload.get("claims", [])
    unsupported_value = payload.get("unsupported_claims", [])
    if not isinstance(claims_value, list) or not isinstance(unsupported_value, list):
        raise SourceCitedAnalysisSmokeError("LLM JSON has invalid claims or unsupported_claims fields")

    valid_claims: list[dict[str, str]] = []
    for item in claims_value:
        if not isinstance(item, dict):
            continue
        claim_text = item.get("claim_text")
        quote_text = item.get("quote_text")
        source_label = item.get("source_label", "chunk_1")
        if not isinstance(claim_text, str) or not isinstance(quote_text, str) or not isinstance(source_label, str):
            continue
        if quote_text in source_text:
            valid_claims.append({"claim_text": claim_text, "quote_text": quote_text, "source_label": source_label})

    unsupported_claims = [str(item) for item in unsupported_value if isinstance(item, str)]
    return valid_claims[:1], unsupported_claims
