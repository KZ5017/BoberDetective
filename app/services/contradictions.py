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
from app.schemas.contradiction import ContradictionSourceCreate
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.reviews import list_object_reviews, record_object_review, review_status_for_action
from app.services.storage import StoragePaths


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


def _get_case_event(db: Session, case_id: UUID, event_id: UUID) -> EventModel:
    event = db.get(EventModel, event_id)
    if event is None or event.case_id != case_id:
        raise ContradictionCandidateValidationError("Event not found for this case")
    return event


def _get_case_source_reference(db: Session, case_id: UUID, source_reference_id: UUID) -> SourceReferenceModel:
    source_reference = db.get(SourceReferenceModel, source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise ContradictionCandidateValidationError("Source reference not found for this case")
    return source_reference


def _review_status_for_action(action_type: str, previous_status: str) -> str | None:
    return review_status_for_action(action_type, previous_status, ContradictionCandidateValidationError)
