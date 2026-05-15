from dataclasses import dataclass
from typing import Any
from uuid import UUID
import json
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import DocumentChunkModel, DocumentModel
from app.schemas.analysis_modules import AnalysisModuleRunRequest
from app.schemas.search import KeywordSearchRequest, SearchFilters
from app.services.search import keyword_search
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
    "adj",
    "alapjan",
    "alatamasztott",
    "az",
    "egy",
    "elemeket",
    "emeld",
    "es",
    "forrashu",
    "hivatkozik",
    "hivatkozott",
    "hivatkozo",
    "hogy",
    "keress",
    "keszits",
    "ki",
    "kulon",
    "mit",
    "nyerd",
    "osszefoglalo",
    "rovid",
    "szempontjabol",
    "ugyosszefoglalo",
}

HUNGARIAN_SUFFIXES = (
    "ekrol",
    "okrol",
    "akrol",
    "ekre",
    "okra",
    "akra",
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
    "rol",
    "et",
    "ot",
    "at",
    "ra",
    "re",
    "t",
)


def retrieve_chunks(db: Session, case_id: UUID, payload: AnalysisModuleRunRequest) -> list[RetrievedChunk]:
    if payload.query is None or payload.query.strip() == "":
        raise AnalysisModuleError("Query is required for focused query analysis")

    retrieved_chunks: list[RetrievedChunk] = []
    seen_chunk_ids: set[UUID] = set()

    for query in analysis_retrieval_queries(payload.query):
        keyword_hits = keyword_search(
            db,
            case_id,
            KeywordSearchRequest(
                query=query,
                filters=SearchFilters(),
                limit=payload.limit,
                include_quotes=False,
                target="chunks",
            )
        )
        if payload.retrieval_strategy == "semantic":
            hits = semantic_chunk_search(db, case_id, query, payload.limit)
        elif payload.retrieval_strategy == "hybrid":
            hits = hybrid_chunk_search(db, case_id, query, keyword_hits, payload.limit)
        else:
            hits = keyword_hits
        for hit in hits:
            if hit.chunk_id is None or hit.chunk_id in seen_chunk_ids:
                continue
            chunk = db.get(DocumentChunkModel, hit.chunk_id)
            if chunk is None:
                continue
            seen_chunk_ids.add(chunk.id)
            retrieved_chunks.append(
                RetrievedChunk(
                    label=f"chunk_{len(retrieved_chunks) + 1}",
                    document_name=hit.document_name,
                    chunk=chunk,
                    retrieval_score=hit.score,
                    match_type=hit.match_type,
                )
            )
            if len(retrieved_chunks) >= payload.limit:
                return retrieved_chunks
    if retrieved_chunks:
        return retrieved_chunks
    return _fallback_case_chunks(db, case_id, payload.limit)


def select_source_chunks(db: Session, case_id: UUID, payload: AnalysisModuleRunRequest) -> list[RetrievedChunk]:
    if payload.source_mode == "focused_query":
        return retrieve_chunks(db, case_id, payload)
    if payload.source_mode == "document":
        if payload.document_id is None:
            raise AnalysisModuleError("document_id is required for document source mode")
        return _document_chunks(db, case_id, payload.document_id, payload.max_chunks)
    if payload.source_mode == "case":
        return _fallback_case_chunks(db, case_id, payload.max_chunks)
    raise AnalysisModuleError("Unsupported source_mode")


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
        .where(DocumentChunkModel.case_id == case_id, DocumentChunkModel.is_current.is_(True))
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
    normalized = unicodedata.normalize("NFKD", query.casefold())
    ascii_query = "".join(char for char in normalized if not unicodedata.combining(char))
    terms: list[str] = []
    for raw_term in re.findall(r"\w+", ascii_query):
        if raw_term in ANALYSIS_RETRIEVAL_STOPWORDS:
            continue
        term = _strip_hungarian_suffix(raw_term)
        if len(term) < 4 or term in ANALYSIS_RETRIEVAL_STOPWORDS:
            continue
        if term not in terms:
            terms.append(term)
    return terms


def _strip_hungarian_suffix(term: str) -> str:
    for suffix in HUNGARIAN_SUFFIXES:
        if term.endswith(suffix) and len(term) - len(suffix) >= 4:
            return term[: -len(suffix)]
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


def build_source_blocks(retrieved_chunks: list[RetrievedChunk]) -> str:
    source_blocks = []
    for retrieved in retrieved_chunks:
        source_blocks.append(
            f"{retrieved.label}:\n"
            f"document_id: {retrieved.chunk.document_id}\n"
            f"document_name: {retrieved.document_name}\n"
            f"page_start: {retrieved.chunk.page_start}\n"
            f"page_end: {retrieved.chunk.page_end}\n"
            f"text:\n{retrieved.chunk.chunk_text}"
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
