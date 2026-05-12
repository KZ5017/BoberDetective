from uuid import UUID

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import AnalysisRunModel
from app.models.claim import ClaimModel, ClaimSourceModel
from app.models.review import HumanReviewModel
from app.models.source_reference import SourceReferenceModel
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.reviews import list_object_reviews, record_object_review, review_status_for_action
from app.services.storage import StoragePaths


class ClaimError(ValueError):
    pass


class ClaimNotFoundError(ClaimError):
    pass


class ClaimValidationError(ClaimError):
    pass


def list_claims(db: Session, case_id: UUID) -> list[ClaimModel]:
    return list(
        db.execute(select(ClaimModel).where(ClaimModel.case_id == case_id).order_by(ClaimModel.created_at.desc())).scalars()
    )


def get_claim(db: Session, case_id: UUID, claim_id: UUID) -> ClaimModel:
    claim = db.get(ClaimModel, claim_id)
    if claim is None or claim.case_id != case_id:
        raise ClaimNotFoundError("Claim not found")
    return claim


def list_claim_sources(db: Session, claim_id: UUID) -> list[ClaimSourceModel]:
    return list(
        db.execute(select(ClaimSourceModel).where(ClaimSourceModel.claim_id == claim_id).order_by(ClaimSourceModel.relevance_rank.asc())).scalars()
    )


def list_claim_reviews(db: Session, claim_id: UUID) -> list[HumanReviewModel]:
    return list_object_reviews(db, "claim", claim_id)


def review_claim(
    db: Session,
    *,
    case_id: UUID,
    claim_id: UUID,
    action_type: str,
    review_comment: str | None = None,
) -> ClaimModel:
    claim = get_claim(db, case_id, claim_id)
    previous_status = claim.review_status
    new_status = _review_status_for_action(action_type, previous_status)

    if new_status is not None:
        claim.review_status = new_status
        claim.updated_at = datetime.now(UTC)
        db.add(claim)

    record_object_review(
        db,
        case_id=case_id,
        object_type="claim",
        object_id=claim.id,
        action_type=action_type,
        previous_status=previous_status,
        new_status=new_status,
        review_comment=review_comment,
        audit_event_type="claim_review_recorded",
    )
    db.commit()
    db.refresh(claim)
    return claim


def create_claim_with_source(
    db: Session,
    *,
    case_id: UUID,
    claim_text: str,
    source_reference_id: UUID,
    analysis_run_id: UUID,
    claim_type: str = "document_fact",
    support_type: str = "direct",
    relevance_rank: int = 0,
) -> ClaimModel:
    if claim_text.strip() == "":
        raise ClaimValidationError("Claim text is required")

    run = db.get(AnalysisRunModel, analysis_run_id)
    if run is None or run.case_id != case_id:
        raise ClaimValidationError("Analysis run not found for this case")

    source_reference = db.get(SourceReferenceModel, source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise ClaimValidationError("Source reference not found for this case")

    claim = ClaimModel(
        case_id=case_id,
        claim_type=claim_type,
        claim_text=claim_text,
        created_by_analysis_run_id=analysis_run_id,
        source_validation_status="source_valid",
        review_status="needs_review",
    )
    db.add(claim)
    db.flush()

    db.add(
        ClaimSourceModel(
            claim_id=claim.id,
            source_reference_id=source_reference.id,
            relevance_rank=relevance_rank,
            support_type=support_type,
        )
    )
    db.flush()

    event = AuditEvent(
        event_type="claim_created",
        success=True,
        case_id=str(case_id),
        user_id=str(run.started_by_user_id),
        analysis_run_id=str(analysis_run_id),
        related_object_type="claim",
        related_object_id=str(claim.id),
        related_document_id=str(source_reference.document_id),
        related_page_id=str(source_reference.page_id) if source_reference.page_id is not None else None,
        related_chunk_id=str(source_reference.chunk_id) if source_reference.chunk_id is not None else None,
        input_summary={"source_reference_id": str(source_reference.id)},
        output_summary={"claim_id": str(claim.id), "claim_type": claim.claim_type},
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(event)
    db.commit()
    db.refresh(claim)
    return claim


def _review_status_for_action(action_type: str, previous_status: str) -> str | None:
    return review_status_for_action(action_type, previous_status, ClaimValidationError)
