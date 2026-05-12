from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.claim import ClaimModel, ClaimSourceModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.analysis_modules import AnalysisModuleContradictionCandidate, AnalysisModuleRunRequest, AnalysisModuleRunResponse
from app.schemas.contradiction import ContradictionSourceCreate
from app.services.analysis_module_common import AnalysisModuleError, parse_llm_json_object
from app.services.analysis_runs import add_analysis_run_input, add_analysis_run_output, finish_analysis_run, start_analysis_run
from app.services.contradictions import create_contradiction_candidate
from app.services.llm import LLMChatMessage, LMStudioNativeProvider


SUPPORTED_CONTRADICTION_TYPES = {
    "time_conflict",
    "location_conflict",
    "identity_conflict",
    "document_mismatch",
    "amount_conflict",
    "other",
}

EXTRACT_CONTRADICTIONS_SYSTEM_PROMPT = """Te egy forrashu ellentmondasjelolt-azonosito komponens vagy.
Csak a megadott CLAIM objektumokbol es azok forrasidezeteibol dolgozhatsz.
Nem hasznalhatsz kulso tudast es nem egeszitheted ki a hianyzo tenyeket.
Csak ellenorizendo contradiction_candidates elemeket adhatsz vissza.
Nem allithatod, hogy az ellentmondas bizonyitott, lenyeges vagy jogilag relevans.
Nem donthetsz bunossegrol, jogi minositesrol, kockazatrol vagy szemelyi felelossegrol.
Valaszolj kizarolag ervenyes JSON objektummal.
Minden jelolthez kotelezo a claim_label_a es claim_label_b.
Csak akkor adj jeloltet, ha ket forrasolt claim kozott konkretan osszevetheto elteres latszik.
Ha nincs eleg forras vagy nincs osszevetheto par, ne tedd contradiction_candidates koze; tedd az unsupported_contradiction_candidates listaba.
Elvart JSON alak:
{"contradiction_candidates":[{"contradiction_type":"time_conflict","title":"...","description":"...","claim_label_a":"claim_1","claim_label_b":"claim_2","severity_hint":"medium","confidence":"low"}],"unsupported_contradiction_candidates":["..."]}
"""


@dataclass(frozen=True)
class RetrievedClaim:
    label: str
    claim: ClaimModel
    source_reference: SourceReferenceModel


def run_detect_contradiction_candidates(
    db: Session,
    case_id: UUID,
    payload: AnalysisModuleRunRequest,
) -> AnalysisModuleRunResponse:
    settings = get_settings()
    run = start_analysis_run(
        db,
        case_id,
        "detect_contradictions",
        provider_type="lm_studio_native",
        model_name=settings.llm_chat_model,
        input_parameters={"query": payload.query, "limit": payload.limit},
        prompt_template_name="detect_contradiction_candidates_v1",
        prompt_template_version="1",
        output_schema_name="detect_contradiction_candidates",
        output_schema_version="1",
        retrieval_strategy="claim_sources_v1",
    )
    try:
        add_analysis_run_input(db, run.id, "query_text", 0, payload_json={"query": payload.query})
        retrieved_claims = retrieve_claims_for_contradiction_detection(db, case_id, payload.limit)
        if len(retrieved_claims) < 2:
            finish_analysis_run(
                db,
                run,
                status="failed",
                validation_status="failed",
                error_message="At least two source-cited claims are required",
            )
            raise AnalysisModuleError("At least two source-cited claims are required")

        for index, retrieved in enumerate(retrieved_claims, start=1):
            add_analysis_run_input(
                db,
                run.id,
                "claim",
                index,
                related_object_type="claim",
                related_object_id=retrieved.claim.id,
                payload_json={
                    "claim_label": retrieved.label,
                    "source_reference_id": str(retrieved.source_reference.id),
                },
            )

        completion = LMStudioNativeProvider(settings).chat_completion(
            settings.llm_chat_model,
            [
                LLMChatMessage(role="system", content=EXTRACT_CONTRADICTIONS_SYSTEM_PROMPT),
                LLMChatMessage(role="user", content=build_detect_contradictions_user_prompt(payload.query, retrieved_claims)),
            ],
            temperature=0.1,
            max_tokens=1600,
        )
        parsed = parse_llm_json_object(completion.content)
        valid_candidates, unsupported_items = validate_extracted_contradiction_candidates(parsed, retrieved_claims)

        response_candidates: list[AnalysisModuleContradictionCandidate] = []
        for index, candidate in enumerate(valid_candidates):
            persisted_candidate = create_contradiction_candidate(
                db,
                case_id=case_id,
                contradiction_type=candidate["contradiction_type"],
                title=candidate["title"],
                description=candidate["description"],
                analysis_run_id=run.id,
                claim_id_a=candidate["claim_a"].claim.id,
                claim_id_b=candidate["claim_b"].claim.id,
                sources=[
                    ContradictionSourceCreate(source_reference_id=candidate["claim_a"].source_reference.id, side_label="a"),
                    ContradictionSourceCreate(source_reference_id=candidate["claim_b"].source_reference.id, side_label="b"),
                ],
                confidence=candidate["confidence"],
                severity_hint=candidate["severity_hint"],
            )
            add_analysis_run_output(db, run.id, "contradiction_candidate", persisted_candidate.id, index)
            response_candidates.append(
                AnalysisModuleContradictionCandidate(
                    contradiction_candidate_id=persisted_candidate.id,
                    contradiction_type=persisted_candidate.contradiction_type,
                    title=persisted_candidate.title,
                    description=persisted_candidate.description,
                    claim_id_a=persisted_candidate.claim_id_a,
                    claim_id_b=persisted_candidate.claim_id_b,
                    severity_hint=persisted_candidate.severity_hint,
                    source_reference_ids=[
                        candidate["claim_a"].source_reference.id,
                        candidate["claim_b"].source_reference.id,
                    ],
                )
            )

        validation_status = "passed" if response_candidates or unsupported_items else "warning"
        finish_analysis_run(
            db,
            run,
            status="succeeded",
            validation_status=validation_status,
            output_summary={
                "contradiction_candidate_count": len(response_candidates),
                "unsupported_count": len(unsupported_items),
            },
        )
        return AnalysisModuleRunResponse(
            analysis_run_id=run.id,
            module_key="detect_contradiction_candidates",
            model=settings.llm_chat_model,
            claims=[],
            events=[],
            entities=[],
            summary_items=[],
            contradiction_candidates=response_candidates,
            unsupported_items=unsupported_items,
            selected_chunk_ids=[],
            validation_status=validation_status,
        )
    except Exception as exc:
        if run.status == "running":
            finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=str(exc))
        if isinstance(exc, AnalysisModuleError):
            raise
        raise AnalysisModuleError(str(exc)) from exc


def retrieve_claims_for_contradiction_detection(db: Session, case_id: UUID, limit: int) -> list[RetrievedClaim]:
    rows = db.execute(
        select(ClaimModel, ClaimSourceModel, SourceReferenceModel)
        .join(ClaimSourceModel, ClaimSourceModel.claim_id == ClaimModel.id)
        .join(SourceReferenceModel, SourceReferenceModel.id == ClaimSourceModel.source_reference_id)
        .where(
            ClaimModel.case_id == case_id,
            ClaimModel.source_validation_status == "source_valid",
        )
        .order_by(ClaimModel.created_at.desc(), ClaimSourceModel.relevance_rank.asc())
        .limit(max(limit * 2, 2))
    )
    retrieved: list[RetrievedClaim] = []
    seen_claim_ids: set[UUID] = set()
    for claim, _source_link, source_reference in rows:
        if claim.id in seen_claim_ids:
            continue
        seen_claim_ids.add(claim.id)
        retrieved.append(RetrievedClaim(label=f"claim_{len(retrieved) + 1}", claim=claim, source_reference=source_reference))
        if len(retrieved) >= max(limit, 2):
            break
    return retrieved


def build_detect_contradictions_user_prompt(query: str, retrieved_claims: list[RetrievedClaim]) -> str:
    claim_blocks = []
    for retrieved in retrieved_claims:
        claim_blocks.append(
            f"{retrieved.label}:\n"
            f"claim_id: {retrieved.claim.id}\n"
            f"claim_type: {retrieved.claim.claim_type}\n"
            f"claim_text: {retrieved.claim.claim_text}\n"
            f"source_reference_id: {retrieved.source_reference.id}\n"
            f"quote_text: {retrieved.source_reference.quote_text}"
        )
    return (
        f"QUERY:\n{query}\n\n"
        f"CLAIMS:\n{chr(10).join(claim_blocks)}\n\n"
        "FELADAT:\n"
        "Keress legfeljebb 5 ellenorizendo ellentmondasjeloltet a fenti forrasolt claim parok kozott. "
        "Csak jeloltet adj vissza, vegleges kovetkeztetest ne."
    )


def validate_extracted_contradiction_candidates(
    payload: dict[str, Any],
    retrieved_claims: list[RetrievedClaim],
) -> tuple[list[dict[str, Any]], list[str]]:
    candidates_value = payload.get("contradiction_candidates", [])
    unsupported_value = payload.get("unsupported_contradiction_candidates", [])
    if not isinstance(candidates_value, list) or not isinstance(unsupported_value, list):
        raise AnalysisModuleError("LLM JSON has invalid contradiction_candidates or unsupported_contradiction_candidates fields")

    claims_by_label = {retrieved.label: retrieved for retrieved in retrieved_claims}
    valid_candidates: list[dict[str, Any]] = []
    for item in candidates_value:
        if not isinstance(item, dict):
            continue
        contradiction_type = item.get("contradiction_type", "other")
        title = item.get("title")
        description = item.get("description")
        claim_label_a = item.get("claim_label_a")
        claim_label_b = item.get("claim_label_b")
        severity_hint = item.get("severity_hint")
        confidence = _normalized_confidence(item.get("confidence"))
        if contradiction_type not in SUPPORTED_CONTRADICTION_TYPES:
            contradiction_type = "other"
        if severity_hint not in {"low", "medium", "high"}:
            severity_hint = None
        if not isinstance(title, str) or not isinstance(description, str):
            continue
        if not isinstance(claim_label_a, str) or not isinstance(claim_label_b, str):
            continue
        if title.strip() == "" or description.strip() == "" or claim_label_a == claim_label_b:
            continue
        claim_a = claims_by_label.get(claim_label_a)
        claim_b = claims_by_label.get(claim_label_b)
        if claim_a is None or claim_b is None:
            continue
        valid_candidates.append(
            {
                "contradiction_type": contradiction_type,
                "title": title,
                "description": description,
                "claim_a": claim_a,
                "claim_b": claim_b,
                "severity_hint": severity_hint,
                "confidence": confidence,
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
