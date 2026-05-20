from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.research_finding import (
    ResearchFindingBulkDeleteRequest,
    ResearchFindingBulkDeleteResponse,
    ResearchFindingConvertRequest,
    ResearchFindingConvertResponse,
    ResearchFindingDetail,
    ResearchFindingList,
    ResearchFindingRead,
    ResearchFindingSetAsideRequest,
)
from app.schemas.source_reference import SourceReferenceRead
from app.services.research_findings import (
    ResearchFindingNotFoundError,
    ResearchFindingValidationError,
    convert_research_finding_to_manual_object,
    delete_research_finding,
    delete_research_findings,
    get_research_finding,
    list_research_findings,
    restore_research_finding,
    set_aside_research_finding,
)


router = APIRouter()


@router.get("/cases/{case_id}/research-findings", response_model=ResearchFindingList)
def get_case_research_findings(case_id: UUID, db: Session = Depends(get_db)) -> ResearchFindingList:
    return ResearchFindingList(data=[ResearchFindingRead.model_validate(finding) for finding in list_research_findings(db, case_id)])


@router.get("/cases/{case_id}/research-findings/{finding_id}", response_model=ResearchFindingDetail)
def get_case_research_finding(case_id: UUID, finding_id: UUID, db: Session = Depends(get_db)) -> ResearchFindingDetail:
    try:
        finding = get_research_finding(db, case_id, finding_id)
    except ResearchFindingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ResearchFindingDetail(finding=ResearchFindingRead.model_validate(finding))


@router.post(
    "/cases/{case_id}/research-findings/{finding_id}/convert",
    response_model=ResearchFindingConvertResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_research_finding_conversion(
    case_id: UUID,
    finding_id: UUID,
    payload: ResearchFindingConvertRequest,
    db: Session = Depends(get_db),
) -> ResearchFindingConvertResponse:
    try:
        finding, run_id, source_reference, object_type, object_id = convert_research_finding_to_manual_object(
            db,
            case_id,
            finding_id,
            payload,
        )
    except ResearchFindingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ResearchFindingValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ResearchFindingConvertResponse(
        analysis_run_id=run_id,
        source_reference=SourceReferenceRead.model_validate(source_reference),
        object_type=object_type,
        object_id=object_id,
        finding=ResearchFindingRead.model_validate(finding),
    )


@router.post("/cases/{case_id}/research-findings/{finding_id}/set-aside", response_model=ResearchFindingDetail)
def post_research_finding_set_aside(
    case_id: UUID,
    finding_id: UUID,
    payload: ResearchFindingSetAsideRequest,
    db: Session = Depends(get_db),
) -> ResearchFindingDetail:
    _ = payload
    try:
        finding = set_aside_research_finding(db, case_id=case_id, finding_id=finding_id)
    except ResearchFindingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ResearchFindingValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ResearchFindingDetail(finding=ResearchFindingRead.model_validate(finding))


@router.post("/cases/{case_id}/research-findings/{finding_id}/restore", response_model=ResearchFindingDetail)
def post_research_finding_restore(
    case_id: UUID,
    finding_id: UUID,
    db: Session = Depends(get_db),
) -> ResearchFindingDetail:
    try:
        finding = restore_research_finding(db, case_id=case_id, finding_id=finding_id)
    except ResearchFindingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ResearchFindingValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ResearchFindingDetail(finding=ResearchFindingRead.model_validate(finding))


@router.delete("/cases/{case_id}/research-findings/{finding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case_research_finding(case_id: UUID, finding_id: UUID, db: Session = Depends(get_db)) -> None:
    try:
        delete_research_finding(db, case_id=case_id, finding_id=finding_id)
    except ResearchFindingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ResearchFindingValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/cases/{case_id}/research-findings/bulk-delete", response_model=ResearchFindingBulkDeleteResponse)
def post_research_finding_bulk_delete(
    case_id: UUID,
    payload: ResearchFindingBulkDeleteRequest,
    db: Session = Depends(get_db),
) -> ResearchFindingBulkDeleteResponse:
    try:
        deleted_count = delete_research_findings(db, case_id=case_id, finding_ids=payload.finding_ids)
    except ResearchFindingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ResearchFindingValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ResearchFindingBulkDeleteResponse(deleted_count=deleted_count)
