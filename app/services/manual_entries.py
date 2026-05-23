from uuid import UUID

from sqlalchemy.orm import Session

from app.models.detached_source import DetachedSourceItemModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.manual_entry import ManualObjectCreate, ManualObjectFields, ManualObjectFromSourceCreate
from app.schemas.missing_item import MissingItemSourceCreate
from app.services.analysis_runs import add_analysis_run_input, add_analysis_run_output, finish_analysis_run, start_analysis_run
from app.services.claims import create_claim_with_source
from app.services.entities import create_entity_with_mention
from app.services.events import create_event_with_source
from app.services.missing_items import create_missing_item_candidate
from app.services.source_references import create_source_reference_for_run


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
    run = start_analysis_run(
        db,
        case_id,
        "manual_entry",
        provider_type="human",
        model_name=None,
        input_parameters={"object_type": payload.object_type},
        output_schema_name="manual_object",
        output_schema_version="v1",
        retrieval_strategy="user_selected_source",
    )
    return run


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
