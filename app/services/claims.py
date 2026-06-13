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
from app.services.detached_sources import create_detached_source_item
from app.services.reviews import list_object_reviews, record_object_review, review_status_for_action
from app.services.source_references import ensure_source_reference_document_is_active
from app.services.storage import StoragePaths
from app.services.users import get_or_create_dev_user


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


def merge_claim(
    db: Session,
    *,
    case_id: UUID,
    source_claim_id: UUID,
    target_claim_id: UUID,
    review_comment: str | None = None,
) -> ClaimModel:
    if source_claim_id == target_claim_id:
        raise ClaimValidationError("Source and target claim must be different")

    source_claim = get_claim(db, case_id, source_claim_id)
    target_claim = get_claim(db, case_id, target_claim_id)
    if target_claim.review_status == "corrected":
        raise ClaimValidationError("Corrected claims cannot be merge targets")
    if source_claim.source_validation_status == "source_invalid":
        raise ClaimValidationError("Claims without valid sources cannot be merged")
    if target_claim.source_validation_status == "source_invalid":
        raise ClaimValidationError("Claims without valid sources cannot be merge targets")
    source_claim_sources = list_claim_sources(db, source_claim.id)
    target_claim_sources = list_claim_sources(db, target_claim.id)
    if not source_claim_sources:
        raise ClaimValidationError("Claims without valid sources cannot be merged")
    if not target_claim_sources:
        raise ClaimValidationError("Claims without valid sources cannot be merge targets")
    _ensure_claim_sources_have_active_documents(db, case_id, source_claim_sources + target_claim_sources)

    target_source_reference_ids = {
        source.source_reference_id
        for source in db.execute(select(ClaimSourceModel).where(ClaimSourceModel.claim_id == target_claim.id)).scalars()
    }
    moved_source_count = 0
    skipped_duplicate_source_count = 0
    for source in source_claim_sources:
        if source.source_reference_id in target_source_reference_ids:
            db.delete(source)
            skipped_duplicate_source_count += 1
            continue
        source.claim_id = target_claim.id
        db.add(source)
        target_source_reference_ids.add(source.source_reference_id)
        moved_source_count += 1

    previous_source_status = source_claim.review_status
    source_claim.review_status = "corrected"
    source_claim.source_validation_status = "source_invalid"
    source_claim.updated_at = datetime.now(UTC)
    target_claim.updated_at = datetime.now(UTC)
    db.add(source_claim)
    db.add(target_claim)

    user = get_or_create_dev_user(db)
    source_review = HumanReviewModel(
        case_id=case_id,
        object_type="claim",
        object_id=source_claim.id,
        action_type="correct",
        previous_review_status=previous_source_status,
        new_review_status="corrected",
        review_comment=review_comment or f"Allitas osszevonva: {target_claim.claim_title}",
        correction_patch_json={
            "operation": "merge_into",
            "target_claim_id": str(target_claim.id),
            "moved_source_count": moved_source_count,
            "skipped_duplicate_source_count": skipped_duplicate_source_count,
        },
        performed_by_user_id=user.id,
    )
    target_review = HumanReviewModel(
        case_id=case_id,
        object_type="claim",
        object_id=target_claim.id,
        action_type="attach_source",
        previous_review_status=target_claim.review_status,
        new_review_status=None,
        review_comment=review_comment or f"Allitas forrasai hozzaadva: {source_claim.claim_title}",
        correction_patch_json={
            "operation": "merge_from",
            "source_claim_id": str(source_claim.id),
            "moved_source_count": moved_source_count,
            "skipped_duplicate_source_count": skipped_duplicate_source_count,
        },
        performed_by_user_id=user.id,
    )
    db.add(source_review)
    db.add(target_review)
    db.flush()

    audit_event = AuditEvent(
        event_type="claim_merged",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="claim",
        related_object_id=str(target_claim.id),
        input_summary={
            "source_claim_id": str(source_claim.id),
            "target_claim_id": str(target_claim.id),
            "source_review_status": previous_source_status,
        },
        output_summary={
            "source_review_id": str(source_review.id),
            "target_review_id": str(target_review.id),
            "moved_source_count": moved_source_count,
            "skipped_duplicate_source_count": skipped_duplicate_source_count,
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(target_claim)
    return target_claim


def detach_claim_source(
    db: Session,
    *,
    case_id: UUID,
    claim_id: UUID,
    claim_source_id: UUID,
    review_comment: str | None = None,
) -> ClaimModel:
    claim = get_claim(db, case_id, claim_id)
    source_link = db.get(ClaimSourceModel, claim_source_id)
    if source_link is None or source_link.claim_id != claim.id:
        raise ClaimValidationError("Claim source not found for this claim")

    source_reference = db.get(SourceReferenceModel, source_link.source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise ClaimValidationError("Claim source reference not found for this case")
    ensure_source_reference_document_is_active(db, case_id, source_reference, ClaimValidationError)
    source_reference_id = source_link.source_reference_id
    previous_review_status = claim.review_status
    db.delete(source_link)
    db.flush()
    remaining_source_count = len(list_claim_sources(db, claim.id))
    orphaned_by_detach = remaining_source_count <= 0
    if remaining_source_count <= 0:
        claim.review_status = "corrected"
        claim.source_validation_status = "source_invalid"
    claim.updated_at = datetime.now(UTC)
    db.add(claim)

    user = get_or_create_dev_user(db)
    detached_item = create_detached_source_item(
        db,
        case_id=case_id,
        source_reference=source_reference,
        detached_from_object_type="claim",
        detached_from_object_id=claim.id,
        detached_from_source_link_id=claim_source_id,
        detached_from_source_link_type="claim_source",
        object_title_snapshot=claim.claim_title,
        object_body_snapshot=claim.claim_text,
        object_subtype_snapshot=claim.claim_type,
        object_review_status_snapshot=claim.review_status,
        source_validation_status_snapshot=claim.source_validation_status,
        detach_comment=review_comment,
        detached_by_user_id=user.id,
    )
    review = HumanReviewModel(
        case_id=case_id,
        object_type="claim",
        object_id=claim.id,
        action_type="detach_source",
        previous_review_status=previous_review_status,
        new_review_status=claim.review_status if orphaned_by_detach else None,
        review_comment=review_comment or "Allitas forrasa levalasztva.",
        correction_patch_json={
            "operation": "detach_source",
            "claim_source_id": str(claim_source_id),
            "source_reference_id": str(source_reference_id),
            "detached_source_item_id": str(detached_item.id),
            "orphaned_by_detach": orphaned_by_detach,
        },
        performed_by_user_id=user.id,
    )
    db.add(review)
    db.flush()

    audit_event = AuditEvent(
        event_type="claim_source_detached",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="claim",
        related_object_id=str(claim.id),
        related_document_id=str(source_reference.document_id),
        related_page_id=str(source_reference.page_id) if source_reference.page_id is not None else None,
        related_chunk_id=str(source_reference.chunk_id) if source_reference.chunk_id is not None else None,
        input_summary={"claim_source_id": str(claim_source_id), "source_reference_id": str(source_reference_id)},
        output_summary={
            "human_review_id": str(review.id),
            "detached_source_item_id": str(detached_item.id),
            "remaining_source_count": max(0, remaining_source_count),
            "source_validation_status": claim.source_validation_status,
            "review_status": claim.review_status,
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(claim)
    return claim


def move_claim_source(
    db: Session,
    *,
    case_id: UUID,
    source_claim_id: UUID,
    claim_source_id: UUID,
    target_claim_id: UUID,
    review_comment: str | None = None,
) -> ClaimModel:
    if source_claim_id == target_claim_id:
        raise ClaimValidationError("Source and target claim must be different")

    source_claim = get_claim(db, case_id, source_claim_id)
    target_claim = get_claim(db, case_id, target_claim_id)

    source_link = db.get(ClaimSourceModel, claim_source_id)
    if source_link is None or source_link.claim_id != source_claim.id:
        raise ClaimValidationError("Claim source not found for this claim")
    source_reference = db.get(SourceReferenceModel, source_link.source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise ClaimValidationError("Claim source reference not found for this case")
    ensure_source_reference_document_is_active(db, case_id, source_reference, ClaimValidationError)
    _ensure_claim_sources_have_active_documents(db, case_id, list_claim_sources(db, target_claim.id))

    previous_target_status = target_claim.review_status
    previous_source_status = source_claim.review_status
    target_reactivated = previous_target_status == "corrected"
    if target_reactivated:
        target_claim.review_status = "needs_review"

    duplicate = db.execute(
        select(ClaimSourceModel).where(
            ClaimSourceModel.claim_id == target_claim.id,
            ClaimSourceModel.source_reference_id == source_link.source_reference_id,
        )
    ).scalar_one_or_none()
    skipped_duplicate_source = duplicate is not None
    if skipped_duplicate_source:
        db.delete(source_link)
    else:
        source_link.claim_id = target_claim.id
        db.add(source_link)

    db.flush()
    remaining_source_count = len(list_claim_sources(db, source_claim.id))
    orphaned_by_move = remaining_source_count <= 0
    if remaining_source_count <= 0:
        source_claim.review_status = "corrected"
        source_claim.source_validation_status = "source_invalid"
    target_claim.source_validation_status = "source_valid"
    source_claim.updated_at = datetime.now(UTC)
    target_claim.updated_at = datetime.now(UTC)
    db.add(source_claim)
    db.add(target_claim)

    user = get_or_create_dev_user(db)
    source_review = HumanReviewModel(
        case_id=case_id,
        object_type="claim",
        object_id=source_claim.id,
        action_type="detach_source",
        previous_review_status=previous_source_status,
        new_review_status=source_claim.review_status if orphaned_by_move else None,
        review_comment=review_comment or f"Allitas forrasa athelyezve: {target_claim.claim_title}",
        correction_patch_json={
            "operation": "move_source_to",
            "claim_source_id": str(claim_source_id),
            "target_claim_id": str(target_claim.id),
            "skipped_duplicate_source": skipped_duplicate_source,
            "orphaned_by_move": orphaned_by_move,
        },
        performed_by_user_id=user.id,
    )
    target_review = HumanReviewModel(
        case_id=case_id,
        object_type="claim",
        object_id=target_claim.id,
        action_type="attach_source",
        previous_review_status=previous_target_status,
        new_review_status=target_claim.review_status if target_reactivated else None,
        review_comment=review_comment or f"Allitas forrasa atveve: {source_claim.claim_title}",
        correction_patch_json={
            "operation": "move_source_from",
            "claim_source_id": str(claim_source_id),
            "source_claim_id": str(source_claim.id),
            "skipped_duplicate_source": skipped_duplicate_source,
            "reactivated_corrected_target": target_reactivated,
        },
        performed_by_user_id=user.id,
    )
    db.add(source_review)
    db.add(target_review)
    db.flush()

    audit_event = AuditEvent(
        event_type="claim_source_moved",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="claim",
        related_object_id=str(target_claim.id),
        related_document_id=str(source_reference.document_id),
        related_page_id=str(source_reference.page_id) if source_reference.page_id is not None else None,
        related_chunk_id=str(source_reference.chunk_id) if source_reference.chunk_id is not None else None,
        input_summary={
            "source_claim_id": str(source_claim.id),
            "target_claim_id": str(target_claim.id),
            "claim_source_id": str(claim_source_id),
        },
        output_summary={"source_review_id": str(source_review.id), "target_review_id": str(target_review.id)},
    )
    if target_reactivated:
        audit_event.output_summary["target_previous_review_status"] = previous_target_status
        audit_event.output_summary["target_new_review_status"] = target_claim.review_status
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(target_claim)
    return target_claim


def create_claim_with_source(
    db: Session,
    *,
    case_id: UUID,
    claim_text: str,
    source_reference_id: UUID,
    analysis_run_id: UUID,
    claim_title: str | None = None,
    claim_type: str = "document_fact",
    support_type: str = "direct",
    relevance_rank: int = 0,
) -> ClaimModel:
    if claim_text.strip() == "":
        raise ClaimValidationError("Claim text is required")
    normalized_title = claim_title.strip() if claim_title is not None else ""
    if normalized_title == "":
        normalized_title = _default_claim_title(claim_text)

    run = db.get(AnalysisRunModel, analysis_run_id)
    if run is None or run.case_id != case_id:
        raise ClaimValidationError("Analysis run not found for this case")

    source_reference = db.get(SourceReferenceModel, source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise ClaimValidationError("Source reference not found for this case")
    ensure_source_reference_document_is_active(db, case_id, source_reference, ClaimValidationError)

    claim = ClaimModel(
        case_id=case_id,
        claim_type=claim_type,
        claim_title=normalized_title,
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


def _default_claim_title(claim_text: str) -> str:
    text = " ".join(claim_text.strip().split())
    if len(text) <= 160:
        return text
    return f"{text[:157].rstrip()}..."


def _ensure_claim_sources_have_active_documents(db: Session, case_id: UUID, sources: list[ClaimSourceModel]) -> None:
    for source in sources:
        source_reference = db.get(SourceReferenceModel, source.source_reference_id)
        if source_reference is None or source_reference.case_id != case_id:
            raise ClaimValidationError("Claim source reference not found for this case")
        ensure_source_reference_document_is_active(db, case_id, source_reference, ClaimValidationError)
