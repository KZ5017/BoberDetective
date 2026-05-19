from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import AnalysisRunModel
from app.models.review import HumanReviewModel
from app.models.source_reference import SourceReferenceModel
from app.models.summary_item import SummaryItemModel, SummaryItemSourceModel
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.reviews import list_object_reviews, record_object_review, review_status_for_action
from app.services.source_references import ensure_source_reference_document_is_active
from app.services.storage import StoragePaths


class SummaryItemError(ValueError):
    pass


class SummaryItemNotFoundError(SummaryItemError):
    pass


class SummaryItemValidationError(SummaryItemError):
    pass


def list_summary_items(db: Session, case_id: UUID) -> list[SummaryItemModel]:
    return list(
        db.execute(
            select(SummaryItemModel)
            .where(SummaryItemModel.case_id == case_id)
            .order_by(SummaryItemModel.created_at.desc())
        ).scalars()
    )


def get_summary_item(db: Session, case_id: UUID, summary_item_id: UUID) -> SummaryItemModel:
    summary_item = db.get(SummaryItemModel, summary_item_id)
    if summary_item is None or summary_item.case_id != case_id:
        raise SummaryItemNotFoundError("Summary item not found")
    return summary_item


def list_summary_item_sources(db: Session, summary_item_id: UUID) -> list[SummaryItemSourceModel]:
    return list(
        db.execute(
            select(SummaryItemSourceModel)
            .where(SummaryItemSourceModel.summary_item_id == summary_item_id)
            .order_by(SummaryItemSourceModel.relevance_rank.asc())
        ).scalars()
    )


def list_summary_item_reviews(db: Session, summary_item_id: UUID) -> list[HumanReviewModel]:
    return list_object_reviews(db, "summary_item", summary_item_id)


def create_summary_item_with_source(
    db: Session,
    *,
    case_id: UUID,
    summary_type: str,
    title: str,
    body_text: str,
    source_reference_id: UUID,
    analysis_run_id: UUID,
    confidence: Decimal | None = None,
    support_type: str = "direct",
    relevance_rank: int = 0,
) -> SummaryItemModel:
    if title.strip() == "":
        raise SummaryItemValidationError("Summary item title is required")
    if body_text.strip() == "":
        raise SummaryItemValidationError("Summary item body text is required")

    run = db.get(AnalysisRunModel, analysis_run_id)
    if run is None or run.case_id != case_id:
        raise SummaryItemValidationError("Analysis run not found for this case")

    source_reference = db.get(SourceReferenceModel, source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise SummaryItemValidationError("Source reference not found for this case")
    ensure_source_reference_document_is_active(db, case_id, source_reference, SummaryItemValidationError)

    summary_item = SummaryItemModel(
        case_id=case_id,
        summary_type=summary_type,
        title=title,
        body_text=body_text,
        confidence=confidence,
        created_by_analysis_run_id=analysis_run_id,
        source_validation_status="source_valid",
        review_status="needs_review",
    )
    db.add(summary_item)
    db.flush()

    db.add(
        SummaryItemSourceModel(
            summary_item_id=summary_item.id,
            source_reference_id=source_reference.id,
            relevance_rank=relevance_rank,
            support_type=support_type,
        )
    )
    db.flush()

    event = AuditEvent(
        event_type="summary_item_created",
        success=True,
        case_id=str(case_id),
        user_id=str(run.started_by_user_id),
        analysis_run_id=str(analysis_run_id),
        related_object_type="summary_item",
        related_object_id=str(summary_item.id),
        related_document_id=str(source_reference.document_id),
        related_page_id=str(source_reference.page_id) if source_reference.page_id is not None else None,
        related_chunk_id=str(source_reference.chunk_id) if source_reference.chunk_id is not None else None,
        input_summary={"source_reference_id": str(source_reference.id)},
        output_summary={"summary_item_id": str(summary_item.id), "summary_type": summary_item.summary_type},
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(event)
    db.commit()
    db.refresh(summary_item)
    return summary_item


def review_summary_item(
    db: Session,
    *,
    case_id: UUID,
    summary_item_id: UUID,
    action_type: str,
    review_comment: str | None = None,
) -> SummaryItemModel:
    summary_item = get_summary_item(db, case_id, summary_item_id)
    previous_status = summary_item.review_status
    new_status = _review_status_for_action(action_type, previous_status)

    if new_status is not None:
        summary_item.review_status = new_status
        summary_item.updated_at = datetime.now(UTC)
        db.add(summary_item)

    record_object_review(
        db,
        case_id=case_id,
        object_type="summary_item",
        object_id=summary_item.id,
        action_type=action_type,
        previous_status=previous_status,
        new_status=new_status,
        review_comment=review_comment,
        audit_event_type="summary_item_review_recorded",
    )
    db.commit()
    db.refresh(summary_item)
    return summary_item


def _review_status_for_action(action_type: str, previous_status: str) -> str | None:
    return review_status_for_action(action_type, previous_status, SummaryItemValidationError)
