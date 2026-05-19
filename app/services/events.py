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
from app.services.detached_sources import create_detached_source_item
from app.services.reviews import list_object_reviews, record_object_review, review_status_for_action
from app.services.source_references import ensure_source_reference_document_is_active
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
    return list_object_reviews(db, "event", event_id)


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

    if new_status is not None:
        event.review_status = new_status
        event.updated_at = datetime.now(UTC)
        db.add(event)

    record_object_review(
        db,
        case_id=case_id,
        object_type="event",
        object_id=event.id,
        action_type=action_type,
        previous_status=previous_status,
        new_status=new_status,
        review_comment=review_comment,
        audit_event_type="event_review_recorded",
    )
    db.commit()
    db.refresh(event)
    return event


def merge_event(
    db: Session,
    *,
    case_id: UUID,
    source_event_id: UUID,
    target_event_id: UUID,
    review_comment: str | None = None,
) -> EventModel:
    if source_event_id == target_event_id:
        raise EventValidationError("Source and target event must be different")

    source_event = get_event(db, case_id, source_event_id)
    target_event = get_event(db, case_id, target_event_id)
    if source_event.event_type != target_event.event_type:
        raise EventValidationError("Only events with the same type can be merged")
    if target_event.review_status == "corrected":
        raise EventValidationError("Corrected events cannot be merge targets")
    if source_event.source_validation_status == "source_invalid":
        raise EventValidationError("Events without valid sources cannot be merged")
    if target_event.source_validation_status == "source_invalid":
        raise EventValidationError("Events without valid sources cannot be merge targets")
    source_event_sources = list_event_sources(db, source_event.id)
    target_event_sources = list_event_sources(db, target_event.id)
    if not source_event_sources:
        raise EventValidationError("Events without valid sources cannot be merged")
    if not target_event_sources:
        raise EventValidationError("Events without valid sources cannot be merge targets")
    _ensure_event_sources_have_active_documents(db, case_id, source_event_sources + target_event_sources)

    target_source_reference_ids = {
        source.source_reference_id
        for source in db.execute(select(EventSourceModel).where(EventSourceModel.event_id == target_event.id)).scalars()
    }
    moved_source_count = 0
    skipped_duplicate_source_count = 0
    for source in source_event_sources:
        if source.source_reference_id in target_source_reference_ids:
            db.delete(source)
            skipped_duplicate_source_count += 1
            continue
        source.event_id = target_event.id
        db.add(source)
        target_source_reference_ids.add(source.source_reference_id)
        moved_source_count += 1

    previous_source_status = source_event.review_status
    source_event.review_status = "corrected"
    source_event.updated_at = datetime.now(UTC)
    target_event.updated_at = datetime.now(UTC)
    db.add(source_event)
    db.add(target_event)

    user = get_or_create_dev_user(db)
    source_review = HumanReviewModel(
        case_id=case_id,
        object_type="event",
        object_id=source_event.id,
        action_type="correct",
        previous_review_status=previous_source_status,
        new_review_status="corrected",
        review_comment=review_comment or f"Esemeny osszevonva: {target_event.event_title}",
        correction_patch_json={
            "operation": "merge_into",
            "target_event_id": str(target_event.id),
            "moved_source_count": moved_source_count,
            "skipped_duplicate_source_count": skipped_duplicate_source_count,
        },
        performed_by_user_id=user.id,
    )
    target_review = HumanReviewModel(
        case_id=case_id,
        object_type="event",
        object_id=target_event.id,
        action_type="attach_source",
        previous_review_status=target_event.review_status,
        new_review_status=None,
        review_comment=review_comment or f"Esemeny forrasai hozzaadva: {source_event.event_title}",
        correction_patch_json={
            "operation": "merge_from",
            "source_event_id": str(source_event.id),
            "moved_source_count": moved_source_count,
            "skipped_duplicate_source_count": skipped_duplicate_source_count,
        },
        performed_by_user_id=user.id,
    )
    db.add(source_review)
    db.add(target_review)
    db.flush()

    audit_event = AuditEvent(
        event_type="event_merged",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="event",
        related_object_id=str(target_event.id),
        input_summary={
            "source_event_id": str(source_event.id),
            "target_event_id": str(target_event.id),
            "source_review_status": previous_source_status,
        },
        output_summary={
            "target_event_id": str(target_event.id),
            "source_event_new_review_status": source_event.review_status,
            "moved_source_count": moved_source_count,
            "skipped_duplicate_source_count": skipped_duplicate_source_count,
            "source_review_id": str(source_review.id),
            "target_review_id": str(target_review.id),
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(target_event)
    return target_event


def detach_event_source(
    db: Session,
    *,
    case_id: UUID,
    event_id: UUID,
    event_source_id: UUID,
    review_comment: str | None = None,
) -> EventModel:
    event = get_event(db, case_id, event_id)
    source_link = db.get(EventSourceModel, event_source_id)
    if source_link is None or source_link.event_id != event.id:
        raise EventValidationError("Event source not found for this event")

    source_reference = db.get(SourceReferenceModel, source_link.source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise EventValidationError("Event source reference not found for this case")
    ensure_source_reference_document_is_active(db, case_id, source_reference, EventValidationError)
    source_reference_id = source_link.source_reference_id
    db.delete(source_link)
    db.flush()
    remaining_source_count = len(list_event_sources(db, event.id))
    if remaining_source_count <= 0:
        event.source_validation_status = "source_invalid"
    event.updated_at = datetime.now(UTC)
    db.add(event)

    user = get_or_create_dev_user(db)
    detached_item = create_detached_source_item(
        db,
        case_id=case_id,
        source_reference=source_reference,
        detached_from_object_type="event",
        detached_from_object_id=event.id,
        detached_from_source_link_id=event_source_id,
        detached_from_source_link_type="event_source",
        object_title_snapshot=event.event_title,
        object_body_snapshot=event.event_description,
        object_subtype_snapshot=event.event_type,
        object_review_status_snapshot=event.review_status,
        source_validation_status_snapshot=event.source_validation_status,
        detach_comment=review_comment,
        detached_by_user_id=user.id,
    )
    review = HumanReviewModel(
        case_id=case_id,
        object_type="event",
        object_id=event.id,
        action_type="detach_source",
        previous_review_status=event.review_status,
        new_review_status=None,
        review_comment=review_comment or "Esemeny forrasa levalasztva.",
        correction_patch_json={
            "operation": "detach_source",
            "event_source_id": str(event_source_id),
            "source_reference_id": str(source_reference_id),
            "detached_source_item_id": str(detached_item.id),
        },
        performed_by_user_id=user.id,
    )
    db.add(review)
    db.flush()

    audit_event = AuditEvent(
        event_type="event_source_detached",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="event",
        related_object_id=str(event.id),
        related_document_id=str(source_reference.document_id) if source_reference is not None else None,
        related_page_id=str(source_reference.page_id) if source_reference is not None and source_reference.page_id is not None else None,
        related_chunk_id=str(source_reference.chunk_id) if source_reference is not None and source_reference.chunk_id is not None else None,
        input_summary={"event_source_id": str(event_source_id), "source_reference_id": str(source_reference_id)},
        output_summary={
            "human_review_id": str(review.id),
            "detached_source_item_id": str(detached_item.id),
            "remaining_source_count": max(0, remaining_source_count),
            "source_validation_status": event.source_validation_status,
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(event)
    return event


def move_event_source(
    db: Session,
    *,
    case_id: UUID,
    source_event_id: UUID,
    event_source_id: UUID,
    target_event_id: UUID,
    review_comment: str | None = None,
) -> EventModel:
    if source_event_id == target_event_id:
        raise EventValidationError("Source and target event must be different")

    source_event = get_event(db, case_id, source_event_id)
    target_event = get_event(db, case_id, target_event_id)
    if source_event.event_type != target_event.event_type:
        raise EventValidationError("Only events with the same type can receive this source")

    source_link = db.get(EventSourceModel, event_source_id)
    if source_link is None or source_link.event_id != source_event.id:
        raise EventValidationError("Event source not found for this event")
    source_reference = db.get(SourceReferenceModel, source_link.source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise EventValidationError("Event source reference not found for this case")
    ensure_source_reference_document_is_active(db, case_id, source_reference, EventValidationError)
    _ensure_event_sources_have_active_documents(db, case_id, list_event_sources(db, target_event.id))

    previous_target_status = target_event.review_status
    target_reactivated = previous_target_status == "corrected"
    if target_reactivated:
        target_event.review_status = "needs_review"

    duplicate = db.execute(
        select(EventSourceModel).where(
            EventSourceModel.event_id == target_event.id,
            EventSourceModel.source_reference_id == source_link.source_reference_id,
        )
    ).scalar_one_or_none()
    skipped_duplicate_source = duplicate is not None
    if skipped_duplicate_source:
        db.delete(source_link)
    else:
        source_link.event_id = target_event.id
        db.add(source_link)

    db.flush()
    remaining_source_count = len(list_event_sources(db, source_event.id))
    if remaining_source_count <= 0:
        source_event.source_validation_status = "source_invalid"
    target_event.source_validation_status = "source_valid"
    source_event.updated_at = datetime.now(UTC)
    target_event.updated_at = datetime.now(UTC)
    db.add(source_event)
    db.add(target_event)

    user = get_or_create_dev_user(db)
    source_review = HumanReviewModel(
        case_id=case_id,
        object_type="event",
        object_id=source_event.id,
        action_type="detach_source",
        previous_review_status=source_event.review_status,
        new_review_status=None,
        review_comment=review_comment or f"Esemeny forrasa athelyezve: {target_event.event_title}",
        correction_patch_json={
            "operation": "move_source_to",
            "event_source_id": str(event_source_id),
            "target_event_id": str(target_event.id),
            "skipped_duplicate_source": skipped_duplicate_source,
        },
        performed_by_user_id=user.id,
    )
    target_review = HumanReviewModel(
        case_id=case_id,
        object_type="event",
        object_id=target_event.id,
        action_type="attach_source",
        previous_review_status=previous_target_status,
        new_review_status=target_event.review_status if target_reactivated else None,
        review_comment=review_comment or f"Esemeny forrasa atveve: {source_event.event_title}",
        correction_patch_json={
            "operation": "move_source_from",
            "event_source_id": str(event_source_id),
            "source_event_id": str(source_event.id),
            "skipped_duplicate_source": skipped_duplicate_source,
            "reactivated_corrected_target": target_reactivated,
        },
        performed_by_user_id=user.id,
    )
    db.add(source_review)
    db.add(target_review)
    db.flush()

    audit_event = AuditEvent(
        event_type="event_source_moved",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="event",
        related_object_id=str(target_event.id),
        input_summary={
            "source_event_id": str(source_event.id),
            "target_event_id": str(target_event.id),
            "event_source_id": str(event_source_id),
        },
        output_summary={
            "source_review_id": str(source_review.id),
            "target_review_id": str(target_review.id),
            "skipped_duplicate_source": skipped_duplicate_source,
            "remaining_source_count": remaining_source_count,
            "target_previous_review_status": previous_target_status if target_reactivated else None,
            "target_new_review_status": target_event.review_status if target_reactivated else None,
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(target_event)
    return target_event


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
    ensure_source_reference_document_is_active(db, case_id, source_reference, EventValidationError)

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
    return review_status_for_action(action_type, previous_status, EventValidationError)


def _ensure_event_sources_have_active_documents(db: Session, case_id: UUID, sources: list[EventSourceModel]) -> None:
    for source in sources:
        source_reference = db.get(SourceReferenceModel, source.source_reference_id)
        if source_reference is None or source_reference.case_id != case_id:
            raise EventValidationError("Event source reference not found for this case")
        ensure_source_reference_document_is_active(db, case_id, source_reference, EventValidationError)
