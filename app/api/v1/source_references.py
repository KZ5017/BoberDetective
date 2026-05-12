from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.source_reference import (
    SourceReferenceCreate,
    SourceReferenceList,
    SourceReferenceRead,
    SourceReferenceValidateRequest,
    SourceReferenceValidateResponse,
    SourceReferenceValidationResult,
)
from app.services.source_references import (
    SourceReferenceNotFoundError,
    SourceReferenceValidationError,
    create_source_reference,
    get_source_reference,
    list_source_references,
    validate_source_references,
)

router = APIRouter()


@router.get("/cases/{case_id}/source-references", response_model=SourceReferenceList)
def get_source_references(case_id: UUID, db: Session = Depends(get_db)) -> SourceReferenceList:
    return SourceReferenceList(
        data=[SourceReferenceRead.model_validate(item) for item in list_source_references(db, case_id)]
    )


@router.post("/cases/{case_id}/source-references", response_model=SourceReferenceRead, status_code=status.HTTP_201_CREATED)
def post_source_reference(
    case_id: UUID,
    payload: SourceReferenceCreate,
    db: Session = Depends(get_db),
) -> SourceReferenceRead:
    try:
        source_reference = create_source_reference(db, case_id, payload)
    except SourceReferenceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SourceReferenceRead.model_validate(source_reference)


@router.get("/cases/{case_id}/source-references/{source_reference_id}", response_model=SourceReferenceRead)
def get_source_reference_endpoint(
    case_id: UUID,
    source_reference_id: UUID,
    db: Session = Depends(get_db),
) -> SourceReferenceRead:
    try:
        source_reference = get_source_reference(db, case_id, source_reference_id)
    except SourceReferenceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SourceReferenceRead.model_validate(source_reference)


@router.post("/cases/{case_id}/source-references/validate", response_model=SourceReferenceValidateResponse)
def post_source_reference_validation(
    case_id: UUID,
    payload: SourceReferenceValidateRequest,
    db: Session = Depends(get_db),
) -> SourceReferenceValidateResponse:
    validations = validate_source_references(db, case_id, payload.source_reference_ids)
    return SourceReferenceValidateResponse(
        data=[
            SourceReferenceValidationResult(
                source_reference_id=item.source_reference_id,
                is_valid=item.is_valid,
                errors=item.errors,
            )
            for item in validations
        ]
    )
