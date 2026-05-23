from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.claim import ClaimDetail, ClaimList, ClaimMergeCreate, ClaimRead, ClaimSourceDetachCreate, ClaimSourceMoveCreate, ClaimSourceRead
from app.schemas.review import HumanReviewCreate, HumanReviewRead
from app.services.claims import (
    ClaimError,
    ClaimNotFoundError,
    detach_claim_source,
    get_claim,
    list_claim_reviews,
    list_claim_sources,
    list_claims,
    merge_claim,
    move_claim_source,
    review_claim,
)

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


@router.post("/cases/{case_id}/claims/{claim_id}/merge", response_model=ClaimDetail)
def post_claim_merge(
    case_id: UUID,
    claim_id: UUID,
    payload: ClaimMergeCreate,
    db: Session = Depends(get_db),
) -> ClaimDetail:
    try:
        claim = merge_claim(
            db,
            case_id=case_id,
            source_claim_id=claim_id,
            target_claim_id=payload.target_claim_id,
            review_comment=payload.review_comment,
        )
    except ClaimNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ClaimError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ClaimDetail(
        claim=ClaimRead.model_validate(claim),
        sources=[ClaimSourceRead.model_validate(source) for source in list_claim_sources(db, claim.id)],
        reviews=[HumanReviewRead.model_validate(review) for review in list_claim_reviews(db, claim.id)],
    )


@router.post("/cases/{case_id}/claims/{claim_id}/sources/{claim_source_id}/detach", response_model=ClaimDetail)
def post_claim_source_detach(
    case_id: UUID,
    claim_id: UUID,
    claim_source_id: UUID,
    payload: ClaimSourceDetachCreate,
    db: Session = Depends(get_db),
) -> ClaimDetail:
    try:
        claim = detach_claim_source(
            db,
            case_id=case_id,
            claim_id=claim_id,
            claim_source_id=claim_source_id,
            review_comment=payload.review_comment,
        )
    except ClaimNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ClaimError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ClaimDetail(
        claim=ClaimRead.model_validate(claim),
        sources=[ClaimSourceRead.model_validate(source) for source in list_claim_sources(db, claim.id)],
        reviews=[HumanReviewRead.model_validate(review) for review in list_claim_reviews(db, claim.id)],
    )


@router.post("/cases/{case_id}/claims/{claim_id}/sources/{claim_source_id}/move", response_model=ClaimDetail)
def post_claim_source_move(
    case_id: UUID,
    claim_id: UUID,
    claim_source_id: UUID,
    payload: ClaimSourceMoveCreate,
    db: Session = Depends(get_db),
) -> ClaimDetail:
    try:
        claim = move_claim_source(
            db,
            case_id=case_id,
            source_claim_id=claim_id,
            claim_source_id=claim_source_id,
            target_claim_id=payload.target_claim_id,
            review_comment=payload.review_comment,
        )
    except ClaimNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ClaimError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ClaimDetail(
        claim=ClaimRead.model_validate(claim),
        sources=[ClaimSourceRead.model_validate(source) for source in list_claim_sources(db, claim.id)],
        reviews=[HumanReviewRead.model_validate(review) for review in list_claim_reviews(db, claim.id)],
    )
