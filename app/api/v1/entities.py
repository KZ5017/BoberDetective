from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.entity import EntityDetail, EntityList, EntityMentionRead, EntityRead
from app.services.entities import EntityNotFoundError, get_entity, list_entities, list_entity_mentions

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
    )
