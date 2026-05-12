from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.review_report import CaseReviewReport
from app.services.review_report import build_case_review_report

router = APIRouter()


@router.get("/cases/{case_id}/review-report", response_model=CaseReviewReport)
def get_case_review_report(case_id: UUID, db: Session = Depends(get_db)) -> CaseReviewReport:
    return build_case_review_report(db, case_id)
