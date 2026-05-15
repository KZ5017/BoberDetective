from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.detached_source import DetachedSourceItemModel
from app.models.entity import EntityMentionModel, EntityModel
from app.models.event import EventModel, EventSourceModel
from app.models.missing_item import MissingItemCandidateModel, MissingItemCandidateSourceModel
from app.models.review import HumanReviewModel
from app.models.source_reference import SourceReferenceModel
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.storage import StoragePaths
from app.services.users import get_or_create_dev_user


class DetachedSourceError(ValueError):
    pass


class DetachedSourceNotFoundError(DetachedSourceError):
    pass


class DetachedSourceValidationError(DetachedSourceError):
    pass


def list_detached_source_items(db: Session, case_id: UUID) -> list[DetachedSourceItemModel]:
    return list(
        db.execute(
            select(DetachedSourceItemModel)
            .where(DetachedSourceItemModel.case_id == case_id)
            .order_by(DetachedSourceItemModel.detached_at.desc())
        ).scalars()
    )


def get_detached_source_item(db: Session, case_id: UUID, item_id: UUID) -> DetachedSourceItemModel:
    item = db.get(DetachedSourceItemModel, item_id)
    if item is None or item.case_id != case_id:
        raise DetachedSourceNotFoundError("Detached source item not found")
    return item


def create_detached_source_item(
    db: Session,
    *,
    case_id: UUID,
    source_reference: SourceReferenceModel,
    detached_from_object_type: str,
    detached_from_object_id: UUID,
    detached_from_source_link_id: UUID,
    detached_from_source_link_type: str,
    object_title_snapshot: str,
    object_body_snapshot: str | None,
    object_subtype_snapshot: str | None,
    object_review_status_snapshot: str | None,
    source_validation_status_snapshot: str | None,
    detach_comment: str | None,
    detached_by_user_id: UUID,
) -> DetachedSourceItemModel:
    item = DetachedSourceItemModel(
        case_id=case_id,
        source_reference_id=source_reference.id,
        detached_from_object_type=detached_from_object_type,
        detached_from_object_id=detached_from_object_id,
        detached_from_source_link_id=detached_from_source_link_id,
        detached_from_source_link_type=detached_from_source_link_type,
        object_title_snapshot=object_title_snapshot,
        object_body_snapshot=object_body_snapshot,
        object_subtype_snapshot=object_subtype_snapshot,
        object_review_status_snapshot=object_review_status_snapshot,
        source_validation_status_snapshot=source_validation_status_snapshot,
        source_snapshot_json={
            "document_id": str(source_reference.document_id),
            "page_id": str(source_reference.page_id) if source_reference.page_id is not None else None,
            "chunk_id": str(source_reference.chunk_id) if source_reference.chunk_id is not None else None,
            "page_number": source_reference.page_number,
            "quote_text": source_reference.quote_text,
            "quote_char_start": source_reference.quote_char_start,
            "quote_char_end": source_reference.quote_char_end,
            "citation_label": source_reference.citation_label,
            "source_kind": source_reference.source_kind,
        },
        handling_status="needs_review",
        detach_comment=detach_comment,
        detached_by_user_id=detached_by_user_id,
        detached_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(item)
    db.flush()
    return item


def attach_detached_source_item(
    db: Session,
    *,
    case_id: UUID,
    item_id: UUID,
    target_object_id: UUID,
    review_comment: str | None = None,
) -> DetachedSourceItemModel:
    item = get_detached_source_item(db, case_id, item_id)
    if item.handling_status != "needs_review":
        raise DetachedSourceValidationError("Detached source item has already been handled")

    source_reference = db.get(SourceReferenceModel, item.source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise DetachedSourceValidationError("Detached source reference not found for this case")

    user = get_or_create_dev_user(db)
    skipped_duplicate_source = False
    if item.detached_from_object_type == "entity":
        target = db.get(EntityModel, target_object_id)
        if target is None or target.case_id != case_id:
            raise DetachedSourceValidationError("Target entity not found for this case")
        if item.object_subtype_snapshot and target.entity_type != item.object_subtype_snapshot:
            raise DetachedSourceValidationError("Target entity type does not match detached source snapshot")
        duplicate = db.execute(
            select(EntityMentionModel).where(
                EntityMentionModel.entity_id == target.id,
                EntityMentionModel.source_reference_id == source_reference.id,
            )
        ).scalar_one_or_none()
        skipped_duplicate_source = duplicate is not None
        if not skipped_duplicate_source:
            db.add(
                EntityMentionModel(
                    case_id=case_id,
                    entity_id=target.id,
                    document_id=source_reference.document_id,
                    page_id=source_reference.page_id,
                    chunk_id=source_reference.chunk_id,
                    page_number=source_reference.page_number,
                    surface_text=source_reference.quote_text,
                    char_start=source_reference.quote_char_start,
                    char_end=source_reference.quote_char_end,
                    source_reference_id=source_reference.id,
                    created_by_analysis_run_id=source_reference.extraction_run_id,
                )
            )
        target.updated_at = datetime.now(UTC)
        object_type = "entity"
        object_id = target.id
        object_title = target.canonical_name
    elif item.detached_from_object_type == "event":
        target = db.get(EventModel, target_object_id)
        if target is None or target.case_id != case_id:
            raise DetachedSourceValidationError("Target event not found for this case")
        if item.object_subtype_snapshot and target.event_type != item.object_subtype_snapshot:
            raise DetachedSourceValidationError("Target event type does not match detached source snapshot")
        duplicate = db.execute(
            select(EventSourceModel).where(
                EventSourceModel.event_id == target.id,
                EventSourceModel.source_reference_id == source_reference.id,
            )
        ).scalar_one_or_none()
        skipped_duplicate_source = duplicate is not None
        if not skipped_duplicate_source:
            db.add(EventSourceModel(event_id=target.id, source_reference_id=source_reference.id, relevance_rank=None, support_type="direct"))
        target.source_validation_status = "source_valid"
        target.updated_at = datetime.now(UTC)
        object_type = "event"
        object_id = target.id
        object_title = target.event_title
    elif item.detached_from_object_type == "missing_item_candidate":
        target = db.get(MissingItemCandidateModel, target_object_id)
        if target is None or target.case_id != case_id:
            raise DetachedSourceValidationError("Target missing item candidate not found for this case")
        if item.object_subtype_snapshot and target.missing_item_type != item.object_subtype_snapshot:
            raise DetachedSourceValidationError("Target missing item type does not match detached source snapshot")
        duplicate = db.execute(
            select(MissingItemCandidateSourceModel).where(
                MissingItemCandidateSourceModel.missing_item_candidate_id == target.id,
                MissingItemCandidateSourceModel.source_reference_id == source_reference.id,
            )
        ).scalar_one_or_none()
        skipped_duplicate_source = duplicate is not None
        if not skipped_duplicate_source:
            db.add(MissingItemCandidateSourceModel(missing_item_candidate_id=target.id, source_reference_id=source_reference.id, relevance_rank=None))
        target.source_validation_status = "source_valid"
        target.updated_at = datetime.now(UTC)
        object_type = "missing_item_candidate"
        object_id = target.id
        object_title = target.referenced_item_text
    else:
        raise DetachedSourceValidationError("Unsupported detached source object type")

    item.handling_status = "reattached"
    item.reattached_to_object_type = object_type
    item.reattached_to_object_id = object_id
    item.reattached_to_object_title_snapshot = object_title
    item.updated_at = datetime.now(UTC)
    db.add(item)

    review = HumanReviewModel(
        case_id=case_id,
        object_type=object_type,
        object_id=object_id,
        action_type="attach_source",
        previous_review_status=None,
        new_review_status=None,
        review_comment=review_comment or f"Levalasztott forras csatolva: {object_title}",
        correction_patch_json={
            "operation": "reattach_detached_source",
            "detached_source_item_id": str(item.id),
            "source_reference_id": str(source_reference.id),
            "skipped_duplicate_source": skipped_duplicate_source,
        },
        performed_by_user_id=user.id,
    )
    db.add(review)
    db.flush()

    audit_event = AuditEvent(
        event_type="detached_source_reattached",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type=object_type,
        related_object_id=str(object_id),
        related_document_id=str(source_reference.document_id),
        related_page_id=str(source_reference.page_id) if source_reference.page_id is not None else None,
        related_chunk_id=str(source_reference.chunk_id) if source_reference.chunk_id is not None else None,
        input_summary={"detached_source_item_id": str(item.id), "target_object_id": str(target_object_id)},
        output_summary={"human_review_id": str(review.id), "skipped_duplicate_source": skipped_duplicate_source},
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(item)
    return item


def discard_detached_source_item(
    db: Session,
    *,
    case_id: UUID,
    item_id: UUID,
    review_comment: str | None = None,
) -> DetachedSourceItemModel:
    item = get_detached_source_item(db, case_id, item_id)
    if item.handling_status != "needs_review":
        raise DetachedSourceValidationError("Detached source item has already been handled")

    user = get_or_create_dev_user(db)
    item.handling_status = "discarded"
    item.updated_at = datetime.now(UTC)
    db.add(item)
    review = HumanReviewModel(
        case_id=case_id,
        object_type="source_reference",
        object_id=item.source_reference_id,
        action_type="reject",
        previous_review_status=None,
        new_review_status=None,
        review_comment=review_comment or "Levalasztott forras irrelevansnak jelolve.",
        correction_patch_json={"operation": "discard_detached_source", "detached_source_item_id": str(item.id)},
        performed_by_user_id=user.id,
    )
    db.add(review)
    db.flush()

    audit_event = AuditEvent(
        event_type="detached_source_discarded",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="source_reference",
        related_object_id=str(item.source_reference_id),
        input_summary={"detached_source_item_id": str(item.id)},
        output_summary={"human_review_id": str(review.id), "handling_status": item.handling_status},
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(item)
    return item
