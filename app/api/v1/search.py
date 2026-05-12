from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.search import KeywordSearchRequest, KeywordSearchResponse, KeywordSearchResult
from app.services.search import keyword_search

router = APIRouter()


@router.post("/cases/{case_id}/search/keyword", response_model=KeywordSearchResponse)
def post_keyword_search(
    case_id: UUID,
    payload: KeywordSearchRequest,
    db: Session = Depends(get_db),
) -> KeywordSearchResponse:
    hits = keyword_search(db, case_id, payload)
    return KeywordSearchResponse(data=[KeywordSearchResult(**hit.__dict__) for hit in hits])
