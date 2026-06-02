from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.detached_source import DetachedSourceItemModel
from app.models.document import DocumentChunkModel, DocumentPageModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.detached_source import DetachedSourceAttachCreate, DetachedSourceItemList, DetachedSourceItemRead
from app.services.detached_sources import (
    DetachedSourceError,
    DetachedSourceNotFoundError,
    attach_detached_source_item,
    delete_detached_source_item,
    list_detached_source_items,
)
from app.services.text_store import read_chunk_text_from_store, read_page_text_from_store

router = APIRouter()


@router.get("/cases/{case_id}/detached-source-items", response_model=DetachedSourceItemList)
def get_case_detached_source_items(case_id: UUID, db: Session = Depends(get_db)) -> DetachedSourceItemList:
    return DetachedSourceItemList(
        data=[_detached_source_item_read(db, item) for item in list_detached_source_items(db, case_id)]
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
    return _detached_source_item_read(db, item)


@router.delete("/cases/{case_id}/detached-source-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_detached_source_item_endpoint(
    case_id: UUID,
    item_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_detached_source_item(
            db,
            case_id=case_id,
            item_id=item_id,
        )
    except DetachedSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DetachedSourceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _detached_source_item_read(db: Session, item: DetachedSourceItemModel) -> DetachedSourceItemRead:
    source_reference = db.get(SourceReferenceModel, item.source_reference_id)
    excerpt, excerpt_start, excerpt_end = _detached_source_excerpt(db, source_reference)
    return DetachedSourceItemRead.model_validate(item).model_copy(
        update={
            "source_text_excerpt": excerpt,
            "source_text_excerpt_char_start": excerpt_start,
            "source_text_excerpt_char_end": excerpt_end,
        }
    )


def _detached_source_excerpt(
    db: Session,
    source_reference: SourceReferenceModel | None,
) -> tuple[str | None, int | None, int | None]:
    if source_reference is None:
        return None, None, None
    source_text = _detached_source_text(db, source_reference)
    if source_text is None:
        return None, None, None
    quote_start = source_reference.quote_char_start
    quote_end = source_reference.quote_char_end
    if quote_start is not None and quote_end is not None and source_text[quote_start:quote_end] == source_reference.quote_text:
        return source_text, 0, len(source_text)
    found_at = source_text.find(source_reference.quote_text)
    if found_at >= 0:
        return source_text, 0, len(source_text)
    return source_text, 0, len(source_text)


def _detached_source_text(db: Session, source_reference: SourceReferenceModel) -> str | None:
    if source_reference.chunk_id is not None:
        chunk = db.get(DocumentChunkModel, source_reference.chunk_id)
        return read_chunk_text_from_store(db, chunk) if chunk is not None else None
    if source_reference.page_id is not None:
        page = db.get(DocumentPageModel, source_reference.page_id)
        return read_page_text_from_store(db, page) if page is not None else None
    return None
