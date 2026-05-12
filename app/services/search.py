from dataclasses import dataclass
from uuid import UUID
import re

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.document import DocumentChunkModel, DocumentModel, DocumentPageModel
from app.schemas.search import KeywordSearchRequest


MAX_QUOTE_CHARS = 280


@dataclass(frozen=True)
class KeywordSearchHit:
    source_type: str
    document_id: UUID
    document_name: str
    page_start: int
    page_end: int
    score: float
    page_id: UUID | None = None
    chunk_id: UUID | None = None
    chunk_index: int | None = None
    quote: str | None = None


def keyword_search(db: Session, case_id: UUID, request: KeywordSearchRequest) -> list[KeywordSearchHit]:
    query = request.query.strip()
    if query == "":
        return []

    hits: list[KeywordSearchHit] = []
    if request.target in {"chunks", "all"}:
        hits.extend(_search_chunks(db, case_id, request, query))
    if request.target in {"pages", "all"}:
        hits.extend(_search_pages(db, case_id, request, query))

    return sorted(hits, key=lambda hit: (-hit.score, hit.document_name, hit.page_start))[: request.limit]


def _search_chunks(
    db: Session,
    case_id: UUID,
    request: KeywordSearchRequest,
    query: str,
) -> list[KeywordSearchHit]:
    ts_query = func.to_tsquery("simple", _make_prefix_tsquery(query))
    vector = func.to_tsvector("simple", DocumentChunkModel.chunk_text)
    rank = func.ts_rank_cd(vector, ts_query).label("score")
    stmt = (
        select(DocumentChunkModel, DocumentModel.original_filename, rank)
        .join(DocumentModel, DocumentModel.id == DocumentChunkModel.document_id)
        .where(
            DocumentChunkModel.case_id == case_id,
            DocumentChunkModel.is_current.is_(True),
            vector.op("@@")(ts_query),
        )
        .order_by(desc(rank), DocumentChunkModel.chunk_index.asc())
        .limit(request.limit)
    )
    stmt = _apply_common_filters(stmt, request, DocumentModel, DocumentChunkModel.page_start, DocumentChunkModel.page_end)

    return [
        KeywordSearchHit(
            source_type="chunk",
            document_id=row.DocumentChunkModel.document_id,
            document_name=row.original_filename,
            page_start=row.DocumentChunkModel.page_start,
            page_end=row.DocumentChunkModel.page_end,
            chunk_id=row.DocumentChunkModel.id,
            chunk_index=row.DocumentChunkModel.chunk_index,
            quote=_make_quote(row.DocumentChunkModel.chunk_text, query) if request.include_quotes else None,
            score=float(row.score or 0),
        )
        for row in db.execute(stmt)
    ]


def _search_pages(
    db: Session,
    case_id: UUID,
    request: KeywordSearchRequest,
    query: str,
) -> list[KeywordSearchHit]:
    ts_query = func.to_tsquery("simple", _make_prefix_tsquery(query))
    vector = func.to_tsvector("simple", DocumentPageModel.extracted_text)
    rank = func.ts_rank_cd(vector, ts_query).label("score")
    stmt = (
        select(DocumentPageModel, DocumentModel.original_filename, rank)
        .join(DocumentModel, DocumentModel.id == DocumentPageModel.document_id)
        .where(
            DocumentPageModel.case_id == case_id,
            DocumentPageModel.is_current.is_(True),
            vector.op("@@")(ts_query),
        )
        .order_by(desc(rank), DocumentPageModel.page_number.asc())
        .limit(request.limit)
    )
    stmt = _apply_common_filters(stmt, request, DocumentModel, DocumentPageModel.page_number, DocumentPageModel.page_number)

    return [
        KeywordSearchHit(
            source_type="page",
            document_id=row.DocumentPageModel.document_id,
            document_name=row.original_filename,
            page_start=row.DocumentPageModel.page_number,
            page_end=row.DocumentPageModel.page_number,
            page_id=row.DocumentPageModel.id,
            quote=_make_quote(row.DocumentPageModel.extracted_text, query) if request.include_quotes else None,
            score=float(row.score or 0),
        )
        for row in db.execute(stmt)
    ]


def _apply_common_filters(stmt, request: KeywordSearchRequest, document_model, page_start_column, page_end_column):
    if request.filters.document_ids:
        stmt = stmt.where(document_model.id.in_(request.filters.document_ids))
    if request.filters.document_type is not None:
        stmt = stmt.where(document_model.document_type == request.filters.document_type)
    if request.filters.page_start is not None:
        stmt = stmt.where(page_end_column >= request.filters.page_start)
    if request.filters.page_end is not None:
        stmt = stmt.where(page_start_column <= request.filters.page_end)
    return stmt


def _make_quote(text: str, query: str, max_chars: int = MAX_QUOTE_CHARS) -> str:
    normalized_query_terms = [term.casefold() for term in query.split() if term.strip()]
    lower_text = text.casefold()
    first_match = min(
        (index for term in normalized_query_terms if (index := lower_text.find(term)) >= 0),
        default=0,
    )
    half_window = max_chars // 2
    start = max(first_match - half_window, 0)
    end = min(start + max_chars, len(text))
    start, end = _expand_to_word_boundary(text, start, end)
    quote = text[start:end].strip()
    if start > 0:
        quote = "..." + quote
    if end < len(text):
        quote = quote + "..."
    return quote


def _make_prefix_tsquery(query: str) -> str:
    terms = re.findall(r"\w+", query.casefold())
    if not terms:
        return ""
    return " & ".join(f"{term}:*" for term in terms)


def _expand_to_word_boundary(text: str, start: int, end: int) -> tuple[int, int]:
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    while end < len(text) and not text[end - 1].isspace():
        end += 1
    return start, end
