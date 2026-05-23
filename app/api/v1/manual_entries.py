from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.manual_entry import (
    ManualObjectCreate,
    ManualObjectCreateResponse,
    ManualObjectFromSourceCreate,
    ManualSourceAttachmentCreate,
    ManualSourceAttachmentResponse,
)
from app.schemas.source_reference import SourceReferenceRead
from app.services.manual_entries import ManualEntryError, attach_manual_source_to_existing_object, create_manual_object, create_manual_object_from_detached_source
from app.services.source_references import SourceReferenceValidationError

router = APIRouter()


@router.post("/cases/{case_id}/manual-objects", response_model=ManualObjectCreateResponse, status_code=status.HTTP_201_CREATED)
def post_manual_object(case_id: UUID, payload: ManualObjectCreate, db: Session = Depends(get_db)) -> ManualObjectCreateResponse:
    try:
        run_id, source_reference, object_type, object_id = create_manual_object(db, case_id, payload)
    except (ManualEntryError, SourceReferenceValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ManualObjectCreateResponse(
        analysis_run_id=run_id,
        source_reference=SourceReferenceRead.model_validate(source_reference),
        object_type=object_type,
        object_id=object_id,
    )


@router.post(
    "/cases/{case_id}/manual-source-attachments",
    response_model=ManualSourceAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_manual_source_attachment(
    case_id: UUID,
    payload: ManualSourceAttachmentCreate,
    db: Session = Depends(get_db),
) -> ManualSourceAttachmentResponse:
    try:
        run_id, source_reference, target_object_type, target_object_id, skipped_duplicate_source, target_reactivated = attach_manual_source_to_existing_object(
            db,
            case_id,
            payload,
        )
    except (ManualEntryError, SourceReferenceValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ManualSourceAttachmentResponse(
        analysis_run_id=run_id,
        source_reference=SourceReferenceRead.model_validate(source_reference),
        target_object_type=target_object_type,
        target_object_id=target_object_id,
        skipped_duplicate_source=skipped_duplicate_source,
        target_reactivated=target_reactivated,
    )


@router.post(
    "/cases/{case_id}/detached-source-items/{item_id}/manual-object",
    response_model=ManualObjectCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_manual_object_from_detached_source(
    case_id: UUID,
    item_id: UUID,
    payload: ManualObjectFromSourceCreate,
    db: Session = Depends(get_db),
) -> ManualObjectCreateResponse:
    try:
        run_id, source_reference, object_type, object_id = create_manual_object_from_detached_source(db, case_id, item_id, payload)
    except (ManualEntryError, SourceReferenceValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ManualObjectCreateResponse(
        analysis_run_id=run_id,
        source_reference=SourceReferenceRead.model_validate(source_reference),
        object_type=object_type,
        object_id=object_id,
    )
