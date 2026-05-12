from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.missing_item import (
    MissingItemCandidateCreate,
    MissingItemCandidateDetail,
    MissingItemCandidateList,
    MissingItemCandidateRead,
    MissingItemCandidateSourceRead,
)
from app.schemas.review import HumanReviewCreate, HumanReviewRead
from app.services.missing_items import (
    MissingItemCandidateNotFoundError,
    MissingItemCandidateValidationError,
    create_missing_item_candidate,
    get_missing_item_candidate,
    list_missing_item_candidate_reviews,
    list_missing_item_candidate_sources,
    list_missing_item_candidates,
    review_missing_item_candidate,
)

router = APIRouter()


@router.get("/cases/{case_id}/missing-item-candidates", response_model=MissingItemCandidateList)
def get_case_missing_item_candidates(case_id: UUID, db: Session = Depends(get_db)) -> MissingItemCandidateList:
    return MissingItemCandidateList(
        data=[MissingItemCandidateRead.model_validate(candidate) for candidate in list_missing_item_candidates(db, case_id)]
    )


@router.post(
    "/cases/{case_id}/missing-item-candidates",
    response_model=MissingItemCandidateDetail,
    status_code=status.HTTP_201_CREATED,
)
def post_case_missing_item_candidate(
    case_id: UUID,
    payload: MissingItemCandidateCreate,
    db: Session = Depends(get_db),
) -> MissingItemCandidateDetail:
    try:
        candidate = create_missing_item_candidate(
            db,
            case_id=case_id,
            missing_item_type=payload.missing_item_type,
            referenced_item_text=payload.referenced_item_text,
            description=payload.description,
            expected_document_type=payload.expected_document_type,
            confidence=payload.confidence,
            analysis_run_id=payload.analysis_run_id,
            sources=payload.sources,
        )
    except MissingItemCandidateValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _missing_item_candidate_detail(db, case_id, candidate.id)


@router.get("/cases/{case_id}/missing-item-candidates/{missing_item_candidate_id}", response_model=MissingItemCandidateDetail)
def get_case_missing_item_candidate(
    case_id: UUID,
    missing_item_candidate_id: UUID,
    db: Session = Depends(get_db),
) -> MissingItemCandidateDetail:
    try:
        return _missing_item_candidate_detail(db, case_id, missing_item_candidate_id)
    except MissingItemCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/cases/{case_id}/missing-item-candidates/{missing_item_candidate_id}/reviews",
    response_model=MissingItemCandidateDetail,
)
def post_missing_item_candidate_review(
    case_id: UUID,
    missing_item_candidate_id: UUID,
    payload: HumanReviewCreate,
    db: Session = Depends(get_db),
) -> MissingItemCandidateDetail:
    try:
        candidate = review_missing_item_candidate(
            db,
            case_id=case_id,
            missing_item_candidate_id=missing_item_candidate_id,
            action_type=payload.action_type,
            review_comment=payload.review_comment,
        )
    except MissingItemCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MissingItemCandidateValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _missing_item_candidate_detail(db, case_id, candidate.id)


def _missing_item_candidate_detail(db: Session, case_id: UUID, missing_item_candidate_id: UUID) -> MissingItemCandidateDetail:
    candidate = get_missing_item_candidate(db, case_id, missing_item_candidate_id)
    return MissingItemCandidateDetail(
        missing_item_candidate=MissingItemCandidateRead.model_validate(candidate),
        sources=[
            MissingItemCandidateSourceRead.model_validate(source)
            for source in list_missing_item_candidate_sources(db, candidate.id)
        ],
        reviews=[HumanReviewRead.model_validate(review) for review in list_missing_item_candidate_reviews(db, candidate.id)],
    )
