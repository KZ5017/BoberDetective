from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.review_report import CaseReviewReport, ReviewReportFilters
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
