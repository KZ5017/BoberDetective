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
from app.services.detached_sources import create_detached_source_item
from app.services.reviews import list_object_reviews, record_object_review, review_status_for_action
from app.services.source_references import ensure_source_reference_document_is_active
from app.services.storage import StoragePaths
from app.services.users import get_or_create_dev_user


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


def merge_missing_item_candidate(
    db: Session,
    *,
    case_id: UUID,
    source_candidate_id: UUID,
    target_candidate_id: UUID,
    review_comment: str | None = None,
) -> MissingItemCandidateModel:
    if source_candidate_id == target_candidate_id:
        raise MissingItemCandidateValidationError("Source and target missing item candidate must be different")

    source_candidate = get_missing_item_candidate(db, case_id, source_candidate_id)
    target_candidate = get_missing_item_candidate(db, case_id, target_candidate_id)
    if target_candidate.review_status == "corrected":
        raise MissingItemCandidateValidationError("Corrected missing item candidates cannot be merge targets")
    if source_candidate.source_validation_status == "source_invalid":
        raise MissingItemCandidateValidationError("Missing item candidates without valid sources cannot be merged")
    if target_candidate.source_validation_status == "source_invalid":
        raise MissingItemCandidateValidationError("Missing item candidates without valid sources cannot be merge targets")
    source_candidate_sources = list_missing_item_candidate_sources(db, source_candidate.id)
    target_candidate_sources = list_missing_item_candidate_sources(db, target_candidate.id)
    if not source_candidate_sources:
        raise MissingItemCandidateValidationError("Missing item candidates without valid sources cannot be merged")
    if not target_candidate_sources:
        raise MissingItemCandidateValidationError("Missing item candidates without valid sources cannot be merge targets")
    _ensure_missing_item_candidate_sources_have_active_documents(db, case_id, source_candidate_sources + target_candidate_sources)

    target_source_reference_ids = {
        source.source_reference_id
        for source in db.execute(
            select(MissingItemCandidateSourceModel).where(
                MissingItemCandidateSourceModel.missing_item_candidate_id == target_candidate.id
            )
        ).scalars()
    }
    moved_source_count = 0
    skipped_duplicate_source_count = 0
    for source in source_candidate_sources:
        if source.source_reference_id in target_source_reference_ids:
            db.delete(source)
            skipped_duplicate_source_count += 1
            continue
        source.missing_item_candidate_id = target_candidate.id
        db.add(source)
        target_source_reference_ids.add(source.source_reference_id)
        moved_source_count += 1

    previous_source_status = source_candidate.review_status
    source_candidate.review_status = "corrected"
    source_candidate.updated_at = datetime.now(UTC)
    target_candidate.updated_at = datetime.now(UTC)
    db.add(source_candidate)
    db.add(target_candidate)

    user = get_or_create_dev_user(db)
    source_review = HumanReviewModel(
        case_id=case_id,
        object_type="missing_item_candidate",
        object_id=source_candidate.id,
        action_type="correct",
        previous_review_status=previous_source_status,
        new_review_status="corrected",
        review_comment=review_comment or f"Hianyzo irat jelolt osszevonva: {target_candidate.referenced_item_text}",
        correction_patch_json={
            "operation": "merge_into",
            "target_missing_item_candidate_id": str(target_candidate.id),
            "moved_source_count": moved_source_count,
            "skipped_duplicate_source_count": skipped_duplicate_source_count,
        },
        performed_by_user_id=user.id,
    )
    target_review = HumanReviewModel(
        case_id=case_id,
        object_type="missing_item_candidate",
        object_id=target_candidate.id,
        action_type="attach_source",
        previous_review_status=target_candidate.review_status,
        new_review_status=None,
        review_comment=review_comment or f"Hianyzo irat jelolt forrasai hozzaadva: {source_candidate.referenced_item_text}",
        correction_patch_json={
            "operation": "merge_from",
            "source_missing_item_candidate_id": str(source_candidate.id),
            "moved_source_count": moved_source_count,
            "skipped_duplicate_source_count": skipped_duplicate_source_count,
        },
        performed_by_user_id=user.id,
    )
    db.add(source_review)
    db.add(target_review)
    db.flush()

    audit_event = AuditEvent(
        event_type="missing_item_candidate_merged",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="missing_item_candidate",
        related_object_id=str(target_candidate.id),
        input_summary={
            "source_missing_item_candidate_id": str(source_candidate.id),
            "target_missing_item_candidate_id": str(target_candidate.id),
            "source_review_status": previous_source_status,
        },
        output_summary={
            "target_missing_item_candidate_id": str(target_candidate.id),
            "source_candidate_new_review_status": source_candidate.review_status,
            "moved_source_count": moved_source_count,
            "skipped_duplicate_source_count": skipped_duplicate_source_count,
            "source_review_id": str(source_review.id),
            "target_review_id": str(target_review.id),
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(target_candidate)
    return target_candidate


def detach_missing_item_candidate_source(
    db: Session,
    *,
    case_id: UUID,
    missing_item_candidate_id: UUID,
    source_link_id: UUID,
    review_comment: str | None = None,
) -> MissingItemCandidateModel:
    candidate = get_missing_item_candidate(db, case_id, missing_item_candidate_id)
    source_link = db.get(MissingItemCandidateSourceModel, source_link_id)
    if source_link is None or source_link.missing_item_candidate_id != candidate.id:
        raise MissingItemCandidateValidationError("Missing item candidate source not found for this candidate")

    source_reference = db.get(SourceReferenceModel, source_link.source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise MissingItemCandidateValidationError("Missing item candidate source reference not found for this case")
    ensure_source_reference_document_is_active(db, case_id, source_reference, MissingItemCandidateValidationError)
    source_reference_id = source_link.source_reference_id
    db.delete(source_link)
    db.flush()
    remaining_source_count = len(list_missing_item_candidate_sources(db, candidate.id))
    if remaining_source_count <= 0:
        candidate.source_validation_status = "source_invalid"
    candidate.updated_at = datetime.now(UTC)
    db.add(candidate)

    user = get_or_create_dev_user(db)
    detached_item = create_detached_source_item(
        db,
        case_id=case_id,
        source_reference=source_reference,
        detached_from_object_type="missing_item_candidate",
        detached_from_object_id=candidate.id,
        detached_from_source_link_id=source_link_id,
        detached_from_source_link_type="missing_item_candidate_source",
        object_title_snapshot=candidate.referenced_item_text,
        object_body_snapshot=candidate.description,
        object_subtype_snapshot=candidate.missing_item_type,
        object_review_status_snapshot=candidate.review_status,
        source_validation_status_snapshot=candidate.source_validation_status,
        detach_comment=review_comment,
        detached_by_user_id=user.id,
    )
    review = HumanReviewModel(
        case_id=case_id,
        object_type="missing_item_candidate",
        object_id=candidate.id,
        action_type="detach_source",
        previous_review_status=candidate.review_status,
        new_review_status=None,
        review_comment=review_comment or "Hianyzo irat jelolt forrasa levalasztva.",
        correction_patch_json={
            "operation": "detach_source",
            "missing_item_candidate_source_id": str(source_link_id),
            "source_reference_id": str(source_reference_id),
            "detached_source_item_id": str(detached_item.id),
        },
        performed_by_user_id=user.id,
    )
    db.add(review)
    db.flush()

    audit_event = AuditEvent(
        event_type="missing_item_candidate_source_detached",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="missing_item_candidate",
        related_object_id=str(candidate.id),
        related_document_id=str(source_reference.document_id) if source_reference is not None else None,
        related_page_id=str(source_reference.page_id) if source_reference is not None and source_reference.page_id is not None else None,
        related_chunk_id=str(source_reference.chunk_id) if source_reference is not None and source_reference.chunk_id is not None else None,
        input_summary={"missing_item_candidate_source_id": str(source_link_id), "source_reference_id": str(source_reference_id)},
        output_summary={
            "human_review_id": str(review.id),
            "detached_source_item_id": str(detached_item.id),
            "remaining_source_count": remaining_source_count,
            "source_validation_status": candidate.source_validation_status,
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(candidate)
    return candidate


def move_missing_item_candidate_source(
    db: Session,
    *,
    case_id: UUID,
    source_candidate_id: UUID,
    source_link_id: UUID,
    target_candidate_id: UUID,
    review_comment: str | None = None,
) -> MissingItemCandidateModel:
    if source_candidate_id == target_candidate_id:
        raise MissingItemCandidateValidationError("Source and target missing item candidate must be different")

    source_candidate = get_missing_item_candidate(db, case_id, source_candidate_id)
    target_candidate = get_missing_item_candidate(db, case_id, target_candidate_id)
    source_link = db.get(MissingItemCandidateSourceModel, source_link_id)
    if source_link is None or source_link.missing_item_candidate_id != source_candidate.id:
        raise MissingItemCandidateValidationError("Missing item candidate source not found for this candidate")
    source_reference = db.get(SourceReferenceModel, source_link.source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise MissingItemCandidateValidationError("Missing item candidate source reference not found for this case")
    ensure_source_reference_document_is_active(db, case_id, source_reference, MissingItemCandidateValidationError)
    _ensure_missing_item_candidate_sources_have_active_documents(
        db,
        case_id,
        list_missing_item_candidate_sources(db, target_candidate.id),
    )

    previous_target_status = target_candidate.review_status
    target_reactivated = previous_target_status == "corrected"
    if target_reactivated:
        target_candidate.review_status = "needs_review"

    duplicate = db.execute(
        select(MissingItemCandidateSourceModel).where(
            MissingItemCandidateSourceModel.missing_item_candidate_id == target_candidate.id,
            MissingItemCandidateSourceModel.source_reference_id == source_link.source_reference_id,
        )
    ).scalar_one_or_none()
    skipped_duplicate_source = duplicate is not None
    if skipped_duplicate_source:
        db.delete(source_link)
    else:
        source_link.missing_item_candidate_id = target_candidate.id
        db.add(source_link)

    db.flush()
    remaining_source_count = len(list_missing_item_candidate_sources(db, source_candidate.id))
    if remaining_source_count <= 0:
        source_candidate.source_validation_status = "source_invalid"
    target_candidate.source_validation_status = "source_valid"
    source_candidate.updated_at = datetime.now(UTC)
    target_candidate.updated_at = datetime.now(UTC)
    db.add(source_candidate)
    db.add(target_candidate)

    user = get_or_create_dev_user(db)
    source_review = HumanReviewModel(
        case_id=case_id,
        object_type="missing_item_candidate",
        object_id=source_candidate.id,
        action_type="detach_source",
        previous_review_status=source_candidate.review_status,
        new_review_status=None,
        review_comment=review_comment or f"Hianyzo irat jelolt forrasa athelyezve: {target_candidate.referenced_item_text}",
        correction_patch_json={
            "operation": "move_source_to",
            "missing_item_candidate_source_id": str(source_link_id),
            "target_missing_item_candidate_id": str(target_candidate.id),
            "skipped_duplicate_source": skipped_duplicate_source,
        },
        performed_by_user_id=user.id,
    )
    target_review = HumanReviewModel(
        case_id=case_id,
        object_type="missing_item_candidate",
        object_id=target_candidate.id,
        action_type="attach_source",
        previous_review_status=previous_target_status,
        new_review_status=target_candidate.review_status if target_reactivated else None,
        review_comment=review_comment or f"Hianyzo irat jelolt forrasa atveve: {source_candidate.referenced_item_text}",
        correction_patch_json={
            "operation": "move_source_from",
            "missing_item_candidate_source_id": str(source_link_id),
            "source_missing_item_candidate_id": str(source_candidate.id),
            "skipped_duplicate_source": skipped_duplicate_source,
            "reactivated_corrected_target": target_reactivated,
        },
        performed_by_user_id=user.id,
    )
    db.add(source_review)
    db.add(target_review)
    db.flush()

    audit_event = AuditEvent(
        event_type="missing_item_candidate_source_moved",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="missing_item_candidate",
        related_object_id=str(target_candidate.id),
        input_summary={
            "source_missing_item_candidate_id": str(source_candidate.id),
            "target_missing_item_candidate_id": str(target_candidate.id),
            "missing_item_candidate_source_id": str(source_link_id),
        },
        output_summary={
            "source_review_id": str(source_review.id),
            "target_review_id": str(target_review.id),
            "skipped_duplicate_source": skipped_duplicate_source,
            "remaining_source_count": remaining_source_count,
            "target_previous_review_status": previous_target_status if target_reactivated else None,
            "target_new_review_status": target_candidate.review_status if target_reactivated else None,
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(target_candidate)
    return target_candidate


def _get_case_source_reference(db: Session, case_id: UUID, source_reference_id: UUID) -> SourceReferenceModel:
    source_reference = db.get(SourceReferenceModel, source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise MissingItemCandidateValidationError("Source reference not found for this case")
    ensure_source_reference_document_is_active(db, case_id, source_reference, MissingItemCandidateValidationError)
    return source_reference


def _review_status_for_action(action_type: str, previous_status: str) -> str | None:
    return review_status_for_action(action_type, previous_status, MissingItemCandidateValidationError)


def _ensure_missing_item_candidate_sources_have_active_documents(
    db: Session,
    case_id: UUID,
    sources: list[MissingItemCandidateSourceModel],
) -> None:
    for source in sources:
        source_reference = db.get(SourceReferenceModel, source.source_reference_id)
        if source_reference is None or source_reference.case_id != case_id:
            raise MissingItemCandidateValidationError("Missing item candidate source reference not found for this case")
        ensure_source_reference_document_is_active(db, case_id, source_reference, MissingItemCandidateValidationError)
