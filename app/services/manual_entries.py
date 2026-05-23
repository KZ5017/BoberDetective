from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.claim import ClaimModel, ClaimSourceModel
from app.models.detached_source import DetachedSourceItemModel
from app.models.entity import EntityMentionModel, EntityModel
from app.models.event import EventModel, EventSourceModel
from app.models.missing_item import MissingItemCandidateModel, MissingItemCandidateSourceModel
from app.models.review import HumanReviewModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.manual_entry import ManualObjectCreate, ManualObjectFields, ManualObjectFromSourceCreate, ManualSourceAttachmentCreate
from app.schemas.missing_item import MissingItemSourceCreate
from app.services.analysis_runs import add_analysis_run_input, add_analysis_run_output, finish_analysis_run, start_analysis_run
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.claims import create_claim_with_source
from app.services.entities import create_entity_with_mention
from app.services.events import create_event_with_source
from app.services.missing_items import create_missing_item_candidate
from app.services.source_references import create_source_reference_for_run
from app.services.storage import StoragePaths
from app.services.users import get_or_create_dev_user


class ManualEntryError(ValueError):
    pass


def create_manual_object(db: Session, case_id: UUID, payload: ManualObjectCreate) -> tuple[UUID, object, str, UUID]:
    run = _start_manual_run(db, case_id, payload)
    try:
        source_reference = create_source_reference_for_run(db, case_id, payload.source_reference, extraction_run_id=run.id)
        return _create_manual_object_for_source(db, case_id, payload, run, source_reference, "manual_source_selection")
    except Exception as exc:
        finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=str(exc))
        raise


def attach_manual_source_to_existing_object(
    db: Session,
    case_id: UUID,
    payload: ManualSourceAttachmentCreate,
) -> tuple[UUID, SourceReferenceModel, str, UUID, bool, bool]:
    _ensure_manual_source_is_not_already_attached(db, case_id, payload)
    run = _start_manual_run_for_target(db, case_id, payload.target_object_type)
    try:
        source_reference = create_source_reference_for_run(
            db,
            case_id,
            payload.source_reference,
            extraction_run_id=run.id,
            commit=False,
        )
        add_analysis_run_input(
            db,
            run.id,
            "chunk" if source_reference.chunk_id is not None else "page",
            0,
            document_id=source_reference.document_id,
            page_id=source_reference.page_id,
            chunk_id=source_reference.chunk_id,
            payload_json={
                "input_kind": "manual_source_attachment",
                "source_reference_id": str(source_reference.id),
                "target_object_type": payload.target_object_type,
                "target_object_id": str(payload.target_object_id),
                "quote_text": source_reference.quote_text,
            },
        )
        skipped_duplicate_source, target_reactivated = _attach_source_reference_to_existing_object(
            db,
            case_id=case_id,
            source_reference=source_reference,
            target_object_type=payload.target_object_type,
            target_object_id=payload.target_object_id,
            run_id=run.id,
        )
        add_analysis_run_output(db, run.id, "source_reference", source_reference.id, 0)
        add_analysis_run_output(db, run.id, payload.target_object_type, payload.target_object_id, 1)
        finish_analysis_run(
            db,
            run,
            status="succeeded",
            validation_status="passed",
            output_summary={
                "operation": "manual_source_attachment",
                "target_object_type": payload.target_object_type,
                "target_object_id": str(payload.target_object_id),
                "source_reference_id": str(source_reference.id),
                "skipped_duplicate_source": skipped_duplicate_source,
                "target_reactivated": target_reactivated,
            },
        )
        db.commit()
        db.refresh(source_reference)
        return run.id, source_reference, payload.target_object_type, payload.target_object_id, skipped_duplicate_source, target_reactivated
    except Exception as exc:
        db.rollback()
        finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=str(exc))
        raise


def create_manual_object_from_detached_source(
    db: Session,
    case_id: UUID,
    detached_source_item_id: UUID,
    payload: ManualObjectFromSourceCreate,
) -> tuple[UUID, object, str, UUID]:
    item = db.get(DetachedSourceItemModel, detached_source_item_id)
    if item is None or item.case_id != case_id:
        raise ManualEntryError("Detached source item not found")
    if item.handling_status != "needs_review":
        raise ManualEntryError("Detached source item has already been handled")
    source_reference = db.get(SourceReferenceModel, item.source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise ManualEntryError("Detached source reference not found for this case")

    run = _start_manual_run(db, case_id, payload)
    try:
        run_id, source_reference, object_type, object_id = _create_manual_object_for_source(
            db,
            case_id,
            payload,
            run,
            source_reference,
            "manual_detached_source_selection",
        )
        item.handling_status = "reattached"
        item.reattached_to_object_type = object_type
        item.reattached_to_object_id = object_id
        item.reattached_to_object_title_snapshot = _manual_object_title(payload)
        db.add(item)
        db.commit()
        db.refresh(item)
        return run_id, source_reference, object_type, object_id
    except Exception as exc:
        finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=str(exc))
        raise


def create_manual_object_from_source_reference(
    db: Session,
    case_id: UUID,
    source_reference_id: UUID,
    payload: ManualObjectFromSourceCreate,
    input_kind: str = "manual_existing_source_selection",
) -> tuple[UUID, SourceReferenceModel, str, UUID]:
    source_reference = db.get(SourceReferenceModel, source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise ManualEntryError("Source reference not found for this case")

    run = _start_manual_run(db, case_id, payload)
    try:
        return _create_manual_object_for_source(db, case_id, payload, run, source_reference, input_kind)
    except Exception as exc:
        finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=str(exc))
        raise


def _start_manual_run(db: Session, case_id: UUID, payload: ManualObjectFields):
    return _start_manual_run_for_target(db, case_id, payload.object_type)


def _start_manual_run_for_target(db: Session, case_id: UUID, object_type: str):
    run = start_analysis_run(
        db,
        case_id,
        "manual_entry",
        provider_type="human",
        model_name=None,
        input_parameters={"object_type": object_type},
        output_schema_name="manual_object",
        output_schema_version="v1",
        retrieval_strategy="user_selected_source",
    )
    return run


def _attach_source_reference_to_existing_object(
    db: Session,
    *,
    case_id: UUID,
    source_reference: SourceReferenceModel,
    target_object_type: str,
    target_object_id: UUID,
    run_id: UUID,
) -> tuple[bool, bool]:
    skipped_duplicate_source = False
    target_reactivated = False
    now = datetime.now(UTC)

    if target_object_type == "claim":
        target = db.get(ClaimModel, target_object_id)
        if target is None or target.case_id != case_id:
            raise ManualEntryError("Target claim not found for this case")
        previous_status = target.review_status
        target_reactivated = previous_status == "corrected"
        if target_reactivated:
            target.review_status = "needs_review"
        duplicate = db.execute(
            select(ClaimSourceModel).where(
                ClaimSourceModel.claim_id == target.id,
                ClaimSourceModel.source_reference_id == source_reference.id,
            )
        ).scalar_one_or_none()
        skipped_duplicate_source = duplicate is not None
        if not skipped_duplicate_source:
            db.add(ClaimSourceModel(claim_id=target.id, source_reference_id=source_reference.id, relevance_rank=None, support_type="direct"))
        target.source_validation_status = "source_valid"
        target.updated_at = now
        object_title = target.claim_title
    elif target_object_type == "entity":
        target = db.get(EntityModel, target_object_id)
        if target is None or target.case_id != case_id:
            raise ManualEntryError("Target entity not found for this case")
        previous_status = target.review_status
        target_reactivated = previous_status == "corrected"
        if target_reactivated:
            target.review_status = "needs_review"
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
                    created_by_analysis_run_id=run_id,
                )
            )
        target.updated_at = now
        object_title = target.canonical_name
    elif target_object_type == "event":
        target = db.get(EventModel, target_object_id)
        if target is None or target.case_id != case_id:
            raise ManualEntryError("Target event not found for this case")
        previous_status = target.review_status
        target_reactivated = previous_status == "corrected"
        if target_reactivated:
            target.review_status = "needs_review"
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
        target.updated_at = now
        object_title = target.event_title
    elif target_object_type == "missing_item_candidate":
        target = db.get(MissingItemCandidateModel, target_object_id)
        if target is None or target.case_id != case_id:
            raise ManualEntryError("Target missing item candidate not found for this case")
        previous_status = target.review_status
        target_reactivated = previous_status == "corrected"
        if target_reactivated:
            target.review_status = "needs_review"
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
        target.updated_at = now
        object_title = target.referenced_item_text
    else:
        raise ManualEntryError("Unsupported target object type")

    db.add(target)
    db.flush()
    user = get_or_create_dev_user(db)
    review = HumanReviewModel(
        case_id=case_id,
        object_type=target_object_type,
        object_id=target_object_id,
        action_type="attach_source",
        previous_review_status=previous_status,
        new_review_status="needs_review" if target_reactivated else None,
        review_comment=f"Kézi forráshivatkozás csatolva: {object_title}",
        correction_patch_json={
            "operation": "manual_source_attachment",
            "source_reference_id": str(source_reference.id),
            "skipped_duplicate_source": skipped_duplicate_source,
            "target_reactivated": target_reactivated,
        },
        performed_by_user_id=user.id,
    )
    db.add(review)
    db.flush()
    audit_event = AuditEvent(
        event_type="manual_source_attached",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        analysis_run_id=str(run_id),
        related_object_type=target_object_type,
        related_object_id=str(target_object_id),
        related_document_id=str(source_reference.document_id),
        related_page_id=str(source_reference.page_id) if source_reference.page_id is not None else None,
        related_chunk_id=str(source_reference.chunk_id) if source_reference.chunk_id is not None else None,
        input_summary={"source_reference_id": str(source_reference.id), "target_object_type": target_object_type},
        output_summary={
            "human_review_id": str(review.id),
            "skipped_duplicate_source": skipped_duplicate_source,
            "target_reactivated": target_reactivated,
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    return skipped_duplicate_source, target_reactivated


def _ensure_manual_source_is_not_already_attached(
    db: Session,
    case_id: UUID,
    payload: ManualSourceAttachmentCreate,
) -> None:
    source = payload.source_reference
    if payload.target_object_type == "claim":
        target = db.get(ClaimModel, payload.target_object_id)
        if target is None or target.case_id != case_id:
            raise ManualEntryError("Target claim not found for this case")
        query = (
            select(ClaimSourceModel.id)
            .join(SourceReferenceModel, ClaimSourceModel.source_reference_id == SourceReferenceModel.id)
            .where(ClaimSourceModel.claim_id == target.id)
        )
    elif payload.target_object_type == "entity":
        target = db.get(EntityModel, payload.target_object_id)
        if target is None or target.case_id != case_id:
            raise ManualEntryError("Target entity not found for this case")
        query = (
            select(EntityMentionModel.id)
            .join(SourceReferenceModel, EntityMentionModel.source_reference_id == SourceReferenceModel.id)
            .where(EntityMentionModel.entity_id == target.id)
        )
    elif payload.target_object_type == "event":
        target = db.get(EventModel, payload.target_object_id)
        if target is None or target.case_id != case_id:
            raise ManualEntryError("Target event not found for this case")
        query = (
            select(EventSourceModel.id)
            .join(SourceReferenceModel, EventSourceModel.source_reference_id == SourceReferenceModel.id)
            .where(EventSourceModel.event_id == target.id)
        )
    elif payload.target_object_type == "missing_item_candidate":
        target = db.get(MissingItemCandidateModel, payload.target_object_id)
        if target is None or target.case_id != case_id:
            raise ManualEntryError("Target missing item candidate not found for this case")
        query = (
            select(MissingItemCandidateSourceModel.id)
            .join(SourceReferenceModel, MissingItemCandidateSourceModel.source_reference_id == SourceReferenceModel.id)
            .where(MissingItemCandidateSourceModel.missing_item_candidate_id == target.id)
        )
    else:
        raise ManualEntryError("Unsupported target object type")

    duplicate = db.execute(
        query.where(
            SourceReferenceModel.case_id == case_id,
            SourceReferenceModel.document_id == source.document_id,
            SourceReferenceModel.page_id.is_(None) if source.page_id is None else SourceReferenceModel.page_id == source.page_id,
            SourceReferenceModel.chunk_id.is_(None) if source.chunk_id is None else SourceReferenceModel.chunk_id == source.chunk_id,
            SourceReferenceModel.quote_text == source.quote_text,
            SourceReferenceModel.quote_char_start == source.quote_char_start,
            SourceReferenceModel.quote_char_end == source.quote_char_end,
        ).limit(1)
    ).scalar_one_or_none()
    if duplicate is not None:
        raise ManualEntryError("This exact source reference is already attached to the selected target")


def _create_manual_object_for_source(
    db: Session,
    case_id: UUID,
    payload: ManualObjectFields,
    run,
    source_reference: SourceReferenceModel,
    input_kind: str,
) -> tuple[UUID, SourceReferenceModel, str, UUID]:
    add_analysis_run_input(
        db,
        run.id,
        "chunk" if source_reference.chunk_id is not None else "page",
        0,
        document_id=source_reference.document_id,
        page_id=source_reference.page_id,
        chunk_id=source_reference.chunk_id,
        payload_json={
            "input_kind": input_kind,
            "source_reference_id": str(source_reference.id),
            "quote_text": source_reference.quote_text,
        },
    )

    if payload.object_type == "claim":
        created = create_claim_with_source(
            db,
            case_id=case_id,
            claim_title=payload.claim_title or "",
            claim_text=payload.claim_text or "",
            claim_type=payload.claim_type,
            source_reference_id=source_reference.id,
            analysis_run_id=run.id,
        )
        object_id = created.id
    elif payload.object_type == "entity":
        created, _mention = create_entity_with_mention(
            db,
            case_id=case_id,
            entity_type=payload.entity_type or "other",
            canonical_name=payload.canonical_name or "",
            normalized_value=payload.normalized_value,
            description=payload.description,
            surface_text=source_reference.quote_text,
            source_reference_id=source_reference.id,
            analysis_run_id=run.id,
        )
        object_id = created.id
    elif payload.object_type == "event":
        created = create_event_with_source(
            db,
            case_id=case_id,
            event_type=payload.event_type or "other",
            event_title=payload.event_title or "",
            event_description=payload.event_description,
            event_time_start=payload.event_time_start,
            time_precision=payload.time_precision or "unknown",
            source_reference_id=source_reference.id,
            analysis_run_id=run.id,
        )
        object_id = created.id
    elif payload.object_type == "missing_item_candidate":
        created = create_missing_item_candidate(
            db,
            case_id=case_id,
            missing_item_type=payload.missing_item_type or "other",
            referenced_item_text=payload.referenced_item_text or "",
            description=payload.description or "",
            confidence=payload.confidence,
            analysis_run_id=run.id,
            sources=[MissingItemSourceCreate(source_reference_id=source_reference.id)],
        )
        object_id = created.id
    else:
        raise ManualEntryError("Unsupported manual object type")

    add_analysis_run_output(db, run.id, "source_reference", source_reference.id, 0)
    add_analysis_run_output(db, run.id, payload.object_type, object_id, 1)
    finish_analysis_run(
        db,
        run,
        status="succeeded",
        validation_status="passed",
        output_summary={"object_type": payload.object_type, "object_id": str(object_id), "source_reference_id": str(source_reference.id)},
    )
    return run.id, source_reference, payload.object_type, object_id


def _manual_object_title(payload: ManualObjectFields) -> str:
    if payload.object_type == "claim":
        return payload.claim_title or payload.claim_text or "Allitas"
    if payload.object_type == "entity":
        return payload.canonical_name or "Entitas"
    if payload.object_type == "event":
        return payload.event_title or "Esemeny"
    return payload.referenced_item_text or "Hianyzo irat jelolt"
