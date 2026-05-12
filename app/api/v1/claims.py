from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.claim import ClaimDetail, ClaimList, ClaimRead, ClaimSourceRead
from app.schemas.review import HumanReviewCreate, HumanReviewRead
from app.services.claims import ClaimNotFoundError, get_claim, list_claim_reviews, list_claim_sources, list_claims, review_claim

router = APIRouter()


@router.get("/cases/{case_id}/claims", response_model=ClaimList)
def get_case_claims(case_id: UUID, db: Session = Depends(get_db)) -> ClaimList:
    return ClaimList(data=[ClaimRead.model_validate(claim) for claim in list_claims(db, case_id)])


@router.get("/cases/{case_id}/claims/{claim_id}", response_model=ClaimDetail)
def get_case_claim(case_id: UUID, claim_id: UUID, db: Session = Depends(get_db)) -> ClaimDetail:
    try:
        claim = get_claim(db, case_id, claim_id)
    except ClaimNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ClaimDetail(
        claim=ClaimRead.model_validate(claim),
        sources=[ClaimSourceRead.model_validate(source) for source in list_claim_sources(db, claim_id)],
        reviews=[HumanReviewRead.model_validate(review) for review in list_claim_reviews(db, claim_id)],
    )


@router.post("/cases/{case_id}/claims/{claim_id}/reviews", response_model=ClaimDetail)
def post_claim_review(
    case_id: UUID,
    claim_id: UUID,
    payload: HumanReviewCreate,
    db: Session = Depends(get_db),
) -> ClaimDetail:
    try:
        claim = review_claim(
            db,
            case_id=case_id,
            claim_id=claim_id,
            action_type=payload.action_type,
            review_comment=payload.review_comment,
        )
    except ClaimNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ClaimDetail(
        claim=ClaimRead.model_validate(claim),
        sources=[ClaimSourceRead.model_validate(source) for source in list_claim_sources(db, claim_id)],
        reviews=[HumanReviewRead.model_validate(review) for review in list_claim_reviews(db, claim_id)],
    )
