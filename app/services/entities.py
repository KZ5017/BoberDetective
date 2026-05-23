from uuid import UUID

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import AnalysisRunModel
from app.models.entity import EntityMentionModel, EntityModel
from app.models.review import HumanReviewModel
from app.models.source_reference import SourceReferenceModel
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.detached_sources import create_detached_source_item
from app.services.reviews import list_object_reviews, record_object_review, review_status_for_action
from app.services.source_references import ensure_source_reference_document_is_active
from app.services.storage import StoragePaths
from app.services.users import get_or_create_dev_user


class EntityError(ValueError):
    pass


class EntityNotFoundError(EntityError):
    pass


class EntityValidationError(EntityError):
    pass


def list_entities(db: Session, case_id: UUID) -> list[EntityModel]:
    return list(
        db.execute(
            select(EntityModel)
            .where(EntityModel.case_id == case_id)
            .order_by(EntityModel.entity_type.asc(), EntityModel.canonical_name.asc())
        ).scalars()
    )


def get_entity(db: Session, case_id: UUID, entity_id: UUID) -> EntityModel:
    entity = db.get(EntityModel, entity_id)
    if entity is None or entity.case_id != case_id:
        raise EntityNotFoundError("Entity not found")
    return entity


def list_entity_mentions(db: Session, entity_id: UUID) -> list[EntityMentionModel]:
    return list(
        db.execute(
            select(EntityMentionModel)
            .where(EntityMentionModel.entity_id == entity_id)
            .order_by(EntityMentionModel.created_at.asc())
        ).scalars()
    )


def list_entity_reviews(db: Session, entity_id: UUID) -> list[HumanReviewModel]:
    return list_object_reviews(db, "entity", entity_id)


def review_entity(
    db: Session,
    *,
    case_id: UUID,
    entity_id: UUID,
    action_type: str,
    review_comment: str | None = None,
) -> EntityModel:
    entity = get_entity(db, case_id, entity_id)
    previous_status = entity.review_status
    new_status = _review_status_for_action(action_type, previous_status)

    if new_status is not None:
        entity.review_status = new_status
        entity.updated_at = datetime.now(UTC)
        db.add(entity)

    record_object_review(
        db,
        case_id=case_id,
        object_type="entity",
        object_id=entity.id,
        action_type=action_type,
        previous_status=previous_status,
        new_status=new_status,
        review_comment=review_comment,
        audit_event_type="entity_review_recorded",
    )
    db.commit()
    db.refresh(entity)
    return entity


def merge_entity(
    db: Session,
    *,
    case_id: UUID,
    source_entity_id: UUID,
    target_entity_id: UUID,
    review_comment: str | None = None,
) -> EntityModel:
    if source_entity_id == target_entity_id:
        raise EntityValidationError("Source and target entity must be different")

    source_entity = get_entity(db, case_id, source_entity_id)
    target_entity = get_entity(db, case_id, target_entity_id)
    if target_entity.review_status == "corrected":
        raise EntityValidationError("Corrected entities cannot be merge targets")

    source_mentions = list_entity_mentions(db, source_entity.id)
    if not source_mentions:
        raise EntityValidationError("Entities without sources cannot be merged")
    target_mentions = list_entity_mentions(db, target_entity.id)
    if not target_mentions:
        raise EntityValidationError("Entities without sources cannot be merge targets")
    _ensure_entity_mentions_have_active_documents(db, case_id, source_mentions + target_mentions)
    moved_mention_count = 0
    for mention in source_mentions:
        mention.entity_id = target_entity.id
        db.add(mention)
        moved_mention_count += 1

    previous_source_status = source_entity.review_status
    source_entity.review_status = "corrected"
    source_entity.updated_at = datetime.now(UTC)
    target_entity.updated_at = datetime.now(UTC)
    db.add(source_entity)
    db.add(target_entity)

    user = get_or_create_dev_user(db)
    source_review = HumanReviewModel(
        case_id=case_id,
        object_type="entity",
        object_id=source_entity.id,
        action_type="correct",
        previous_review_status=previous_source_status,
        new_review_status="corrected",
        review_comment=review_comment or f"Entitas osszevonva: {target_entity.canonical_name}",
        correction_patch_json={
            "operation": "merge_into",
            "target_entity_id": str(target_entity.id),
            "moved_mention_count": moved_mention_count,
        },
        performed_by_user_id=user.id,
    )
    target_review = HumanReviewModel(
        case_id=case_id,
        object_type="entity",
        object_id=target_entity.id,
        action_type="attach_source",
        previous_review_status=target_entity.review_status,
        new_review_status=None,
        review_comment=review_comment or f"Entitas forrasai hozzaadva: {source_entity.canonical_name}",
        correction_patch_json={
            "operation": "merge_from",
            "source_entity_id": str(source_entity.id),
            "moved_mention_count": moved_mention_count,
        },
        performed_by_user_id=user.id,
    )
    db.add(source_review)
    db.add(target_review)
    db.flush()

    audit_event = AuditEvent(
        event_type="entity_merged",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="entity",
        related_object_id=str(target_entity.id),
        input_summary={
            "source_entity_id": str(source_entity.id),
            "target_entity_id": str(target_entity.id),
            "source_review_status": previous_source_status,
        },
        output_summary={
            "target_entity_id": str(target_entity.id),
            "source_entity_new_review_status": source_entity.review_status,
            "moved_mention_count": moved_mention_count,
            "source_review_id": str(source_review.id),
            "target_review_id": str(target_review.id),
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(target_entity)
    return target_entity


def detach_entity_mention(
    db: Session,
    *,
    case_id: UUID,
    entity_id: UUID,
    mention_id: UUID,
    review_comment: str | None = None,
) -> EntityModel:
    entity = get_entity(db, case_id, entity_id)
    mention = db.get(EntityMentionModel, mention_id)
    if mention is None or mention.case_id != case_id or mention.entity_id != entity.id:
        raise EntityValidationError("Entity mention not found for this entity")
    source_reference = db.get(SourceReferenceModel, mention.source_reference_id) if mention.source_reference_id is not None else None
    if source_reference is None or source_reference.case_id != case_id:
        raise EntityValidationError("Entity mention source reference not found for this case")
    ensure_source_reference_document_is_active(db, case_id, source_reference, EntityValidationError)

    source_reference_id = mention.source_reference_id
    source_document_id = mention.document_id
    source_page_id = mention.page_id
    source_chunk_id = mention.chunk_id
    db.delete(mention)
    entity.updated_at = datetime.now(UTC)
    db.add(entity)

    user = get_or_create_dev_user(db)
    detached_item = create_detached_source_item(
        db,
        case_id=case_id,
        source_reference=source_reference,
        detached_from_object_type="entity",
        detached_from_object_id=entity.id,
        detached_from_source_link_id=mention_id,
        detached_from_source_link_type="entity_mention",
        object_title_snapshot=entity.canonical_name,
        object_body_snapshot=entity.description,
        object_subtype_snapshot=entity.entity_type,
        object_review_status_snapshot=entity.review_status,
        source_validation_status_snapshot="source_valid",
        detach_comment=review_comment,
        detached_by_user_id=user.id,
    )
    review = HumanReviewModel(
        case_id=case_id,
        object_type="entity",
        object_id=entity.id,
        action_type="detach_source",
        previous_review_status=entity.review_status,
        new_review_status=None,
        review_comment=review_comment or "Entitas forrasa levalasztva.",
        correction_patch_json={
            "operation": "detach_source",
            "mention_id": str(mention_id),
            "source_reference_id": str(source_reference_id) if source_reference_id is not None else None,
            "detached_source_item_id": str(detached_item.id),
        },
        performed_by_user_id=user.id,
    )
    db.add(review)
    db.flush()

    audit_event = AuditEvent(
        event_type="entity_source_detached",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="entity",
        related_object_id=str(entity.id),
        related_document_id=str(source_document_id),
        related_page_id=str(source_page_id) if source_page_id is not None else None,
        related_chunk_id=str(source_chunk_id) if source_chunk_id is not None else None,
        input_summary={"mention_id": str(mention_id), "source_reference_id": str(source_reference_id)},
        output_summary={"human_review_id": str(review.id), "detached_source_item_id": str(detached_item.id)},
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(entity)
    return entity


def move_entity_mention(
    db: Session,
    *,
    case_id: UUID,
    source_entity_id: UUID,
    mention_id: UUID,
    target_entity_id: UUID,
    review_comment: str | None = None,
) -> EntityModel:
    if source_entity_id == target_entity_id:
        raise EntityValidationError("Source and target entity must be different")

    source_entity = get_entity(db, case_id, source_entity_id)
    target_entity = get_entity(db, case_id, target_entity_id)
    mention = db.get(EntityMentionModel, mention_id)
    if mention is None or mention.case_id != case_id or mention.entity_id != source_entity.id:
        raise EntityValidationError("Entity mention not found for this entity")
    source_reference = db.get(SourceReferenceModel, mention.source_reference_id) if mention.source_reference_id is not None else None
    if source_reference is None or source_reference.case_id != case_id:
        raise EntityValidationError("Entity mention source reference not found for this case")
    ensure_source_reference_document_is_active(db, case_id, source_reference, EntityValidationError)
    _ensure_entity_mentions_have_active_documents(db, case_id, list_entity_mentions(db, target_entity.id))

    previous_target_status = target_entity.review_status
    target_reactivated = previous_target_status == "corrected"
    if target_reactivated:
        target_entity.review_status = "needs_review"

    mention.entity_id = target_entity.id
    source_entity.updated_at = datetime.now(UTC)
    target_entity.updated_at = datetime.now(UTC)
    db.add(mention)
    db.add(source_entity)
    db.add(target_entity)

    user = get_or_create_dev_user(db)
    source_review = HumanReviewModel(
        case_id=case_id,
        object_type="entity",
        object_id=source_entity.id,
        action_type="detach_source",
        previous_review_status=source_entity.review_status,
        new_review_status=None,
        review_comment=review_comment or f"Entitas forrasa athelyezve: {target_entity.canonical_name}",
        correction_patch_json={
            "operation": "move_source_to",
            "mention_id": str(mention_id),
            "target_entity_id": str(target_entity.id),
        },
        performed_by_user_id=user.id,
    )
    target_review = HumanReviewModel(
        case_id=case_id,
        object_type="entity",
        object_id=target_entity.id,
        action_type="attach_source",
        previous_review_status=previous_target_status,
        new_review_status=target_entity.review_status if target_reactivated else None,
        review_comment=review_comment or f"Entitas forrasa atveve: {source_entity.canonical_name}",
        correction_patch_json={
            "operation": "move_source_from",
            "mention_id": str(mention_id),
            "source_entity_id": str(source_entity.id),
            "reactivated_corrected_target": target_reactivated,
        },
        performed_by_user_id=user.id,
    )
    db.add(source_review)
    db.add(target_review)
    db.flush()

    audit_event = AuditEvent(
        event_type="entity_source_moved",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="entity",
        related_object_id=str(target_entity.id),
        related_document_id=str(mention.document_id),
        related_page_id=str(mention.page_id) if mention.page_id is not None else None,
        related_chunk_id=str(mention.chunk_id) if mention.chunk_id is not None else None,
        input_summary={
            "source_entity_id": str(source_entity.id),
            "target_entity_id": str(target_entity.id),
            "mention_id": str(mention_id),
        },
        output_summary={"source_review_id": str(source_review.id), "target_review_id": str(target_review.id)},
    )
    if target_reactivated:
        audit_event.output_summary["target_previous_review_status"] = previous_target_status
        audit_event.output_summary["target_new_review_status"] = target_entity.review_status
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(target_entity)
    return target_entity


def create_entity_with_mention(
    db: Session,
    *,
    case_id: UUID,
    entity_type: str,
    canonical_name: str,
    normalized_value: str | None,
    description: str | None,
    surface_text: str,
    source_reference_id: UUID,
    analysis_run_id: UUID,
) -> tuple[EntityModel, EntityMentionModel]:
    if canonical_name.strip() == "":
        raise EntityValidationError("Entity canonical name is required")
    if surface_text.strip() == "":
        raise EntityValidationError("Entity mention surface text is required")

    run = db.get(AnalysisRunModel, analysis_run_id)
    if run is None or run.case_id != case_id:
        raise EntityValidationError("Analysis run not found for this case")

    source_reference = db.get(SourceReferenceModel, source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise EntityValidationError("Source reference not found for this case")
    ensure_source_reference_document_is_active(db, case_id, source_reference, EntityValidationError)

    entity = _find_existing_entity(db, case_id, entity_type, canonical_name, normalized_value)
    created_entity = entity is None
    if entity is None:
        entity = EntityModel(
            case_id=case_id,
            entity_type=entity_type,
            canonical_name=canonical_name,
            normalized_value=normalized_value,
            description=description,
            created_by_analysis_run_id=analysis_run_id,
            review_status="needs_review",
        )
        db.add(entity)
        db.flush()

    mention = _find_existing_mention(db, entity.id, source_reference.id, surface_text)
    created_mention = mention is None
    if mention is None:
        mention = EntityMentionModel(
            case_id=case_id,
            entity_id=entity.id,
            document_id=source_reference.document_id,
            page_id=source_reference.page_id,
            chunk_id=source_reference.chunk_id,
            page_number=source_reference.page_number,
            surface_text=surface_text,
            char_start=source_reference.quote_char_start,
            char_end=source_reference.quote_char_end,
            source_reference_id=source_reference.id,
            created_by_analysis_run_id=analysis_run_id,
        )
        db.add(mention)
        db.flush()

    event_type = "entity_created" if created_entity else "entity_mention_created"
    audit_event = AuditEvent(
        event_type=event_type,
        success=True,
        case_id=str(case_id),
        user_id=str(run.started_by_user_id),
        analysis_run_id=str(analysis_run_id),
        related_object_type="entity",
        related_object_id=str(entity.id),
        related_document_id=str(source_reference.document_id),
        related_page_id=str(source_reference.page_id) if source_reference.page_id is not None else None,
        related_chunk_id=str(source_reference.chunk_id) if source_reference.chunk_id is not None else None,
        input_summary={"source_reference_id": str(source_reference.id), "created_entity": created_entity},
        output_summary={
            "entity_id": str(entity.id),
            "mention_id": str(mention.id),
            "entity_type": entity.entity_type,
            "created_mention": created_mention,
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(entity)
    db.refresh(mention)
    return entity, mention


def _find_existing_entity(
    db: Session,
    case_id: UUID,
    entity_type: str,
    canonical_name: str,
    normalized_value: str | None,
) -> EntityModel | None:
    expected_name = _normalize_entity_key(canonical_name)
    expected_normalized_value = _normalize_entity_key(normalized_value)
    matched_entities: list[EntityModel] = []
    entities = db.execute(
        select(EntityModel).where(
            EntityModel.case_id == case_id,
            EntityModel.entity_type == entity_type,
        )
    ).scalars()
    for entity in entities:
        same_name = _normalize_entity_key(entity.canonical_name) == expected_name
        same_normalized_value = (
            expected_normalized_value != "" and _normalize_entity_key(entity.normalized_value) == expected_normalized_value
        )
        if same_name or same_normalized_value:
            matched_entities.append(entity)
    return matched_entities[0] if len(matched_entities) == 1 else None


def _find_existing_mention(
    db: Session,
    entity_id: UUID,
    source_reference_id: UUID,
    surface_text: str,
) -> EntityMentionModel | None:
    expected_surface = _normalize_entity_key(surface_text)
    mentions = db.execute(
        select(EntityMentionModel).where(
            EntityMentionModel.entity_id == entity_id,
            EntityMentionModel.source_reference_id == source_reference_id,
        )
    ).scalars()
    for mention in mentions:
        if _normalize_entity_key(mention.surface_text) == expected_surface:
            return mention
    return None


def _normalize_entity_key(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _review_status_for_action(action_type: str, previous_status: str) -> str | None:
    return review_status_for_action(action_type, previous_status, EntityValidationError)


def _ensure_entity_mentions_have_active_documents(db: Session, case_id: UUID, mentions: list[EntityMentionModel]) -> None:
    for mention in mentions:
        source_reference = db.get(SourceReferenceModel, mention.source_reference_id) if mention.source_reference_id is not None else None
        if source_reference is None or source_reference.case_id != case_id:
            raise EntityValidationError("Entity mention source reference not found for this case")
        ensure_source_reference_document_is_active(db, case_id, source_reference, EntityValidationError)
