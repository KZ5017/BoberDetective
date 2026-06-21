from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import AnalysisRunModel
from app.models.claim import ClaimModel
from app.models.contradiction import ContradictionCandidateModel, ContradictionCandidateSourceModel
from app.models.event import EventModel
from app.models.review import HumanReviewModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.contradiction import ContradictionSourceCreate, ManualContradictionCandidateCreate
from app.services.analysis_deduplication import find_duplicate_contradiction_candidate
from app.services.analysis_runs import add_analysis_run_input, add_analysis_run_output, finish_analysis_run, start_analysis_run
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.claims import list_claim_sources
from app.services.reviews import list_object_reviews, record_object_review, review_status_for_action
from app.services.source_references import ensure_source_reference_document_is_active
from app.services.storage import StoragePaths
from app.services.users import get_or_create_dev_user


class ContradictionCandidateError(ValueError):
    pass


class ContradictionCandidateNotFoundError(ContradictionCandidateError):
    pass


class ContradictionCandidateValidationError(ContradictionCandidateError):
    pass


def list_contradiction_candidates(db: Session, case_id: UUID) -> list[ContradictionCandidateModel]:
    return list(
        db.execute(
            select(ContradictionCandidateModel)
            .where(ContradictionCandidateModel.case_id == case_id)
            .order_by(ContradictionCandidateModel.created_at.desc())
        ).scalars()
    )


def get_contradiction_candidate(db: Session, case_id: UUID, contradiction_candidate_id: UUID) -> ContradictionCandidateModel:
    candidate = db.get(ContradictionCandidateModel, contradiction_candidate_id)
    if candidate is None or candidate.case_id != case_id:
        raise ContradictionCandidateNotFoundError("Contradiction candidate not found")
    return candidate


def list_contradiction_candidate_sources(db: Session, contradiction_candidate_id: UUID) -> list[ContradictionCandidateSourceModel]:
    return list(
        db.execute(
            select(ContradictionCandidateSourceModel)
            .where(ContradictionCandidateSourceModel.contradiction_candidate_id == contradiction_candidate_id)
            .order_by(ContradictionCandidateSourceModel.side_label.asc().nullslast())
        ).scalars()
    )


def list_contradiction_candidate_reviews(db: Session, contradiction_candidate_id: UUID) -> list[HumanReviewModel]:
    return list_object_reviews(db, "contradiction_candidate", contradiction_candidate_id)


def create_contradiction_candidate(
    db: Session,
    *,
    case_id: UUID,
    contradiction_type: str,
    title: str,
    description: str,
    analysis_run_id: UUID,
    sources: list[ContradictionSourceCreate],
    claim_id_a: UUID | None = None,
    claim_id_b: UUID | None = None,
    event_id_a: UUID | None = None,
    event_id_b: UUID | None = None,
    confidence: Decimal | None = None,
    severity_hint: str | None = None,
) -> ContradictionCandidateModel:
    if title.strip() == "":
        raise ContradictionCandidateValidationError("Contradiction candidate title is required")
    if description.strip() == "":
        raise ContradictionCandidateValidationError("Contradiction candidate description is required")
    if len(sources) < 2:
        raise ContradictionCandidateValidationError("At least two sources are required")

    run = db.get(AnalysisRunModel, analysis_run_id)
    if run is None or run.case_id != case_id:
        raise ContradictionCandidateValidationError("Analysis run not found for this case")

    _validate_claim_or_event_pair(db, case_id, claim_id_a, claim_id_b, event_id_a, event_id_b)
    source_references = [_get_case_source_reference(db, case_id, source.source_reference_id) for source in sources]

    candidate = ContradictionCandidateModel(
        case_id=case_id,
        contradiction_type=contradiction_type,
        title=title,
        description=description,
        claim_id_a=claim_id_a,
        claim_id_b=claim_id_b,
        event_id_a=event_id_a,
        event_id_b=event_id_b,
        confidence=confidence,
        severity_hint=severity_hint,
        created_by_analysis_run_id=analysis_run_id,
        source_validation_status="source_valid",
        review_status="needs_review",
    )
    db.add(candidate)
    db.flush()

    for source, source_reference in zip(sources, source_references, strict=True):
        db.add(
            ContradictionCandidateSourceModel(
                contradiction_candidate_id=candidate.id,
                source_reference_id=source_reference.id,
                side_label=source.side_label,
            )
        )
    db.flush()

    event = AuditEvent(
        event_type="contradiction_candidate_created",
        success=True,
        case_id=str(case_id),
        user_id=str(run.started_by_user_id),
        analysis_run_id=str(analysis_run_id),
        related_object_type="contradiction_candidate",
        related_object_id=str(candidate.id),
        input_summary={"source_reference_ids": [str(source.id) for source in source_references]},
        output_summary={"contradiction_candidate_id": str(candidate.id), "contradiction_type": candidate.contradiction_type},
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(event)
    db.commit()
    db.refresh(candidate)
    return candidate


def create_manual_contradiction_candidate(
    db: Session,
    *,
    case_id: UUID,
    payload: ManualContradictionCandidateCreate,
) -> ContradictionCandidateModel:
    description = payload.description.strip()
    if description == "":
        raise ContradictionCandidateValidationError("Contradiction candidate description is required")
    if payload.claim_id_a == payload.claim_id_b:
        raise ContradictionCandidateValidationError("Two different claims are required")

    claim_a = _get_manual_contradiction_claim(db, case_id, payload.claim_id_a)
    claim_b = _get_manual_contradiction_claim(db, case_id, payload.claim_id_b)
    sources_a = list_claim_sources(db, claim_a.id)
    sources_b = list_claim_sources(db, claim_b.id)
    if not sources_a or not sources_b:
        raise ContradictionCandidateValidationError("Both claims must have at least one source")

    existing_candidate = find_duplicate_contradiction_candidate(
        db,
        case_id=case_id,
        contradiction_type=payload.contradiction_type,
        claim_id_a=claim_a.id,
        claim_id_b=claim_b.id,
    )
    if existing_candidate is not None:
        raise ContradictionCandidateValidationError("Contradiction candidate already exists for this claim pair and type")

    run = start_analysis_run(
        db,
        case_id,
        "manual_entry",
        provider_type="human",
        model_name=None,
        input_parameters={
            "object_type": "contradiction_candidate",
            "claim_id_a": str(claim_a.id),
            "claim_id_b": str(claim_b.id),
            "contradiction_type": payload.contradiction_type,
        },
        output_schema_name="manual_contradiction_candidate",
        output_schema_version="v1",
        retrieval_strategy="user_selected_claim_pair",
    )
    try:
        add_analysis_run_input(
            db,
            run.id,
            "claim",
            0,
            related_object_type="claim",
            related_object_id=claim_a.id,
            payload_json={
                "input_kind": "manual_claim_pair_selection",
                "claim_text": claim_a.claim_text,
                "source_validation_status": claim_a.source_validation_status,
                "review_status": claim_a.review_status,
            },
        )
        add_analysis_run_input(
            db,
            run.id,
            "claim",
            1,
            related_object_type="claim",
            related_object_id=claim_b.id,
            payload_json={
                "input_kind": "manual_claim_pair_selection",
                "claim_text": claim_b.claim_text,
                "source_validation_status": claim_b.source_validation_status,
                "review_status": claim_b.review_status,
            },
        )
        candidate = create_contradiction_candidate(
            db,
            case_id=case_id,
            contradiction_type=payload.contradiction_type,
            title=_manual_contradiction_title(payload.contradiction_type),
            description=description,
            analysis_run_id=run.id,
            sources=[
                *[
                    ContradictionSourceCreate(source_reference_id=source.source_reference_id, side_label="a")
                    for source in sources_a
                ],
                *[
                    ContradictionSourceCreate(source_reference_id=source.source_reference_id, side_label="b")
                    for source in sources_b
                ],
            ],
            claim_id_a=claim_a.id,
            claim_id_b=claim_b.id,
            severity_hint=payload.severity_hint,
        )
        add_analysis_run_output(db, run.id, "contradiction_candidate", candidate.id, 0)
        finish_analysis_run(
            db,
            run,
            status="succeeded",
            validation_status="passed",
            output_summary={"object_type": "contradiction_candidate", "object_id": str(candidate.id)},
        )
        return candidate
    except Exception as exc:
        finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=str(exc))
        raise


def review_contradiction_candidate(
    db: Session,
    *,
    case_id: UUID,
    contradiction_candidate_id: UUID,
    action_type: str,
    review_comment: str | None = None,
) -> ContradictionCandidateModel:
    candidate = get_contradiction_candidate(db, case_id, contradiction_candidate_id)
    previous_status = candidate.review_status
    new_status = _review_status_for_action(action_type, previous_status)

    if new_status is not None:
        candidate.review_status = new_status
        candidate.updated_at = datetime.now(UTC)
        db.add(candidate)

    record_object_review(
        db,
        case_id=case_id,
        object_type="contradiction_candidate",
        object_id=candidate.id,
        action_type=action_type,
        previous_status=previous_status,
        new_status=new_status,
        review_comment=review_comment,
        audit_event_type="contradiction_candidate_review_recorded",
    )
    db.commit()
    db.refresh(candidate)
    return candidate


def detach_contradiction_candidate_claim(
    db: Session,
    *,
    case_id: UUID,
    contradiction_candidate_id: UUID,
    side: str,
    review_comment: str | None = None,
) -> ContradictionCandidateModel:
    if side not in {"a", "b"}:
        raise ContradictionCandidateValidationError("Contradiction candidate claim side must be 'a' or 'b'")

    candidate = get_contradiction_candidate(db, case_id, contradiction_candidate_id)
    field_name = "claim_id_a" if side == "a" else "claim_id_b"
    previous_claim_id = getattr(candidate, field_name)
    if previous_claim_id is None:
        raise ContradictionCandidateValidationError("Selected contradiction candidate claim side is already detached")

    previous_status = candidate.review_status
    setattr(candidate, field_name, None)
    candidate.review_status = "corrected"
    candidate.updated_at = datetime.now(UTC)
    db.add(candidate)
    db.flush()

    _record_contradiction_candidate_claim_detach(
        db,
        case_id=case_id,
        candidate=candidate,
        side=side,
        previous_claim_id=previous_claim_id,
        previous_status=previous_status,
        review_comment=review_comment,
    )
    db.commit()
    db.refresh(candidate)
    return candidate


def _validate_claim_or_event_pair(
    db: Session,
    case_id: UUID,
    claim_id_a: UUID | None,
    claim_id_b: UUID | None,
    event_id_a: UUID | None,
    event_id_b: UUID | None,
) -> None:
    has_claim_pair = claim_id_a is not None and claim_id_b is not None
    has_event_pair = event_id_a is not None and event_id_b is not None
    if not has_claim_pair and not has_event_pair:
        raise ContradictionCandidateValidationError("A claim pair or event pair is required")
    if has_claim_pair:
        _get_case_claim(db, case_id, claim_id_a)
        _get_case_claim(db, case_id, claim_id_b)
    if has_event_pair:
        _get_case_event(db, case_id, event_id_a)
        _get_case_event(db, case_id, event_id_b)


def _get_case_claim(db: Session, case_id: UUID, claim_id: UUID) -> ClaimModel:
    claim = db.get(ClaimModel, claim_id)
    if claim is None or claim.case_id != case_id:
        raise ContradictionCandidateValidationError("Claim not found for this case")
    return claim


def _get_manual_contradiction_claim(db: Session, case_id: UUID, claim_id: UUID) -> ClaimModel:
    claim = _get_case_claim(db, case_id, claim_id)
    if claim.source_validation_status != "source_valid":
        raise ContradictionCandidateValidationError("Only source-valid claims can be used")
    if claim.review_status == "rejected":
        raise ContradictionCandidateValidationError("Rejected claims cannot be used")
    return claim


def _get_case_event(db: Session, case_id: UUID, event_id: UUID) -> EventModel:
    event = db.get(EventModel, event_id)
    if event is None or event.case_id != case_id:
        raise ContradictionCandidateValidationError("Event not found for this case")
    return event


def _get_case_source_reference(db: Session, case_id: UUID, source_reference_id: UUID) -> SourceReferenceModel:
    source_reference = db.get(SourceReferenceModel, source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise ContradictionCandidateValidationError("Source reference not found for this case")
    ensure_source_reference_document_is_active(db, case_id, source_reference, ContradictionCandidateValidationError)
    return source_reference


def _review_status_for_action(action_type: str, previous_status: str) -> str | None:
    return review_status_for_action(action_type, previous_status, ContradictionCandidateValidationError)


def _manual_contradiction_title(contradiction_type: str) -> str:
    labels = {
        "time_conflict": "Kezi idobeli elteresjelolt",
        "location_conflict": "Kezi helyszinbeli elteresjelolt",
        "identity_conflict": "Kezi azonossagi elteresjelolt",
        "document_mismatch": "Kezi iratbeli elteresjelolt",
        "amount_conflict": "Kezi osszegbeli elteresjelolt",
        "other": "Kezi ellentmondasjelolt",
    }
    return labels.get(contradiction_type, labels["other"])


def _record_contradiction_candidate_claim_detach(
    db: Session,
    *,
    case_id: UUID,
    candidate: ContradictionCandidateModel,
    side: str,
    previous_claim_id: UUID,
    previous_status: str,
    review_comment: str | None,
) -> HumanReviewModel:
    user = get_or_create_dev_user(db)
    review = HumanReviewModel(
        case_id=case_id,
        object_type="contradiction_candidate",
        object_id=candidate.id,
        action_type="correct",
        previous_review_status=previous_status,
        new_review_status="corrected",
        review_comment=review_comment or f"{side.upper()} állítás leválasztva az ellentmondásjelöltről.",
        correction_patch_json={
            "operation": "detach_contradiction_candidate_claim",
            "side": side,
            "previous_claim_id": str(previous_claim_id),
            "source_validation_status": candidate.source_validation_status,
        },
        performed_by_user_id=user.id,
    )
    db.add(review)
    db.flush()

    audit_event = AuditEvent(
        event_type="contradiction_candidate_claim_detached",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="contradiction_candidate",
        related_object_id=str(candidate.id),
        input_summary={
            "side": side,
            "previous_claim_id": str(previous_claim_id),
            "previous_review_status": previous_status,
            "source_validation_status": candidate.source_validation_status,
        },
        output_summary={
            "new_review_status": candidate.review_status,
            "human_review_id": str(review.id),
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    return review
