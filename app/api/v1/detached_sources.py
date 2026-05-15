from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.detached_source import DetachedSourceAttachCreate, DetachedSourceDiscardCreate, DetachedSourceItemList, DetachedSourceItemRead
from app.services.detached_sources import (
    DetachedSourceError,
    DetachedSourceNotFoundError,
    attach_detached_source_item,
    discard_detached_source_item,
    list_detached_source_items,
)

router = APIRouter()


@router.get("/cases/{case_id}/detached-source-items", response_model=DetachedSourceItemList)
def get_case_detached_source_items(case_id: UUID, db: Session = Depends(get_db)) -> DetachedSourceItemList:
    return DetachedSourceItemList(
        data=[DetachedSourceItemRead.model_validate(item) for item in list_detached_source_items(db, case_id)]
    )


@router.post("/cases/{case_id}/detached-source-items/{item_id}/attach", response_model=DetachedSourceItemRead)
def post_detached_source_item_attach(
    case_id: UUID,
    item_id: UUID,
    payload: DetachedSourceAttachCreate,
    db: Session = Depends(get_db),
) -> DetachedSourceItemRead:
    try:
        item = attach_detached_source_item(
            db,
            case_id=case_id,
            item_id=item_id,
            target_object_id=payload.target_object_id,
            review_comment=payload.review_comment,
        )
    except DetachedSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DetachedSourceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return DetachedSourceItemRead.model_validate(item)


@router.post("/cases/{case_id}/detached-source-items/{item_id}/discard", response_model=DetachedSourceItemRead)
def post_detached_source_item_discard(
    case_id: UUID,
    item_id: UUID,
    payload: DetachedSourceDiscardCreate,
    db: Session = Depends(get_db),
) -> DetachedSourceItemRead:
    try:
        item = discard_detached_source_item(
            db,
            case_id=case_id,
            item_id=item_id,
            review_comment=payload.review_comment,
        )
    except DetachedSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DetachedSourceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return DetachedSourceItemRead.model_validate(item)
