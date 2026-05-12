from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.export import ExportCreate, ExportDetail, ExportItemRead, ExportList, ExportRead
from app.schemas.review import HumanReviewCreate, HumanReviewRead
from app.services.exports import (
    ExportError,
    ExportNotFoundError,
    create_review_report_export,
    export_file_path,
    get_export,
    list_export_items,
    list_export_reviews,
    list_exports,
    review_export,
)

router = APIRouter()


@router.get("/cases/{case_id}/exports", response_model=ExportList)
def get_case_exports(case_id: UUID, db: Session = Depends(get_db)) -> ExportList:
    return ExportList(data=[ExportRead.model_validate(export) for export in list_exports(db, case_id)])


@router.post("/cases/{case_id}/exports", response_model=ExportDetail, status_code=status.HTTP_201_CREATED)
def post_case_export(case_id: UUID, payload: ExportCreate, db: Session = Depends(get_db)) -> ExportDetail:
    try:
        export = create_review_report_export(db, case_id, payload)
    except ExportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _export_detail(db, export.id, export)


@router.get("/cases/{case_id}/exports/{export_id}", response_model=ExportDetail)
def get_case_export(case_id: UUID, export_id: UUID, db: Session = Depends(get_db)) -> ExportDetail:
    try:
        export = get_export(db, case_id, export_id)
    except ExportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _export_detail(db, export_id, export)


@router.post("/cases/{case_id}/exports/{export_id}/reviews", response_model=ExportDetail)
def post_export_review(
    case_id: UUID,
    export_id: UUID,
    payload: HumanReviewCreate,
    db: Session = Depends(get_db),
) -> ExportDetail:
    try:
        export = review_export(
            db,
            case_id=case_id,
            export_id=export_id,
            action_type=payload.action_type,
            review_comment=payload.review_comment,
        )
    except ExportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ExportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _export_detail(db, export_id, export)


@router.get("/cases/{case_id}/exports/{export_id}/download")
def download_case_export(case_id: UUID, export_id: UUID, db: Session = Depends(get_db)) -> FileResponse:
    try:
        export = get_export(db, case_id, export_id)
        path = export_file_path(export)
    except ExportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ExportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return FileResponse(path, media_type="application/json", filename=f"{export.id}.json")


def _export_detail(db: Session, export_id: UUID, export) -> ExportDetail:
    return ExportDetail(
        export=ExportRead.model_validate(export),
        items=[ExportItemRead.model_validate(item) for item in list_export_items(db, export_id)],
        reviews=[HumanReviewRead.model_validate(review) for review in list_export_reviews(db, export_id)],
    )
