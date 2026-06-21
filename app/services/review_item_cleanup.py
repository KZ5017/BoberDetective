from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.claim import ClaimModel, ClaimSourceModel
from app.models.contradiction import ContradictionCandidateModel, ContradictionCandidateSourceModel
from app.models.entity import EntityMentionModel, EntityModel
from app.models.event import EventModel, EventSourceModel
from app.models.missing_item import MissingItemCandidateModel, MissingItemCandidateSourceModel
from app.models.review import HumanReviewModel
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.storage import StoragePaths
from app.services.users import get_or_create_dev_user


class ReviewItemCleanupError(ValueError):
    pass


class ReviewItemCleanupNotFoundError(ReviewItemCleanupError):
    pass


def _cleanup_allowed(review_status: str, source_validation_status: str) -> bool:
    return review_status == "corrected" or source_validation_status == "source_invalid"


def _text_update_allowed(review_status: str, source_validation_status: str) -> bool:
    return review_status != "corrected" and source_validation_status == "source_valid"


def update_review_report_item_text(
    db: Session,
    *,
    case_id: UUID,
    object_type: str,
    object_id: UUID,
    title: str,
    description: str,
) -> None:
    normalized_title = title.strip()
    normalized_description = description.strip()
    if normalized_title == "":
        raise ReviewItemCleanupError("Title cannot be empty")
    if normalized_description == "":
        raise ReviewItemCleanupError("Description cannot be empty")

    if object_type == "claim":
        target, snapshot = _text_target_claim(db, case_id, object_id)
        target.claim_title = normalized_title
        target.claim_text = normalized_description
    elif object_type == "entity":
        target, snapshot = _text_target_entity(db, case_id, object_id)
        target.canonical_name = normalized_title
        target.description = normalized_description
    elif object_type == "event":
        target, snapshot = _text_target_event(db, case_id, object_id)
        target.event_title = normalized_title
        target.event_description = normalized_description
    elif object_type == "contradiction_candidate":
        target, snapshot = _text_target_contradiction_candidate(db, case_id, object_id)
        target.title = normalized_title
        target.description = normalized_description
    elif object_type == "missing_item_candidate":
        target, snapshot = _text_target_missing_item_candidate(db, case_id, object_id)
        target.referenced_item_text = normalized_title
        target.description = normalized_description
    else:
        raise ReviewItemCleanupError("Unsupported review report item type")

    if not _text_update_allowed(snapshot["review_status"], snapshot["source_validation_status"]):
        raise ReviewItemCleanupError("Only source-valid, non-corrected review report items can be edited")
    if snapshot["title"] == normalized_title and snapshot["description"] == normalized_description:
        raise ReviewItemCleanupError("Text update would not change the item")

    target.updated_at = datetime.now(UTC)
    user = get_or_create_dev_user(db)
    review = HumanReviewModel(
        case_id=case_id,
        object_type=object_type,
        object_id=object_id,
        action_type="edit_text",
        previous_review_status=snapshot["review_status"],
        new_review_status=None,
        review_comment="Találat címe/leírása módosítva.",
        correction_patch_json={
            "operation": "update_review_report_item_text",
            "previous_title": snapshot["title"],
            "new_title": normalized_title,
            "previous_description": snapshot["description"],
            "new_description": normalized_description,
        },
        performed_by_user_id=user.id,
    )
    db.add(review)
    db.flush()

    audit_event = AuditEvent(
        event_type="review_report_item_text_updated",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type=object_type,
        related_object_id=str(object_id),
        input_summary={
            "object_type": object_type,
            "object_id": str(object_id),
            "review_status": snapshot["review_status"],
            "source_validation_status": snapshot["source_validation_status"],
        },
        output_summary={
            "human_review_id": str(review.id),
            "previous_title": snapshot["title"],
            "new_title": normalized_title,
            "previous_description": snapshot["description"],
            "new_description": normalized_description,
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()


def delete_review_report_item(db: Session, *, case_id: UUID, object_type: str, object_id: UUID) -> None:
    if object_type == "claim":
        snapshot = _delete_claim(db, case_id, object_id)
    elif object_type == "entity":
        snapshot = _delete_entity(db, case_id, object_id)
    elif object_type == "event":
        snapshot = _delete_event(db, case_id, object_id)
    elif object_type == "contradiction_candidate":
        snapshot = _delete_contradiction_candidate(db, case_id, object_id)
    elif object_type == "missing_item_candidate":
        snapshot = _delete_missing_item_candidate(db, case_id, object_id)
    else:
        raise ReviewItemCleanupError("Unsupported review report item type")

    user = get_or_create_dev_user(db)
    review = HumanReviewModel(
        case_id=case_id,
        object_type=object_type,
        object_id=object_id,
        action_type="delete_object",
        previous_review_status=snapshot["review_status"],
        new_review_status=None,
        review_comment="Találat véglegesen törölve az áttekintési jelentésből.",
        correction_patch_json={
            "operation": "delete_review_report_item",
            "object_type": object_type,
            "object_id": str(object_id),
            "source_validation_status": snapshot["source_validation_status"],
            "title": snapshot["title"],
        },
        performed_by_user_id=user.id,
    )
    db.add(review)
    db.flush()

    audit_event = AuditEvent(
        event_type="review_report_item_deleted",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type=object_type,
        related_object_id=str(object_id),
        input_summary={
            "object_type": object_type,
            "object_id": str(object_id),
            "review_status": snapshot["review_status"],
            "source_validation_status": snapshot["source_validation_status"],
        },
        output_summary={
            "human_review_id": str(review.id),
            "deleted": True,
            "deleted_source_links": snapshot["deleted_source_links"],
            "deleted_dependent_contradiction_candidates": snapshot.get("deleted_dependent_contradiction_candidates", []),
            "corrected_dependent_contradiction_candidates": snapshot.get("corrected_dependent_contradiction_candidates", []),
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()


def _delete_claim(db: Session, case_id: UUID, claim_id: UUID) -> dict:
    claim = db.get(ClaimModel, claim_id)
    if claim is None or claim.case_id != case_id:
        raise ReviewItemCleanupNotFoundError("Claim not found")
    dependent_ids = _contradiction_candidate_ids_for_claim(db, case_id, claim.id)
    source_count = _count_claim_sources(db, claim.id)
    snapshot = {
        "title": claim.claim_title,
        "review_status": claim.review_status,
        "source_validation_status": claim.source_validation_status,
        "deleted_source_links": source_count,
        "corrected_dependent_contradiction_candidates": [str(item_id) for item_id in dependent_ids],
    }
    _ensure_cleanup_allowed(snapshot)
    _detach_claim_from_dependent_contradiction_candidates(db, case_id, claim.id)
    db.execute(delete(ClaimSourceModel).where(ClaimSourceModel.claim_id == claim.id))
    db.delete(claim)
    return snapshot


def _text_target_claim(db: Session, case_id: UUID, claim_id: UUID) -> tuple[ClaimModel, dict]:
    claim = db.get(ClaimModel, claim_id)
    if claim is None or claim.case_id != case_id:
        raise ReviewItemCleanupNotFoundError("Claim not found")
    return claim, {
        "title": claim.claim_title,
        "description": claim.claim_text,
        "review_status": claim.review_status,
        "source_validation_status": claim.source_validation_status,
    }


def _delete_event(db: Session, case_id: UUID, event_id: UUID) -> dict:
    event = db.get(EventModel, event_id)
    if event is None or event.case_id != case_id:
        raise ReviewItemCleanupNotFoundError("Event not found")
    dependent_ids = _contradiction_candidate_ids_for_event(db, case_id, event.id)
    source_count = _count_event_sources(db, event.id)
    snapshot = {
        "title": event.event_title,
        "review_status": event.review_status,
        "source_validation_status": event.source_validation_status,
        "deleted_source_links": source_count,
        "corrected_dependent_contradiction_candidates": [str(item_id) for item_id in dependent_ids],
    }
    _ensure_cleanup_allowed(snapshot)
    _detach_event_from_dependent_contradiction_candidates(db, case_id, event.id)
    db.execute(update(ClaimModel).where(ClaimModel.related_event_id == event.id).values(related_event_id=None, updated_at=datetime.now(UTC)))
    db.execute(delete(EventSourceModel).where(EventSourceModel.event_id == event.id))
    db.delete(event)
    return snapshot


def _text_target_event(db: Session, case_id: UUID, event_id: UUID) -> tuple[EventModel, dict]:
    event = db.get(EventModel, event_id)
    if event is None or event.case_id != case_id:
        raise ReviewItemCleanupNotFoundError("Event not found")
    return event, {
        "title": event.event_title,
        "description": event.event_description or "",
        "review_status": event.review_status,
        "source_validation_status": event.source_validation_status,
    }


def _delete_entity(db: Session, case_id: UUID, entity_id: UUID) -> dict:
    entity = db.get(EntityModel, entity_id)
    if entity is None or entity.case_id != case_id:
        raise ReviewItemCleanupNotFoundError("Entity not found")
    mention_count = _count_entity_mentions(db, entity.id)
    source_validation_status = "source_valid" if mention_count else "source_invalid"
    snapshot = {
        "title": entity.canonical_name,
        "review_status": entity.review_status,
        "source_validation_status": source_validation_status,
        "deleted_source_links": mention_count,
    }
    _ensure_cleanup_allowed(snapshot)
    db.execute(update(ClaimModel).where(ClaimModel.speaker_entity_id == entity.id).values(speaker_entity_id=None, updated_at=datetime.now(UTC)))
    db.execute(
        update(ClaimModel)
        .where(ClaimModel.subject_entity_id == entity.id)
        .values(subject_entity_id=None, updated_at=datetime.now(UTC))
    )
    db.execute(delete(EntityMentionModel).where(EntityMentionModel.entity_id == entity.id))
    db.delete(entity)
    return snapshot


def _text_target_entity(db: Session, case_id: UUID, entity_id: UUID) -> tuple[EntityModel, dict]:
    entity = db.get(EntityModel, entity_id)
    if entity is None or entity.case_id != case_id:
        raise ReviewItemCleanupNotFoundError("Entity not found")
    source_validation_status = "source_valid" if _count_entity_mentions(db, entity.id) else "source_invalid"
    return entity, {
        "title": entity.canonical_name,
        "description": entity.description or "",
        "review_status": entity.review_status,
        "source_validation_status": source_validation_status,
    }


def _delete_contradiction_candidate(db: Session, case_id: UUID, candidate_id: UUID) -> dict:
    candidate = db.get(ContradictionCandidateModel, candidate_id)
    if candidate is None or candidate.case_id != case_id:
        raise ReviewItemCleanupNotFoundError("Contradiction candidate not found")
    source_count = _count_contradiction_sources(db, candidate.id)
    snapshot = {
        "title": candidate.title,
        "review_status": candidate.review_status,
        "source_validation_status": candidate.source_validation_status,
        "deleted_source_links": source_count,
    }
    _ensure_cleanup_allowed(snapshot)
    db.execute(delete(ContradictionCandidateSourceModel).where(ContradictionCandidateSourceModel.contradiction_candidate_id == candidate.id))
    db.delete(candidate)
    return snapshot


def _text_target_contradiction_candidate(db: Session, case_id: UUID, candidate_id: UUID) -> tuple[ContradictionCandidateModel, dict]:
    candidate = db.get(ContradictionCandidateModel, candidate_id)
    if candidate is None or candidate.case_id != case_id:
        raise ReviewItemCleanupNotFoundError("Contradiction candidate not found")
    return candidate, {
        "title": candidate.title,
        "description": candidate.description,
        "review_status": candidate.review_status,
        "source_validation_status": candidate.source_validation_status,
    }


def _delete_missing_item_candidate(db: Session, case_id: UUID, candidate_id: UUID) -> dict:
    candidate = db.get(MissingItemCandidateModel, candidate_id)
    if candidate is None or candidate.case_id != case_id:
        raise ReviewItemCleanupNotFoundError("Missing item candidate not found")
    source_count = _count_missing_item_sources(db, candidate.id)
    snapshot = {
        "title": candidate.referenced_item_text,
        "review_status": candidate.review_status,
        "source_validation_status": candidate.source_validation_status,
        "deleted_source_links": source_count,
    }
    _ensure_cleanup_allowed(snapshot)
    db.execute(delete(MissingItemCandidateSourceModel).where(MissingItemCandidateSourceModel.missing_item_candidate_id == candidate.id))
    db.delete(candidate)
    return snapshot


def _text_target_missing_item_candidate(db: Session, case_id: UUID, candidate_id: UUID) -> tuple[MissingItemCandidateModel, dict]:
    candidate = db.get(MissingItemCandidateModel, candidate_id)
    if candidate is None or candidate.case_id != case_id:
        raise ReviewItemCleanupNotFoundError("Missing item candidate not found")
    return candidate, {
        "title": candidate.referenced_item_text,
        "description": candidate.description,
        "review_status": candidate.review_status,
        "source_validation_status": candidate.source_validation_status,
    }


def _ensure_cleanup_allowed(snapshot: dict) -> None:
    if not _cleanup_allowed(snapshot["review_status"], snapshot["source_validation_status"]):
        raise ReviewItemCleanupError("Only corrected or source-invalid review report items can be deleted")


def _contradiction_candidate_ids_for_claim(db: Session, case_id: UUID, claim_id: UUID) -> list[UUID]:
    return list(
        db.execute(
            select(ContradictionCandidateModel.id).where(
                ContradictionCandidateModel.case_id == case_id,
                or_(ContradictionCandidateModel.claim_id_a == claim_id, ContradictionCandidateModel.claim_id_b == claim_id),
            )
        ).scalars()
    )


def _contradiction_candidate_ids_for_event(db: Session, case_id: UUID, event_id: UUID) -> list[UUID]:
    return list(
        db.execute(
            select(ContradictionCandidateModel.id).where(
                ContradictionCandidateModel.case_id == case_id,
                or_(ContradictionCandidateModel.event_id_a == event_id, ContradictionCandidateModel.event_id_b == event_id),
            )
        ).scalars()
    )


def _detach_claim_from_dependent_contradiction_candidates(db: Session, case_id: UUID, claim_id: UUID) -> None:
    candidates = list(
        db.execute(
            select(ContradictionCandidateModel).where(
                ContradictionCandidateModel.case_id == case_id,
                or_(ContradictionCandidateModel.claim_id_a == claim_id, ContradictionCandidateModel.claim_id_b == claim_id),
            )
        ).scalars()
    )
    now = datetime.now(UTC)
    for candidate in candidates:
        if candidate.claim_id_a == claim_id:
            candidate.claim_id_a = None
        if candidate.claim_id_b == claim_id:
            candidate.claim_id_b = None
        candidate.review_status = "corrected"
        candidate.updated_at = now
        db.add(candidate)


def _detach_event_from_dependent_contradiction_candidates(db: Session, case_id: UUID, event_id: UUID) -> None:
    candidates = list(
        db.execute(
            select(ContradictionCandidateModel).where(
                ContradictionCandidateModel.case_id == case_id,
                or_(ContradictionCandidateModel.event_id_a == event_id, ContradictionCandidateModel.event_id_b == event_id),
            )
        ).scalars()
    )
    now = datetime.now(UTC)
    for candidate in candidates:
        if candidate.event_id_a == event_id:
            candidate.event_id_a = None
        if candidate.event_id_b == event_id:
            candidate.event_id_b = None
        candidate.review_status = "corrected"
        candidate.updated_at = now
        db.add(candidate)


def _count_claim_sources(db: Session, claim_id: UUID) -> int:
    return int(db.scalar(select(func.count()).select_from(ClaimSourceModel).where(ClaimSourceModel.claim_id == claim_id)) or 0)


def _count_event_sources(db: Session, event_id: UUID) -> int:
    return int(db.scalar(select(func.count()).select_from(EventSourceModel).where(EventSourceModel.event_id == event_id)) or 0)


def _count_entity_mentions(db: Session, entity_id: UUID) -> int:
    return int(db.scalar(select(func.count()).select_from(EntityMentionModel).where(EntityMentionModel.entity_id == entity_id)) or 0)


def _count_contradiction_sources(db: Session, candidate_id: UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(ContradictionCandidateSourceModel)
            .where(ContradictionCandidateSourceModel.contradiction_candidate_id == candidate_id)
        )
        or 0
    )


def _count_missing_item_sources(db: Session, candidate_id: UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(MissingItemCandidateSourceModel)
            .where(MissingItemCandidateSourceModel.missing_item_candidate_id == candidate_id)
        )
        or 0
    )
