from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import AnalysisRunModel
from app.models.missing_item import MissingItemCandidateModel, MissingItemCandidateSourceModel
from app.models.review import HumanReviewModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.missing_item import MissingItemSourceCreate
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.reviews import list_object_reviews, record_object_review, review_status_for_action
from app.services.storage import StoragePaths


class MissingItemCandidateError(ValueError):
    pass


class MissingItemCandidateNotFoundError(MissingItemCandidateError):
    pass


class MissingItemCandidateValidationError(MissingItemCandidateError):
    pass


def list_missing_item_candidates(db: Session, case_id: UUID) -> list[MissingItemCandidateModel]:
    return list(
        db.execute(
            select(MissingItemCandidateModel)
            .where(MissingItemCandidateModel.case_id == case_id)
            .order_by(MissingItemCandidateModel.created_at.desc())
        ).scalars()
    )


def get_missing_item_candidate(db: Session, case_id: UUID, missing_item_candidate_id: UUID) -> MissingItemCandidateModel:
    candidate = db.get(MissingItemCandidateModel, missing_item_candidate_id)
    if candidate is None or candidate.case_id != case_id:
        raise MissingItemCandidateNotFoundError("Missing item candidate not found")
    return candidate


def list_missing_item_candidate_sources(db: Session, missing_item_candidate_id: UUID) -> list[MissingItemCandidateSourceModel]:
    return list(
        db.execute(
            select(MissingItemCandidateSourceModel)
            .where(MissingItemCandidateSourceModel.missing_item_candidate_id == missing_item_candidate_id)
            .order_by(MissingItemCandidateSourceModel.relevance_rank.asc())
        ).scalars()
    )


def list_missing_item_candidate_reviews(db: Session, missing_item_candidate_id: UUID) -> list[HumanReviewModel]:
    return list_object_reviews(db, "missing_item_candidate", missing_item_candidate_id)


def create_missing_item_candidate(
    db: Session,
    *,
    case_id: UUID,
    missing_item_type: str,
    referenced_item_text: str,
    description: str,
    analysis_run_id: UUID,
    sources: list[MissingItemSourceCreate],
    expected_document_type: str | None = None,
    confidence: Decimal | None = None,
) -> MissingItemCandidateModel:
    if referenced_item_text.strip() == "":
        raise MissingItemCandidateValidationError("Referenced item text is required")
    if description.strip() == "":
        raise MissingItemCandidateValidationError("Missing item candidate description is required")
    if len(sources) < 1:
        raise MissingItemCandidateValidationError("At least one source is required")

    run = db.get(AnalysisRunModel, analysis_run_id)
    if run is None or run.case_id != case_id:
        raise MissingItemCandidateValidationError("Analysis run not found for this case")

    source_references = [_get_case_source_reference(db, case_id, source.source_reference_id) for source in sources]

    candidate = MissingItemCandidateModel(
        case_id=case_id,
        missing_item_type=missing_item_type,
        referenced_item_text=referenced_item_text,
        description=description,
        expected_document_type=expected_document_type,
        confidence=confidence,
        created_by_analysis_run_id=analysis_run_id,
        source_validation_status="source_valid",
        review_status="needs_review",
    )
    db.add(candidate)
    db.flush()

    for source, source_reference in zip(sources, source_references, strict=True):
        db.add(
            MissingItemCandidateSourceModel(
                missing_item_candidate_id=candidate.id,
                source_reference_id=source_reference.id,
                relevance_rank=source.relevance_rank,
            )
        )
    db.flush()

    event = AuditEvent(
        event_type="missing_item_candidate_created",
        success=True,
        case_id=str(case_id),
        user_id=str(run.started_by_user_id),
        analysis_run_id=str(analysis_run_id),
        related_object_type="missing_item_candidate",
        related_object_id=str(candidate.id),
        input_summary={"source_reference_ids": [str(source.id) for source in source_references]},
        output_summary={"missing_item_candidate_id": str(candidate.id), "missing_item_type": candidate.missing_item_type},
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(event)
    db.commit()
    db.refresh(candidate)
    return candidate


def review_missing_item_candidate(
    db: Session,
    *,
    case_id: UUID,
    missing_item_candidate_id: UUID,
    action_type: str,
    review_comment: str | None = None,
) -> MissingItemCandidateModel:
    candidate = get_missing_item_candidate(db, case_id, missing_item_candidate_id)
    previous_status = candidate.review_status
    new_status = _review_status_for_action(action_type, previous_status)

    if new_status is not None:
        candidate.review_status = new_status
        candidate.updated_at = datetime.now(UTC)
        db.add(candidate)

    record_object_review(
        db,
        case_id=case_id,
        object_type="missing_item_candidate",
        object_id=candidate.id,
        action_type=action_type,
        previous_status=previous_status,
        new_status=new_status,
        review_comment=review_comment,
        audit_event_type="missing_item_candidate_review_recorded",
    )
    db.commit()
    db.refresh(candidate)
    return candidate


def _get_case_source_reference(db: Session, case_id: UUID, source_reference_id: UUID) -> SourceReferenceModel:
    source_reference = db.get(SourceReferenceModel, source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise MissingItemCandidateValidationError("Source reference not found for this case")
    return source_reference


def _review_status_for_action(action_type: str, previous_status: str) -> str | None:
    return review_status_for_action(action_type, previous_status, MissingItemCandidateValidationError)
