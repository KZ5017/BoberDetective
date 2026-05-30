from dataclasses import dataclass
from uuid import UUID
import re

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.document import DocumentChunkModel, DocumentModel, DocumentPageModel, DocumentSearchEntryModel
from app.schemas.search import KeywordSearchRequest
from app.services.text_store import read_chunk_text_from_store, read_page_text_from_store


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
    match_type: str = "keyword"


def keyword_search(db: Session, case_id: UUID, request: KeywordSearchRequest) -> list[KeywordSearchHit]:
    query = request.query.strip()
    if query == "":
        return []
    if _make_prefix_tsquery(query) == "":
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
    rank = func.ts_rank_cd(DocumentSearchEntryModel.search_vector, ts_query).label("score")
    stmt = (
        select(DocumentSearchEntryModel, DocumentModel.original_filename, rank)
        .join(DocumentModel, DocumentModel.id == DocumentSearchEntryModel.document_id)
        .where(
            DocumentSearchEntryModel.case_id == case_id,
            DocumentSearchEntryModel.source_type == "chunk",
            DocumentSearchEntryModel.is_current.is_(True),
            DocumentSearchEntryModel.lifecycle_status == "active",
            DocumentModel.lifecycle_status == "active",
            DocumentSearchEntryModel.search_vector.op("@@")(ts_query),
        )
        .order_by(desc(rank), DocumentSearchEntryModel.chunk_index.asc())
        .limit(request.limit)
    )
    stmt = _apply_common_filters(
        stmt,
        request,
        DocumentSearchEntryModel.document_id,
        DocumentSearchEntryModel.page_start,
        DocumentSearchEntryModel.page_end,
    )

    hits: list[KeywordSearchHit] = []
    for row in db.execute(stmt):
        entry = row.DocumentSearchEntryModel
        chunk = db.get(DocumentChunkModel, entry.chunk_id) if entry.chunk_id is not None else None
        if chunk is None:
            continue
        quote = None
        if request.include_quotes:
            quote = _make_quote(read_chunk_text_from_store(db, chunk), query)
        hits.append(
            KeywordSearchHit(
                source_type="chunk",
                document_id=entry.document_id,
                document_name=row.original_filename,
                page_start=entry.page_start,
                page_end=entry.page_end,
                chunk_id=entry.chunk_id,
                chunk_index=entry.chunk_index,
                quote=quote,
                score=float(row.score or 0),
            )
        )
    return hits


def _search_pages(
    db: Session,
    case_id: UUID,
    request: KeywordSearchRequest,
    query: str,
) -> list[KeywordSearchHit]:
    ts_query = func.to_tsquery("simple", _make_prefix_tsquery(query))
    rank = func.ts_rank_cd(DocumentSearchEntryModel.search_vector, ts_query).label("score")
    stmt = (
        select(DocumentSearchEntryModel, DocumentModel.original_filename, rank)
        .join(DocumentModel, DocumentModel.id == DocumentSearchEntryModel.document_id)
        .where(
            DocumentSearchEntryModel.case_id == case_id,
            DocumentSearchEntryModel.source_type == "page",
            DocumentSearchEntryModel.is_current.is_(True),
            DocumentSearchEntryModel.lifecycle_status == "active",
            DocumentModel.lifecycle_status == "active",
            DocumentSearchEntryModel.search_vector.op("@@")(ts_query),
        )
        .order_by(desc(rank), DocumentSearchEntryModel.page_start.asc())
        .limit(request.limit)
    )
    stmt = _apply_common_filters(
        stmt,
        request,
        DocumentSearchEntryModel.document_id,
        DocumentSearchEntryModel.page_start,
        DocumentSearchEntryModel.page_end,
    )

    hits: list[KeywordSearchHit] = []
    for row in db.execute(stmt):
        entry = row.DocumentSearchEntryModel
        page = db.get(DocumentPageModel, entry.page_id) if entry.page_id is not None else None
        if page is None:
            continue
        quote = None
        if request.include_quotes:
            quote = _make_quote(read_page_text_from_store(db, page), query)
        hits.append(
            KeywordSearchHit(
                source_type="page",
                document_id=entry.document_id,
                document_name=row.original_filename,
                page_start=entry.page_start,
                page_end=entry.page_end,
                page_id=entry.page_id,
                quote=quote,
                score=float(row.score or 0),
            )
        )
    return hits


def _apply_common_filters(
    stmt,
    request: KeywordSearchRequest,
    document_id_column,
    page_start_column,
    page_end_column,
):
    if request.filters.document_ids:
        stmt = stmt.where(document_id_column.in_(request.filters.document_ids))
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
