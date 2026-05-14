from dataclasses import dataclass
from decimal import Decimal
import re
from typing import Any
import unicodedata
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
SUPPORTED_CONFLICT_BASES = {
    "time",
    "location",
    "identity",
    "amount",
    "document_metadata",
    "mutually_exclusive_fact",
}

MAX_RETRIEVED_CLAIMS_FOR_CONTRADICTION = 40
MAX_CLAIM_PAIRS_FOR_CONTRADICTION = 10
MIN_CLAIMS_FOR_CONTRADICTION = 2
CLAIM_REVIEW_SCOPE_STATUSES = {
    "reviewable": ("new", "needs_review", "verified", "corrected"),
    "verified": ("verified",),
    "needs_review": ("needs_review",),
    "all_source_valid": ("new", "needs_review", "verified", "rejected", "corrected"),
}
CONTRADICTION_FOCUS_STOPWORDS = {
    "keres",
    "keress",
    "talalj",
    "ellentmondas",
    "ellentmondasok",
    "ellentmondasokat",
    "ellentmondasjelolt",
    "ellentmondasjeloltek",
    "claim",
    "claimet",
    "claimok",
    "forras",
    "forrasok",
    "kozott",
}

EXTRACT_CONTRADICTIONS_SYSTEM_PROMPT = """Te egy forrashu ellentmondasjelolt-azonosito komponens vagy.
Csak a megadott CLAIM objektumokbol es azok forrasidezeteibol dolgozhatsz.
Nem hasznalhatsz kulso tudast es nem egeszitheted ki a hianyzo tenyeket.
Csak szigoruan ellenorizendo contradiction_candidates elemeket adhatsz vissza.
Nem allithatod, hogy az ellentmondas bizonyitott, lenyeges vagy jogilag relevans.
Nem donthetsz bunossegrol, jogi minositesrol, kockazatrol vagy szemelyi felelossegrol.
Valaszolj kizarolag ervenyes JSON objektummal.
Ne irj magyarazatot, bevezetest, markdownot vagy kodblokkot a JSON ele vagy utan.
A JSON stringekben minden belso dupla idezojelet kotelezo backslash karakterrel escape-elni.
Rovid, altalanos title es description ertekeket adj; ne masolj hosszu claim szoveget es ne hasznalj idezojeleket.
Minden jelolthez kotelezo a claim_label_a es claim_label_b.
Csak a megadott CLAIM_PAIR blokkokban szereplo claim parokat vetheted ossze.
Csak akkor adj jeloltet, ha egy megadott claim paron belul konkret, egymast kizaro vagy tenyszeruen utkozo allitas latszik.
Az, hogy ket claim ugyanarra a szemelyre, targyra, iratra vagy esemenyre vonatkozik, onmagaban nem ellentmondas.
Kulonbozo kontextus, tovabbi reszlet, idoben kesobbi leiras vagy mas szerep onmagaban nem ellentmondas.
Minden jeloltnel kotelezo: is_contradiction_candidate=true es conflict_basis.
conflict_basis csak ezek egyike lehet: time, location, identity, amount, document_metadata, mutually_exclusive_fact, none.
contradiction_type csak ezek egyike lehet: time_conflict, location_conflict, identity_conflict, document_mismatch, amount_conflict, other.
severity_hint csak ezek egyike lehet: low, medium, high.
severity_hint legyen konzervativ: high csak dokumentumazonossagi vagy egyertelmu irat-osszeferhetetlensegi jeloltnel indokolt.
Ha a par csak osszefuggo, de nem utkozo, ne tedd contradiction_candidates koze; tedd az unsupported_contradiction_candidates listaba rovid indokkal.
Elvart JSON alak:
{"contradiction_candidates":[{"is_contradiction_candidate":true,"conflict_basis":"time","contradiction_type":"time_conflict","title":"Ellenorizendo elteres","description":"A claim par konkretan utkozo teny miatt emberi ellenorzest igenyel","claim_label_a":"claim_1","claim_label_b":"claim_2","severity_hint":"medium","confidence":"low"}],"unsupported_contradiction_candidates":["pair_2: osszefuggo de nem utkozo"]}
"""


@dataclass(frozen=True)
class RetrievedClaim:
    label: str
    claim: ClaimModel
    source_reference: SourceReferenceModel


@dataclass(frozen=True)
class ClaimPair:
    label: str
    claim_a: RetrievedClaim
    claim_b: RetrievedClaim


def run_detect_contradiction_candidates(
    db: Session,
    case_id: UUID,
    payload: AnalysisModuleRunRequest,
) -> AnalysisModuleRunResponse:
    settings = get_settings()
    claim_review_statuses = claim_review_statuses_for_scope(payload.claim_review_scope)
    run = start_analysis_run(
        db,
        case_id,
        "detect_contradictions",
        provider_type="lm_studio_native",
        model_name=settings.llm_chat_model,
        input_parameters={
            "query": payload.query,
            "limit": payload.limit,
            "claim_scope": "case_source_valid_claims",
            "claim_review_scope": payload.claim_review_scope,
            "claim_review_statuses": list(claim_review_statuses),
            "required_min_claim_count": MIN_CLAIMS_FOR_CONTRADICTION,
        },
        prompt_template_name="detect_contradiction_candidates_v1",
        prompt_template_version="1",
        output_schema_name="detect_contradiction_candidates",
        output_schema_version="1",
        retrieval_strategy="claim_sources_v1",
    )
    try:
        add_analysis_run_input(db, run.id, "query_text", 0, payload_json={"query": payload.query})
        claim_fetch_limit = min(
            max(payload.limit * 4, MIN_CLAIMS_FOR_CONTRADICTION * 4),
            MAX_RETRIEVED_CLAIMS_FOR_CONTRADICTION,
        )
        pair_limit = min(max(payload.limit * 2, MIN_CLAIMS_FOR_CONTRADICTION * 2), MAX_CLAIM_PAIRS_FOR_CONTRADICTION)
        retrieved_claims = retrieve_claims_for_contradiction_detection(
            db,
            case_id,
            claim_fetch_limit,
            claim_review_statuses,
        )
        selected_claims, claim_pairs, selection_metadata = select_claim_pairs_for_contradiction_detection(
            retrieved_claims,
            payload.query,
            pair_limit,
        )
        add_analysis_run_input(
            db,
            run.id,
            "filter",
            1,
            payload_json={
                "input_kind": "claim_selection",
                "claim_scope": "case_source_valid_claims",
                "claim_review_scope": payload.claim_review_scope,
                "claim_review_statuses": list(claim_review_statuses),
                "retrieved_claim_count": len(retrieved_claims),
                "selected_claim_count": len(selected_claims),
                "selected_pair_count": len(claim_pairs),
                "required_min_claim_count": MIN_CLAIMS_FOR_CONTRADICTION,
                "limit": payload.limit,
                "claim_fetch_limit": claim_fetch_limit,
                "pair_limit": pair_limit,
                "selected_pairs": [
                    {
                        "pair_label": pair.label,
                        "claim_label_a": pair.claim_a.label,
                        "claim_id_a": str(pair.claim_a.claim.id),
                        "claim_label_b": pair.claim_b.label,
                        "claim_id_b": str(pair.claim_b.claim.id),
                    }
                    for pair in claim_pairs
                ],
                **selection_metadata,
            },
        )
        if len(selected_claims) < MIN_CLAIMS_FOR_CONTRADICTION or not claim_pairs:
            unsupported_items = [_contradiction_precondition_message(retrieved_claims, selected_claims, selection_metadata)]
            finish_analysis_run(
                db,
                run,
                status="succeeded",
                validation_status="warning",
                output_summary={
                    "retrieved_claim_count": len(retrieved_claims),
                    "selected_claim_count": len(selected_claims),
                    "selected_pair_count": len(claim_pairs),
                    "required_min_claim_count": MIN_CLAIMS_FOR_CONTRADICTION,
                    "contradiction_candidate_count": 0,
                    "unsupported_count": len(unsupported_items),
                    **selection_metadata,
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
                contradiction_candidates=[],
                unsupported_items=unsupported_items,
                selected_chunk_ids=[],
                validation_status="warning",
            )

        for index, retrieved in enumerate(selected_claims, start=2):
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
                    "claim_type": retrieved.claim.claim_type,
                    "source_validation_status": retrieved.claim.source_validation_status,
                    "review_status": retrieved.claim.review_status,
                    "claim_pair_labels": [
                        pair.label
                        for pair in claim_pairs
                        if pair.claim_a.label == retrieved.label or pair.claim_b.label == retrieved.label
                    ],
                },
            )

        completion = LMStudioNativeProvider(settings).chat_completion(
            settings.llm_chat_model,
            [
                LLMChatMessage(role="system", content=EXTRACT_CONTRADICTIONS_SYSTEM_PROMPT),
                LLMChatMessage(
                    role="user",
                    content=build_detect_contradictions_user_prompt(payload.query, claim_pairs, payload.limit),
                ),
            ],
            temperature=0.1,
            max_tokens=1600,
        )
        try:
            parsed = parse_llm_json_object(completion.content)
        except AnalysisModuleError as exc:
            unsupported_items = [f"A modell valasza nem volt ervenyes JSON: {exc}"]
            finish_analysis_run(
                db,
                run,
                status="succeeded",
                validation_status="warning",
                output_summary={
                    "retrieved_claim_count": len(retrieved_claims),
                    "selected_claim_count": len(selected_claims),
                    "selected_pair_count": len(claim_pairs),
                    "contradiction_candidate_count": 0,
                    "unsupported_count": len(unsupported_items),
                    "llm_json_error": str(exc),
                    **selection_metadata,
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
                contradiction_candidates=[],
                unsupported_items=unsupported_items,
                selected_chunk_ids=[],
                validation_status="warning",
            )
        valid_candidates, unsupported_items = validate_extracted_contradiction_candidates(
            parsed,
            selected_claims,
            claim_pairs,
            max_candidates=payload.limit,
        )

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
                "retrieved_claim_count": len(retrieved_claims),
                "selected_claim_count": len(selected_claims),
                "selected_pair_count": len(claim_pairs),
                "contradiction_candidate_count": len(response_candidates),
                "unsupported_count": len(unsupported_items),
                **selection_metadata,
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


def retrieve_claims_for_contradiction_detection(
    db: Session,
    case_id: UUID,
    limit: int,
    review_statuses: tuple[str, ...] | None = None,
) -> list[RetrievedClaim]:
    review_status_filter = review_statuses or claim_review_statuses_for_scope("reviewable")
    rows = db.execute(
        select(ClaimModel, ClaimSourceModel, SourceReferenceModel)
        .join(ClaimSourceModel, ClaimSourceModel.claim_id == ClaimModel.id)
        .join(SourceReferenceModel, SourceReferenceModel.id == ClaimSourceModel.source_reference_id)
        .where(
            ClaimModel.case_id == case_id,
            ClaimModel.source_validation_status == "source_valid",
            ClaimModel.review_status.in_(review_status_filter),
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


def claim_review_statuses_for_scope(scope: str) -> tuple[str, ...]:
    return CLAIM_REVIEW_SCOPE_STATUSES.get(scope, CLAIM_REVIEW_SCOPE_STATUSES["reviewable"])


def select_claim_pairs_for_contradiction_detection(
    retrieved_claims: list[RetrievedClaim],
    query: str | None,
    max_pairs: int,
) -> tuple[list[RetrievedClaim], list[ClaimPair], dict[str, Any]]:
    focus_terms = _claim_focus_terms(query)
    matched_claims = [
        retrieved for retrieved in retrieved_claims if focus_terms and _claim_matches_focus(retrieved, focus_terms)
    ]
    candidate_claims = matched_claims if focus_terms else retrieved_claims
    metadata = {
        "focus_filter_applied": bool(focus_terms),
        "focus_terms": focus_terms,
        "focus_matched_claim_count": len(matched_claims) if focus_terms else None,
    }
    if len(candidate_claims) < MIN_CLAIMS_FOR_CONTRADICTION:
        return candidate_claims, [], metadata

    claim_order = {retrieved.label: index for index, retrieved in enumerate(candidate_claims)}
    scored_pairs: list[tuple[int, int, int, RetrievedClaim, RetrievedClaim]] = []
    for left_index, claim_a in enumerate(candidate_claims):
        for right_index, claim_b in enumerate(candidate_claims[left_index + 1 :], start=left_index + 1):
            scored_pairs.append((-_claim_pair_score(claim_a, claim_b), left_index, right_index, claim_a, claim_b))
    scored_pairs.sort(key=lambda item: (item[0], item[1], item[2]))

    claim_pairs: list[ClaimPair] = []
    selected_by_label: dict[str, RetrievedClaim] = {}
    for _score, _left_index, _right_index, claim_a, claim_b in scored_pairs[:max_pairs]:
        claim_pairs.append(ClaimPair(label=f"pair_{len(claim_pairs) + 1}", claim_a=claim_a, claim_b=claim_b))
        selected_by_label.setdefault(claim_a.label, claim_a)
        selected_by_label.setdefault(claim_b.label, claim_b)

    selected_claims = sorted(selected_by_label.values(), key=lambda retrieved: claim_order[retrieved.label])
    return selected_claims, claim_pairs, metadata


def build_detect_contradictions_user_prompt(
    query: str | None,
    claim_pairs: list[ClaimPair],
    max_candidates: int = 5,
) -> str:
    pair_blocks = []
    for pair in claim_pairs:
        pair_blocks.append(
            f"{pair.label}:\n"
            f"claim_label_a: {pair.claim_a.label}\n"
            f"claim_id_a: {pair.claim_a.claim.id}\n"
            f"claim_type_a: {pair.claim_a.claim.claim_type}\n"
            f"claim_text_a: {pair.claim_a.claim.claim_text}\n"
            f"source_reference_id_a: {pair.claim_a.source_reference.id}\n"
            f"quote_text_a: {pair.claim_a.source_reference.quote_text}\n"
            f"claim_label_b: {pair.claim_b.label}\n"
            f"claim_id_b: {pair.claim_b.claim.id}\n"
            f"claim_type_b: {pair.claim_b.claim.claim_type}\n"
            f"claim_text_b: {pair.claim_b.claim.claim_text}\n"
            f"source_reference_id_b: {pair.claim_b.source_reference.id}\n"
            f"quote_text_b: {pair.claim_b.source_reference.quote_text}"
        )
    focus_text = query.strip() if isinstance(query, str) and query.strip() else "Nincs kulon fokusz; a megadott forrasolt claim parok kozott kell ellenorizendo ellentmondasjelolteket keresni."
    return (
        f"QUERY:\n{focus_text}\n\n"
        f"CLAIM_PAIRS:\n{chr(10).join(pair_blocks)}\n\n"
        "FELADAT:\n"
        f"Minositsd a fenti claim parokat, es csak legfeljebb {max_candidates} szigoru ellentmondasjeloltet adj vissza. "
        "Eloszor dontsd el, hogy csak tematikus osszefugges van-e, vagy konkretan utkozo teny. "
        "Csak konkretan utkozo teny eseten hasznalj is_contradiction_candidate=true erteket. "
        "Ha ugyanaz a kozponti szereplo vagy targy csak mas kontextusban szerepel, az unsupported_contradiction_candidates listaba keruljon. "
        "A claim_label_a es claim_label_b erteke csak ugyanabbol a CLAIM_PAIR blokkbol szarmazhat. "
        "Ne allitsd, hogy az ellentmondas bizonyitott; csak azt rogzitsd, hogy a claim par emberi ellenorzest igenyel. "
        "A title es description legyen rovid, idezojelek nelkuli, es ne masoljon claim szoveget. "
        "Keruld a dupla idezojelet tartalmazo szovegeket; ha megis kell ilyen karakter, ervenyes JSON modon escape-eld."
    )


def validate_extracted_contradiction_candidates(
    payload: dict[str, Any],
    retrieved_claims: list[RetrievedClaim],
    allowed_claim_pairs: list[ClaimPair] | None = None,
    max_candidates: int = 5,
) -> tuple[list[dict[str, Any]], list[str]]:
    candidates_value = payload.get("contradiction_candidates", [])
    unsupported_value = payload.get("unsupported_contradiction_candidates", [])
    if not isinstance(candidates_value, list) or not isinstance(unsupported_value, list):
        raise AnalysisModuleError("LLM JSON has invalid contradiction_candidates or unsupported_contradiction_candidates fields")

    claims_by_label = {retrieved.label: retrieved for retrieved in retrieved_claims}
    allowed_pair_labels = None
    if allowed_claim_pairs is not None:
        allowed_pair_labels = {frozenset((pair.claim_a.label, pair.claim_b.label)) for pair in allowed_claim_pairs}
    valid_candidates: list[dict[str, Any]] = []
    seen_candidate_keys: set[tuple[frozenset[str], str]] = set()
    for item in candidates_value:
        if not isinstance(item, dict):
            continue
        contradiction_type = item.get("contradiction_type", "other")
        title = item.get("title")
        description = item.get("description")
        claim_label_a = item.get("claim_label_a")
        claim_label_b = item.get("claim_label_b")
        is_contradiction_candidate = item.get("is_contradiction_candidate")
        conflict_basis = item.get("conflict_basis")
        severity_hint = item.get("severity_hint")
        confidence = _normalized_confidence(item.get("confidence"))
        if is_contradiction_candidate is not True:
            continue
        if not isinstance(conflict_basis, str) or conflict_basis not in SUPPORTED_CONFLICT_BASES:
            continue
        if contradiction_type not in SUPPORTED_CONTRADICTION_TYPES:
            contradiction_type = "other"
        severity_hint = _normalized_severity_hint(severity_hint, contradiction_type)
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
        if allowed_pair_labels is not None and frozenset((claim_label_a, claim_label_b)) not in allowed_pair_labels:
            continue
        candidate_key = (
            frozenset((claim_label_a, claim_label_b)),
            contradiction_type,
        )
        if candidate_key in seen_candidate_keys:
            continue
        seen_candidate_keys.add(candidate_key)
        valid_candidates.append(
            {
                "contradiction_type": contradiction_type,
                "title": _safe_contradiction_title(contradiction_type),
                "description": _safe_contradiction_description(claim_label_a, claim_a, claim_label_b, claim_b),
                "claim_a": claim_a,
                "claim_b": claim_b,
                "severity_hint": severity_hint,
                "confidence": confidence,
            }
        )

    unsupported_items = [item for item in unsupported_value if isinstance(item, str)]
    return valid_candidates[:max_candidates], unsupported_items


def _normalized_severity_hint(value: Any, contradiction_type: str) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized not in {"low", "medium", "high"}:
        return None
    if normalized == "high" and contradiction_type != "document_mismatch":
        return "medium"
    return normalized


def _safe_contradiction_title(contradiction_type: str) -> str:
    labels = {
        "time_conflict": "Ellenorizendo idobeli elteres",
        "location_conflict": "Ellenorizendo helyszini elteres",
        "identity_conflict": "Ellenorizendo szemelyi vagy azonossagi elteres",
        "document_mismatch": "Ellenorizendo iratosszeferhetetlenseg",
        "amount_conflict": "Ellenorizendo osszegbeli elteres",
        "other": "Ellenorizendo allitasok kozotti elteres",
    }
    return labels.get(contradiction_type, labels["other"])


def _safe_contradiction_description(
    claim_label_a: str,
    claim_a: RetrievedClaim,
    claim_label_b: str,
    claim_b: RetrievedClaim,
) -> str:
    claim_text_a = _bounded_inline_text(claim_a.claim.claim_text)
    claim_text_b = _bounded_inline_text(claim_b.claim.claim_text)
    return (
        f"A kivalasztott claim-par emberi ellenorzest igenyel. "
        f"{claim_label_a}: {claim_text_a} "
        f"{claim_label_b}: {claim_text_b} "
        "Ez ellenorizendo jelolt, nem bizonyitott ellentmondas."
    )


def _bounded_inline_text(value: str, max_length: int = 220) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 3].rstrip()}..."


def _normalized_confidence(value: Any) -> Decimal | None:
    if isinstance(value, int | float):
        if 0 <= value <= 1:
            return Decimal(str(value))
        return None
    if isinstance(value, str):
        mapping = {"low": Decimal("0.3000"), "medium": Decimal("0.6000"), "high": Decimal("0.9000")}
        return mapping.get(value.strip().lower())
    return None


def _claim_pair_score(claim_a: RetrievedClaim, claim_b: RetrievedClaim) -> int:
    score = 0
    if claim_a.claim.claim_type == claim_b.claim.claim_type:
        score += 3
    if claim_a.claim.related_event_id is not None and claim_a.claim.related_event_id == claim_b.claim.related_event_id:
        score += 3
    if claim_a.claim.claim_time_raw and claim_b.claim.claim_time_raw:
        score += 2
    if claim_a.source_reference.document_id == claim_b.source_reference.document_id:
        score += 1
    return score


def _claim_focus_terms(query: str | None) -> list[str]:
    if not isinstance(query, str) or not query.strip():
        return []
    normalized = unicodedata.normalize("NFKD", query.casefold())
    ascii_query = "".join(char for char in normalized if not unicodedata.combining(char))
    terms: list[str] = []
    for term in re.findall(r"\w+", ascii_query):
        if len(term) < 4 or term in CONTRADICTION_FOCUS_STOPWORDS:
            continue
        if term not in terms:
            terms.append(term)
    return terms


def _claim_matches_focus(retrieved: RetrievedClaim, focus_terms: list[str]) -> bool:
    haystack = _normalized_text(f"{retrieved.claim.claim_text} {retrieved.source_reference.quote_text}")
    return any(term in haystack for term in focus_terms)


def _normalized_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _contradiction_precondition_message(
    retrieved_claims: list[RetrievedClaim],
    selected_claims: list[RetrievedClaim],
    selection_metadata: dict[str, Any],
) -> str:
    if len(retrieved_claims) < MIN_CLAIMS_FOR_CONTRADICTION:
        return "Legalabb ket source-valid claim szukseges az ellentmondasjeloltek keresesehez."
    if selection_metadata.get("focus_filter_applied"):
        return "A fokuszszures utan legalabb ket source-valid claim szukseges az ellentmondasjeloltek keresesehez."
    if len(selected_claims) < MIN_CLAIMS_FOR_CONTRADICTION:
        return "Nincs eleg kivalasztott source-valid claim az ellentmondasjeloltek keresesehez."
    return "Nincs osszevetheto source-valid claim par az ellentmondasjeloltek keresesehez."
