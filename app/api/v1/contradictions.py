from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.contradiction import (
    ContradictionCandidateCreate,
    ContradictionCandidateDetail,
    ContradictionCandidateList,
    ContradictionCandidateRead,
    ContradictionCandidateSourceRead,
)
from app.schemas.review import HumanReviewCreate, HumanReviewRead
from app.services.contradictions import (
    ContradictionCandidateNotFoundError,
    ContradictionCandidateValidationError,
    create_contradiction_candidate,
    get_contradiction_candidate,
    list_contradiction_candidate_reviews,
    list_contradiction_candidate_sources,
    list_contradiction_candidates,
    review_contradiction_candidate,
)

router = APIRouter()


@router.get("/cases/{case_id}/contradiction-candidates", response_model=ContradictionCandidateList)
def get_case_contradiction_candidates(case_id: UUID, db: Session = Depends(get_db)) -> ContradictionCandidateList:
    return ContradictionCandidateList(
        data=[ContradictionCandidateRead.model_validate(candidate) for candidate in list_contradiction_candidates(db, case_id)]
    )


@router.post(
    "/cases/{case_id}/contradiction-candidates",
    response_model=ContradictionCandidateDetail,
    status_code=status.HTTP_201_CREATED,
)
def post_case_contradiction_candidate(
    case_id: UUID,
    payload: ContradictionCandidateCreate,
    db: Session = Depends(get_db),
) -> ContradictionCandidateDetail:
    try:
        candidate = create_contradiction_candidate(
            db,
            case_id=case_id,
            contradiction_type=payload.contradiction_type,
            title=payload.title,
            description=payload.description,
            analysis_run_id=payload.analysis_run_id,
            sources=payload.sources,
            claim_id_a=payload.claim_id_a,
            claim_id_b=payload.claim_id_b,
            event_id_a=payload.event_id_a,
            event_id_b=payload.event_id_b,
            confidence=payload.confidence,
            severity_hint=payload.severity_hint,
        )
    except ContradictionCandidateValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _contradiction_candidate_detail(db, case_id, candidate.id)


@router.get("/cases/{case_id}/contradiction-candidates/{contradiction_candidate_id}", response_model=ContradictionCandidateDetail)
def get_case_contradiction_candidate(
    case_id: UUID,
    contradiction_candidate_id: UUID,
    db: Session = Depends(get_db),
) -> ContradictionCandidateDetail:
    try:
        return _contradiction_candidate_detail(db, case_id, contradiction_candidate_id)
    except ContradictionCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/cases/{case_id}/contradiction-candidates/{contradiction_candidate_id}/reviews",
    response_model=ContradictionCandidateDetail,
)
def post_contradiction_candidate_review(
    case_id: UUID,
    contradiction_candidate_id: UUID,
    payload: HumanReviewCreate,
    db: Session = Depends(get_db),
) -> ContradictionCandidateDetail:
    try:
        candidate = review_contradiction_candidate(
            db,
            case_id=case_id,
            contradiction_candidate_id=contradiction_candidate_id,
            action_type=payload.action_type,
            review_comment=payload.review_comment,
        )
    except ContradictionCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ContradictionCandidateValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _contradiction_candidate_detail(db, case_id, candidate.id)


def _contradiction_candidate_detail(db: Session, case_id: UUID, contradiction_candidate_id: UUID) -> ContradictionCandidateDetail:
    candidate = get_contradiction_candidate(db, case_id, contradiction_candidate_id)
    return ContradictionCandidateDetail(
        contradiction_candidate=ContradictionCandidateRead.model_validate(candidate),
        sources=[
            ContradictionCandidateSourceRead.model_validate(source)
            for source in list_contradiction_candidate_sources(db, candidate.id)
        ],
        reviews=[HumanReviewRead.model_validate(review) for review in list_contradiction_candidate_reviews(db, candidate.id)],
    )
