from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.missing_item import (
    MissingItemCandidateCreate,
    MissingItemCandidateDetail,
    MissingItemCandidateList,
    MissingItemCandidateMergeCreate,
    MissingItemCandidateRead,
    MissingItemCandidateSourceDetachCreate,
    MissingItemCandidateSourceMoveCreate,
    MissingItemCandidateSourceRead,
)
from app.schemas.review import HumanReviewCreate, HumanReviewRead
from app.services.missing_items import (
    MissingItemCandidateNotFoundError,
    MissingItemCandidateValidationError,
    create_missing_item_candidate,
    detach_missing_item_candidate_source,
    get_missing_item_candidate,
    list_missing_item_candidate_reviews,
    list_missing_item_candidate_sources,
    list_missing_item_candidates,
    merge_missing_item_candidate,
    move_missing_item_candidate_source,
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


@router.post(
    "/cases/{case_id}/missing-item-candidates/{missing_item_candidate_id}/merge",
    response_model=MissingItemCandidateDetail,
)
def post_missing_item_candidate_merge(
    case_id: UUID,
    missing_item_candidate_id: UUID,
    payload: MissingItemCandidateMergeCreate,
    db: Session = Depends(get_db),
) -> MissingItemCandidateDetail:
    try:
        target_candidate = merge_missing_item_candidate(
            db,
            case_id=case_id,
            source_candidate_id=missing_item_candidate_id,
            target_candidate_id=payload.target_missing_item_candidate_id,
            review_comment=payload.review_comment,
        )
    except MissingItemCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MissingItemCandidateValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _missing_item_candidate_detail(db, case_id, target_candidate.id)


@router.post(
    "/cases/{case_id}/missing-item-candidates/{missing_item_candidate_id}/sources/{source_link_id}/detach",
    response_model=MissingItemCandidateDetail,
)
def post_missing_item_candidate_source_detach(
    case_id: UUID,
    missing_item_candidate_id: UUID,
    source_link_id: UUID,
    payload: MissingItemCandidateSourceDetachCreate,
    db: Session = Depends(get_db),
) -> MissingItemCandidateDetail:
    try:
        candidate = detach_missing_item_candidate_source(
            db,
            case_id=case_id,
            missing_item_candidate_id=missing_item_candidate_id,
            source_link_id=source_link_id,
            review_comment=payload.review_comment,
        )
    except MissingItemCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MissingItemCandidateValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _missing_item_candidate_detail(db, case_id, candidate.id)


@router.post(
    "/cases/{case_id}/missing-item-candidates/{missing_item_candidate_id}/sources/{source_link_id}/move",
    response_model=MissingItemCandidateDetail,
)
def post_missing_item_candidate_source_move(
    case_id: UUID,
    missing_item_candidate_id: UUID,
    source_link_id: UUID,
    payload: MissingItemCandidateSourceMoveCreate,
    db: Session = Depends(get_db),
) -> MissingItemCandidateDetail:
    try:
        target_candidate = move_missing_item_candidate_source(
            db,
            case_id=case_id,
            source_candidate_id=missing_item_candidate_id,
            source_link_id=source_link_id,
            target_candidate_id=payload.target_missing_item_candidate_id,
            review_comment=payload.review_comment,
        )
    except MissingItemCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MissingItemCandidateValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _missing_item_candidate_detail(db, case_id, target_candidate.id)


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
