from uuid import UUID

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import AnalysisRunModel
from app.models.event import EventModel, EventSourceModel
from app.models.review import HumanReviewModel
from app.models.source_reference import SourceReferenceModel
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.storage import StoragePaths
from app.services.users import get_or_create_dev_user


class EventError(ValueError):
    pass


class EventNotFoundError(EventError):
    pass


class EventValidationError(EventError):
    pass


def list_events(db: Session, case_id: UUID) -> list[EventModel]:
    return list(
        db.execute(
            select(EventModel)
            .where(EventModel.case_id == case_id)
            .order_by(EventModel.event_time_start.asc().nullslast(), EventModel.created_at.desc())
        ).scalars()
    )


def get_event(db: Session, case_id: UUID, event_id: UUID) -> EventModel:
    event = db.get(EventModel, event_id)
    if event is None or event.case_id != case_id:
        raise EventNotFoundError("Event not found")
    return event


def list_event_sources(db: Session, event_id: UUID) -> list[EventSourceModel]:
    return list(
        db.execute(select(EventSourceModel).where(EventSourceModel.event_id == event_id).order_by(EventSourceModel.relevance_rank.asc())).scalars()
    )


def list_event_reviews(db: Session, event_id: UUID) -> list[HumanReviewModel]:
    return list(
        db.execute(
            select(HumanReviewModel)
            .where(HumanReviewModel.object_type == "event", HumanReviewModel.object_id == event_id)
            .order_by(HumanReviewModel.performed_at.desc())
        ).scalars()
    )


def review_event(
    db: Session,
    *,
    case_id: UUID,
    event_id: UUID,
    action_type: str,
    review_comment: str | None = None,
) -> EventModel:
    event = get_event(db, case_id, event_id)
    previous_status = event.review_status
    new_status = _review_status_for_action(action_type, previous_status)
    user = get_or_create_dev_user(db)

    if new_status is not None:
        event.review_status = new_status
        event.updated_at = datetime.now(UTC)
        db.add(event)

    review = HumanReviewModel(
        case_id=case_id,
        object_type="event",
        object_id=event.id,
        action_type=action_type,
        previous_review_status=previous_status,
        new_review_status=new_status,
        review_comment=review_comment,
        performed_by_user_id=user.id,
    )
    db.add(review)
    db.flush()

    audit_event = AuditEvent(
        event_type="event_review_recorded",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="event",
        related_object_id=str(event.id),
        input_summary={"action_type": action_type, "previous_review_status": previous_status},
        output_summary={"new_review_status": new_status, "human_review_id": str(review.id)},
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(event)
    return event


def create_event_with_source(
    db: Session,
    *,
    case_id: UUID,
    event_type: str,
    event_title: str,
    event_description: str | None,
    event_time_raw: str | None,
    time_precision: str | None,
    location_text: str | None,
    source_reference_id: UUID,
    analysis_run_id: UUID,
    support_type: str = "direct",
    relevance_rank: int = 0,
) -> EventModel:
    if event_title.strip() == "":
        raise EventValidationError("Event title is required")

    run = db.get(AnalysisRunModel, analysis_run_id)
    if run is None or run.case_id != case_id:
        raise EventValidationError("Analysis run not found for this case")

    source_reference = db.get(SourceReferenceModel, source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise EventValidationError("Source reference not found for this case")

    event = EventModel(
        case_id=case_id,
        event_type=event_type,
        event_title=event_title,
        event_description=event_description,
        event_time_raw=event_time_raw,
        time_precision=time_precision or "unknown",
        location_text=location_text,
        created_by_analysis_run_id=analysis_run_id,
        source_validation_status="source_valid",
        review_status="needs_review",
    )
    db.add(event)
    db.flush()

    db.add(
        EventSourceModel(
            event_id=event.id,
            source_reference_id=source_reference.id,
            relevance_rank=relevance_rank,
            support_type=support_type,
        )
    )
    db.flush()

    audit_event = AuditEvent(
        event_type="event_created",
        success=True,
        case_id=str(case_id),
        user_id=str(run.started_by_user_id),
        analysis_run_id=str(analysis_run_id),
        related_object_type="event",
        related_object_id=str(event.id),
        related_document_id=str(source_reference.document_id),
        related_page_id=str(source_reference.page_id) if source_reference.page_id is not None else None,
        related_chunk_id=str(source_reference.chunk_id) if source_reference.chunk_id is not None else None,
        input_summary={"source_reference_id": str(source_reference.id)},
        output_summary={"event_id": str(event.id), "event_type": event.event_type},
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(event)
    return event


def _review_status_for_action(action_type: str, previous_status: str) -> str | None:
    if action_type == "verify":
        return "verified"
    if action_type == "reject":
        return "rejected"
    if action_type == "mark_needs_review":
        return "needs_review"
    if action_type == "comment":
        return None
    raise EventValidationError("Unsupported event review action")
