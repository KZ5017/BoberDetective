from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.review_report import CaseReviewReport, ReviewReportFilters, ReviewReportItemTextUpdate
from app.services.review_item_cleanup import (
    ReviewItemCleanupError,
    ReviewItemCleanupNotFoundError,
    delete_review_report_item,
    update_review_report_item_text,
)
from app.services.review_report import ReviewReportValidationError, build_case_review_report

router = APIRouter()


@router.get("/cases/{case_id}/review-report", response_model=CaseReviewReport)
def get_case_review_report(
    case_id: UUID,
    object_type: list[str] | None = Query(default=None),
    review_status: list[str] | None = Query(default=None),
    source_validation_status: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> CaseReviewReport:
    try:
        return build_case_review_report(
            db,
            case_id,
            ReviewReportFilters(
                object_types=object_type,
                review_statuses=review_status,
                source_validation_statuses=source_validation_status,
            ),
        )
    except ReviewReportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/cases/{case_id}/review-report/items/{object_type}/{object_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case_review_report_item(
    case_id: UUID,
    object_type: str,
    object_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_review_report_item(db, case_id=case_id, object_type=object_type, object_id=object_id)
    except ReviewItemCleanupNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReviewItemCleanupError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/cases/{case_id}/review-report/items/{object_type}/{object_id}/text", status_code=status.HTTP_204_NO_CONTENT)
def patch_case_review_report_item_text(
    case_id: UUID,
    object_type: str,
    object_id: UUID,
    payload: ReviewReportItemTextUpdate,
    db: Session = Depends(get_db),
) -> None:
    try:
        update_review_report_item_text(
            db,
            case_id=case_id,
            object_type=object_type,
            object_id=object_id,
            title=payload.title,
            description=payload.description,
        )
    except ReviewItemCleanupNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReviewItemCleanupError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
