from dataclasses import dataclass
from typing import Any
from uuid import UUID
import json
import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import DocumentChunkModel, DocumentModel
from app.schemas.analysis_modules import AnalysisModuleRunRequest
from app.schemas.search import KeywordSearchRequest, SearchFilters
from app.services.document_collections import DocumentCollectionError, resolve_document_scope
from app.services.search import keyword_search
from app.services.text_store import read_chunk_text, read_chunk_text_from_store
from app.services.vector_index import hybrid_chunk_search, semantic_chunk_search


class AnalysisModuleError(ValueError):
    pass


@dataclass(frozen=True)
class RetrievedChunk:
    label: str
    document_name: str
    chunk: DocumentChunkModel
    retrieval_score: float
    match_type: str = "keyword"


ANALYSIS_RETRIEVAL_STOPWORDS = {
    "a",
    "adj",
    "adott",
    "ahol",
    "ahogy",
    "aki",
    "akik",
    "akkor",
    "alapjan",
    "alapján",
    "alatamasztott",
    "alátámasztott",
    "ami",
    "amik",
    "amiket",
    "amit",
    "amely",
    "amelyek",
    "amelyet",
    "arra",
    "az",
    "azok",
    "azokat",
    "azon",
    "azt",
    "ebben",
    "ebből",
    "egy",
    "egyes",
    "ehhez",
    "elemeket",
    "emeld",
    "informacio",
    "információ",
    "informaciok",
    "információk",
    "kovetkezo",
    "következő",
    "es",
    "és",
    "ezt",
    "forrashu",
    "forráshű",
    "hivatkozik",
    "hivatkozott",
    "hivatkozo",
    "hivatkozó",
    "hogy",
    "kapcsolatos",
    "kapcsolódó",
    "keress",
    "keresd",
    "keszits",
    "készíts",
    "ki",
    "kulon",
    "külön",
    "lehet",
    "legyen",
    "lévő",
    "meg",
    "mit",
    "minden",
    "mindenki",
    "mindent",
    "milyen",
    "miért",
    "mikor",
    "mint",
    "mivel",
    "nyerd",
    "olyan",
    "osszefoglalo",
    "összefoglaló",
    "rovid",
    "rövid",
    "szemely",
    "személy",
    "szemelyrol",
    "szemelyről",
    "szempontjabol",
    "szempontjából",
    "szerint",
    "szóló",
    "talalat",
    "talalatok",
    "találat",
    "találatok",
    "tartalmaz",
    "tény",
    "tények",
    "ugy",
    "ügy",
    "ugyosszefoglalo",
    "ügyösszefoglaló",
    "vagy",
    "valamint",
    "van",
    "vannak",
    "volt",
}

HUNGARIAN_SUFFIXES = (
    "ekről",
    "okról",
    "akról",
    "ekre",
    "okra",
    "akra",
    "ról",
    "ről",
    "ból",
    "tól",
    "höz",
    "ért",
    "ekrol",
    "okrol",
    "akrol",
    "rol",
    "bol",
    "tol",
    "hoz",
    "hez",
    "nek",
    "nak",
    "ban",
    "ben",
    "val",
    "vel",
    "ert",
    "et",
    "ot",
    "at",
    "ra",
    "re",
    "t",
)


def retrieve_chunks(db: Session, case_id: UUID, payload: AnalysisModuleRunRequest) -> list[RetrievedChunk]:
    if payload.query is None or payload.query.strip() == "":
        raise AnalysisModuleError("Focus text is required for analysis")

    retrieved_chunks = _retrieve_chunks_by_query(db, case_id, payload.query, payload.max_chunks, payload.retrieval_strategy)
    if retrieved_chunks:
        return retrieved_chunks
    raise AnalysisModuleError("No source chunks matched the focus text")


def retrieve_source_scope_chunks(
    db: Session,
    case_id: UUID,
    payload: AnalysisModuleRunRequest,
    *,
    document_id: UUID | None = None,
    document_ids: list[UUID] | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
) -> list[RetrievedChunk]:
    if payload.query is None or payload.query.strip() == "":
        return []
    return _retrieve_chunks_by_query(
        db,
        case_id,
        payload.query,
        payload.max_chunks,
        payload.retrieval_strategy,
        document_id=document_id,
        document_ids=document_ids,
        page_start=page_start,
        page_end=page_end,
    )


def _retrieve_chunks_by_query(
    db: Session,
    case_id: UUID,
    query_text: str,
    limit: int,
    retrieval_strategy: str,
    *,
    document_id: UUID | None = None,
    document_ids: list[UUID] | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
) -> list[RetrievedChunk]:
    effective_document_ids = _effective_document_ids(
        db,
        case_id,
        document_id=document_id,
        document_ids=document_ids,
    )
    if effective_document_ids == []:
        return []

    candidate_hits: dict[UUID, tuple[tuple[int, int, float, str, int, int], KeywordSearchHit]] = {}
    for query_index, query in enumerate(analysis_retrieval_queries(query_text)):
        filters = SearchFilters(
            document_ids=effective_document_ids,
            page_start=page_start,
            page_end=page_end,
        )
        keyword_hits = keyword_search(
            db,
            case_id,
            KeywordSearchRequest(
                query=query,
                filters=filters,
                limit=limit,
                include_quotes=False,
                target="chunks",
            )
        )
        if retrieval_strategy == "semantic":
            hits = semantic_chunk_search(
                db,
                case_id,
                query,
                limit,
                document_id=document_id,
                page_start=page_start,
                page_end=page_end,
                document_ids=effective_document_ids if document_id is None else None,
            )
        elif retrieval_strategy == "hybrid":
            hits = hybrid_chunk_search(
                db,
                case_id,
                query,
                keyword_hits,
                limit,
                document_id=document_id,
                page_start=page_start,
                page_end=page_end,
                document_ids=effective_document_ids if document_id is None else None,
            )
        else:
            hits = keyword_hits
        for hit in hits:
            if hit.chunk_id is None:
                continue
            priority = _retrieval_hit_priority(hit.match_type)
            rank_key = (
                priority,
                query_index,
                -float(hit.score),
                hit.document_name,
                hit.page_start,
                hit.chunk_index or 0,
            )
            existing = candidate_hits.get(hit.chunk_id)
            if existing is None or rank_key < existing[0]:
                candidate_hits[hit.chunk_id] = (rank_key, hit)

    retrieved_chunks: list[RetrievedChunk] = []
    sorted_hits = [hit for _, hit in sorted(candidate_hits.values(), key=lambda item: item[0])]
    for hit in sorted_hits:
        if len(retrieved_chunks) >= limit:
            break
        chunk = db.get(DocumentChunkModel, hit.chunk_id)
        if chunk is None:
            continue
        retrieved_chunks.append(
            RetrievedChunk(
                label=f"chunk_{len(retrieved_chunks) + 1}",
                document_name=hit.document_name,
                chunk=chunk,
                retrieval_score=hit.score,
                match_type=hit.match_type,
            )
        )
    return retrieved_chunks


def _retrieval_hit_priority(match_type: str) -> int:
    if match_type == "hybrid":
        return 0
    if match_type == "keyword":
        return 1
    return 2


def select_source_chunks(db: Session, case_id: UUID, payload: AnalysisModuleRunRequest) -> list[RetrievedChunk]:
    if payload.query is None or payload.query.strip() == "":
        raise AnalysisModuleError("Focus text is required for analysis source selection")
    if payload.source_mode == "document":
        if payload.document_id is None:
            raise AnalysisModuleError("document_id is required for document source mode")
        if not _document_is_active(db, case_id, payload.document_id):
            raise AnalysisModuleError("Selected document is not active")
        page_start, page_end = _document_page_range(db, case_id, payload.document_id, payload.page_start, payload.page_end)
        retrieval_chunks = retrieve_source_scope_chunks(
            db,
            case_id,
            payload,
            document_id=payload.document_id,
            page_start=page_start,
            page_end=page_end,
        )
        if not retrieval_chunks:
            raise AnalysisModuleError("No source chunks matched the focus text in the selected document")
        return retrieval_chunks
    if payload.source_mode == "case":
        retrieval_chunks = retrieve_source_scope_chunks(db, case_id, payload, document_ids=payload.document_ids)
        if not retrieval_chunks:
            raise AnalysisModuleError("No source chunks matched the focus text in this case")
        return retrieval_chunks
    if payload.source_mode == "collection":
        if payload.collection_id is None:
            raise AnalysisModuleError("collection_id is required for collection source mode")
        try:
            resolution = resolve_document_scope(db, case_id, "collections", collection_ids=[payload.collection_id])
        except DocumentCollectionError as exc:
            raise AnalysisModuleError(str(exc)) from exc
        retrieval_chunks = retrieve_source_scope_chunks(db, case_id, payload, document_ids=resolution.resolved_document_ids)
        if not retrieval_chunks:
            raise AnalysisModuleError("No source chunks matched the focus text in the selected document collection")
        return retrieval_chunks
    raise AnalysisModuleError("Unsupported source_mode")


def _document_page_range(
    db: Session,
    case_id: UUID,
    document_id: UUID,
    page_start: int | None,
    page_end: int | None,
) -> tuple[int, int]:
    max_page = _source_scope_max_page(db, case_id, document_id)
    if max_page is None:
        raise AnalysisModuleError("No paged source document is available in the selected document scope")
    effective_page_start = page_start if page_start is not None else 1
    effective_page_end = page_end if page_end is not None else max_page
    if effective_page_start > effective_page_end:
        raise AnalysisModuleError("page_start must be less than or equal to page_end")
    if effective_page_start < 1 or effective_page_end < 1 or effective_page_end > max_page:
        raise AnalysisModuleError(f"Page range must be within the selected document page count (1-{max_page})")
    return effective_page_start, effective_page_end


def _source_scope_max_page(db: Session, case_id: UUID, document_id: UUID | None = None) -> int | None:
    stmt = select(func.max(DocumentModel.page_count)).where(
        DocumentModel.case_id == case_id,
        DocumentModel.lifecycle_status == "active",
    )
    if document_id is not None:
        stmt = stmt.where(DocumentModel.id == document_id)
    value = db.execute(stmt).scalar_one_or_none()
    if value is None or int(value) < 1:
        return None
    return int(value)


def _effective_document_ids(
    db: Session,
    case_id: UUID,
    *,
    document_id: UUID | None = None,
    document_ids: list[UUID] | None = None,
) -> list[UUID]:
    base_stmt = select(DocumentModel.id).where(
        DocumentModel.case_id == case_id,
        DocumentModel.lifecycle_status == "active",
    )
    if document_id is not None:
        active_id = db.execute(base_stmt.where(DocumentModel.id == document_id)).scalar_one_or_none()
        return [active_id] if active_id is not None else []
    requested_ids = list(dict.fromkeys(document_ids or []))
    stmt = base_stmt
    if requested_ids:
        stmt = stmt.where(DocumentModel.id.in_(requested_ids))
    return list(db.execute(stmt).scalars().all())


def _document_is_active(db: Session, case_id: UUID, document_id: UUID) -> bool:
    return db.execute(
        select(DocumentModel.id).where(
            DocumentModel.case_id == case_id,
            DocumentModel.id == document_id,
            DocumentModel.lifecycle_status == "active",
        )
    ).scalar_one_or_none() is not None


def split_retrieved_chunks(retrieved_chunks: list[RetrievedChunk], batch_size: int) -> list[list[RetrievedChunk]]:
    if batch_size < 1:
        raise AnalysisModuleError("batch_size must be at least 1")
    return [retrieved_chunks[index : index + batch_size] for index in range(0, len(retrieved_chunks), batch_size)]


def chunk_batch_lookup(batches: list[list[RetrievedChunk]]) -> dict[UUID, dict[str, Any]]:
    lookup: dict[UUID, dict[str, Any]] = {}
    batch_count = len(batches)
    for batch_index, batch in enumerate(batches, start=1):
        chunk_labels = [retrieved.label for retrieved in batch]
        for retrieved in batch:
            lookup[retrieved.chunk.id] = {
                "batch_index": batch_index,
                "batch_count": batch_count,
                "chunk_labels": chunk_labels,
            }
    return lookup


def _document_chunks(db: Session, case_id: UUID, document_id: UUID, limit: int) -> list[RetrievedChunk]:
    stmt = (
        select(DocumentChunkModel, DocumentModel.original_filename)
        .join(DocumentModel, DocumentModel.id == DocumentChunkModel.document_id)
        .where(
            DocumentChunkModel.case_id == case_id,
            DocumentChunkModel.document_id == document_id,
            DocumentModel.case_id == case_id,
            DocumentModel.lifecycle_status == "active",
            DocumentChunkModel.is_current.is_(True),
        )
        .order_by(DocumentChunkModel.chunk_index.asc())
        .limit(limit)
    )
    retrieved_chunks: list[RetrievedChunk] = []
    for row in db.execute(stmt):
        retrieved_chunks.append(
            RetrievedChunk(
                label=f"chunk_{len(retrieved_chunks) + 1}",
                document_name=row.original_filename,
                chunk=row.DocumentChunkModel,
                retrieval_score=0.0,
                match_type="document_order",
            )
        )
    return retrieved_chunks


def _fallback_case_chunks(db: Session, case_id: UUID, limit: int) -> list[RetrievedChunk]:
    stmt = (
        select(DocumentChunkModel, DocumentModel.original_filename)
        .join(DocumentModel, DocumentModel.id == DocumentChunkModel.document_id)
        .where(
            DocumentChunkModel.case_id == case_id,
            DocumentChunkModel.is_current.is_(True),
            DocumentModel.lifecycle_status == "active",
        )
        .order_by(DocumentModel.imported_at.asc(), DocumentChunkModel.chunk_index.asc())
        .limit(limit)
    )
    retrieved_chunks: list[RetrievedChunk] = []
    for row in db.execute(stmt):
        retrieved_chunks.append(
            RetrievedChunk(
                label=f"chunk_{len(retrieved_chunks) + 1}",
                document_name=row.original_filename,
                chunk=row.DocumentChunkModel,
                retrieval_score=0.0,
                match_type="case_order",
            )
        )
    return retrieved_chunks


def analysis_retrieval_queries(query: str) -> list[str]:
    normalized_terms = _normalized_analysis_terms(query)
    variants = [query.strip()]
    if normalized_terms:
        variants.append(" ".join(normalized_terms[:4]))
        variants.extend(normalized_terms[:8])
    deduped: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        variant = variant.strip()
        key = variant.casefold()
        if variant and key not in seen:
            seen.add(key)
            deduped.append(variant)
    return deduped


def _normalized_analysis_terms(query: str) -> list[str]:
    normalized = unicodedata.normalize("NFC", query.casefold())
    terms: list[str] = []
    for raw_term in re.findall(r"\w+", normalized, flags=re.UNICODE):
        if raw_term in ANALYSIS_RETRIEVAL_STOPWORDS:
            continue
        term = _strip_hungarian_suffix(raw_term)
        if len(term) < 2 or term in ANALYSIS_RETRIEVAL_STOPWORDS:
            continue
        if term not in terms:
            terms.append(term)
    return terms


def _strip_hungarian_suffix(term: str) -> str:
    for suffix in HUNGARIAN_SUFFIXES:
        if term.endswith(suffix) and len(term) - len(suffix) >= 2:
            return _shorten_final_linking_vowel(term[: -len(suffix)])
    return term


def _shorten_final_linking_vowel(term: str) -> str:
    if term.endswith("á"):
        return f"{term[:-1]}a"
    if term.endswith("é"):
        return f"{term[:-1]}e"
    return term


def add_retrieved_chunk_inputs(
    db: Session,
    run_id: UUID,
    retrieved_chunks: list[RetrievedChunk],
    batch_metadata_by_chunk_id: dict[UUID, dict[str, Any]] | None = None,
) -> None:
    from app.services.analysis_runs import add_analysis_run_input

    for index, retrieved in enumerate(retrieved_chunks, start=1):
        payload_json = {
            "source_label": retrieved.label,
            "retrieval_score": retrieved.retrieval_score,
            "retrieval_match_type": retrieved.match_type,
        }
        if batch_metadata_by_chunk_id is not None:
            payload_json.update(batch_metadata_by_chunk_id.get(retrieved.chunk.id, {}))
        add_analysis_run_input(
            db,
            run_id,
            "chunk",
            index,
            document_id=retrieved.chunk.document_id,
            chunk_id=retrieved.chunk.id,
            payload_json=payload_json,
        )


def build_source_blocks(db: Session | None, retrieved_chunks: list[RetrievedChunk]) -> str:
    source_blocks = []
    for retrieved in retrieved_chunks:
        chunk_text = read_chunk_text_from_store(db, retrieved.chunk) if db is not None else read_chunk_text(retrieved.chunk)
        source_blocks.append(
            f"{retrieved.label}:\n"
            f"document_id: {retrieved.chunk.document_id}\n"
            f"document_name: {retrieved.document_name}\n"
            f"page_start: {retrieved.chunk.page_start}\n"
            f"page_end: {retrieved.chunk.page_end}\n"
            f"text:\n{chunk_text}"
        )
    return "\n".join(source_blocks)


def parse_llm_json_object(raw_content: str) -> dict[str, Any]:
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        object_start = cleaned.find("{")
        object_end = cleaned.rfind("}")
        if object_start == -1 or object_end <= object_start:
            raise AnalysisModuleError("LLM returned invalid JSON") from exc
        try:
            payload = json.loads(cleaned[object_start : object_end + 1])
        except json.JSONDecodeError:
            raise AnalysisModuleError("LLM returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise AnalysisModuleError("LLM returned a non-object JSON value")
    return payload
