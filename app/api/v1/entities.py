from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.entity import EntityDetail, EntityList, EntityMentionRead, EntityMergeCreate, EntityRead, EntitySourceDetachCreate, EntitySourceMoveCreate
from app.schemas.review import HumanReviewCreate, HumanReviewRead
from app.services.entities import (
    EntityError,
    EntityNotFoundError,
    detach_entity_mention,
    get_entity,
    list_entities,
    list_entity_mentions,
    list_entity_reviews,
    merge_entity,
    move_entity_mention,
    review_entity,
)

router = APIRouter()


@router.get("/cases/{case_id}/entities", response_model=EntityList)
def get_case_entities(case_id: UUID, db: Session = Depends(get_db)) -> EntityList:
    return EntityList(data=[EntityRead.model_validate(entity) for entity in list_entities(db, case_id)])


@router.get("/cases/{case_id}/entities/{entity_id}", response_model=EntityDetail)
def get_case_entity(case_id: UUID, entity_id: UUID, db: Session = Depends(get_db)) -> EntityDetail:
    try:
        entity = get_entity(db, case_id, entity_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return EntityDetail(
        entity=EntityRead.model_validate(entity),
        mentions=[EntityMentionRead.model_validate(mention) for mention in list_entity_mentions(db, entity_id)],
        reviews=[HumanReviewRead.model_validate(review) for review in list_entity_reviews(db, entity_id)],
    )


@router.post("/cases/{case_id}/entities/{entity_id}/reviews", response_model=EntityDetail)
def post_entity_review(
    case_id: UUID,
    entity_id: UUID,
    payload: HumanReviewCreate,
    db: Session = Depends(get_db),
) -> EntityDetail:
    try:
        entity = review_entity(
            db,
            case_id=case_id,
            entity_id=entity_id,
            action_type=payload.action_type,
            review_comment=payload.review_comment,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EntityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EntityDetail(
        entity=EntityRead.model_validate(entity),
        mentions=[EntityMentionRead.model_validate(mention) for mention in list_entity_mentions(db, entity_id)],
        reviews=[HumanReviewRead.model_validate(review) for review in list_entity_reviews(db, entity_id)],
    )


@router.post("/cases/{case_id}/entities/{entity_id}/merge", response_model=EntityDetail)
def post_entity_merge(
    case_id: UUID,
    entity_id: UUID,
    payload: EntityMergeCreate,
    db: Session = Depends(get_db),
) -> EntityDetail:
    try:
        target_entity = merge_entity(
            db,
            case_id=case_id,
            source_entity_id=entity_id,
            target_entity_id=payload.target_entity_id,
            review_comment=payload.review_comment,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EntityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EntityDetail(
        entity=EntityRead.model_validate(target_entity),
        mentions=[EntityMentionRead.model_validate(mention) for mention in list_entity_mentions(db, target_entity.id)],
        reviews=[HumanReviewRead.model_validate(review) for review in list_entity_reviews(db, target_entity.id)],
    )


@router.post("/cases/{case_id}/entities/{entity_id}/mentions/{mention_id}/detach", response_model=EntityDetail)
def post_entity_source_detach(
    case_id: UUID,
    entity_id: UUID,
    mention_id: UUID,
    payload: EntitySourceDetachCreate,
    db: Session = Depends(get_db),
) -> EntityDetail:
    try:
        entity = detach_entity_mention(
            db,
            case_id=case_id,
            entity_id=entity_id,
            mention_id=mention_id,
            review_comment=payload.review_comment,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EntityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EntityDetail(
        entity=EntityRead.model_validate(entity),
        mentions=[EntityMentionRead.model_validate(mention) for mention in list_entity_mentions(db, entity.id)],
        reviews=[HumanReviewRead.model_validate(review) for review in list_entity_reviews(db, entity.id)],
    )


@router.post("/cases/{case_id}/entities/{entity_id}/mentions/{mention_id}/move", response_model=EntityDetail)
def post_entity_source_move(
    case_id: UUID,
    entity_id: UUID,
    mention_id: UUID,
    payload: EntitySourceMoveCreate,
    db: Session = Depends(get_db),
) -> EntityDetail:
    try:
        target_entity = move_entity_mention(
            db,
            case_id=case_id,
            source_entity_id=entity_id,
            mention_id=mention_id,
            target_entity_id=payload.target_entity_id,
            review_comment=payload.review_comment,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EntityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EntityDetail(
        entity=EntityRead.model_validate(target_entity),
        mentions=[EntityMentionRead.model_validate(mention) for mention in list_entity_mentions(db, target_entity.id)],
        reviews=[HumanReviewRead.model_validate(review) for review in list_entity_reviews(db, target_entity.id)],
    )
