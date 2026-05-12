from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.review import HumanReviewCreate, HumanReviewRead
from app.schemas.summary_item import SummaryItemCreate, SummaryItemDetail, SummaryItemList, SummaryItemRead, SummaryItemSourceRead
from app.services.summary_items import (
    SummaryItemNotFoundError,
    SummaryItemValidationError,
    create_summary_item_with_source,
    get_summary_item,
    list_summary_item_reviews,
    list_summary_item_sources,
    list_summary_items,
    review_summary_item,
)

router = APIRouter()


@router.get("/cases/{case_id}/summary-items", response_model=SummaryItemList)
def get_case_summary_items(case_id: UUID, db: Session = Depends(get_db)) -> SummaryItemList:
    return SummaryItemList(data=[SummaryItemRead.model_validate(item) for item in list_summary_items(db, case_id)])


@router.post("/cases/{case_id}/summary-items", response_model=SummaryItemDetail, status_code=status.HTTP_201_CREATED)
def post_case_summary_item(
    case_id: UUID,
    payload: SummaryItemCreate,
    db: Session = Depends(get_db),
) -> SummaryItemDetail:
    try:
        summary_item = create_summary_item_with_source(
            db,
            case_id=case_id,
            summary_type=payload.summary_type,
            title=payload.title,
            body_text=payload.body_text,
            source_reference_id=payload.source_reference_id,
            analysis_run_id=payload.analysis_run_id,
            confidence=payload.confidence,
            support_type=payload.support_type,
            relevance_rank=payload.relevance_rank,
        )
    except SummaryItemValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _summary_item_detail(db, case_id, summary_item.id)


@router.get("/cases/{case_id}/summary-items/{summary_item_id}", response_model=SummaryItemDetail)
def get_case_summary_item(case_id: UUID, summary_item_id: UUID, db: Session = Depends(get_db)) -> SummaryItemDetail:
    try:
        return _summary_item_detail(db, case_id, summary_item_id)
    except SummaryItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/cases/{case_id}/summary-items/{summary_item_id}/reviews", response_model=SummaryItemDetail)
def post_summary_item_review(
    case_id: UUID,
    summary_item_id: UUID,
    payload: HumanReviewCreate,
    db: Session = Depends(get_db),
) -> SummaryItemDetail:
    try:
        summary_item = review_summary_item(
            db,
            case_id=case_id,
            summary_item_id=summary_item_id,
            action_type=payload.action_type,
            review_comment=payload.review_comment,
        )
    except SummaryItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SummaryItemValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _summary_item_detail(db, case_id, summary_item.id)


def _summary_item_detail(db: Session, case_id: UUID, summary_item_id: UUID) -> SummaryItemDetail:
    summary_item = get_summary_item(db, case_id, summary_item_id)
    return SummaryItemDetail(
        summary_item=SummaryItemRead.model_validate(summary_item),
        sources=[SummaryItemSourceRead.model_validate(source) for source in list_summary_item_sources(db, summary_item.id)],
        reviews=[HumanReviewRead.model_validate(review) for review in list_summary_item_reviews(db, summary_item.id)],
    )
