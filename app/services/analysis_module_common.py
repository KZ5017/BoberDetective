from dataclasses import dataclass
from typing import Any
from uuid import UUID
import json
import re
import unicodedata

from sqlalchemy.orm import Session

from app.models.document import DocumentChunkModel
from app.schemas.analysis_modules import AnalysisModuleRunRequest
from app.schemas.search import KeywordSearchRequest, SearchFilters
from app.services.search import keyword_search


class AnalysisModuleError(ValueError):
    pass


@dataclass(frozen=True)
class RetrievedChunk:
    label: str
    document_name: str
    chunk: DocumentChunkModel
    retrieval_score: float


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
    retrieved_chunks: list[RetrievedChunk] = []
    seen_chunk_ids: set[UUID] = set()

    for query in analysis_retrieval_queries(payload.query):
        hits = keyword_search(
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
                )
            )
            if len(retrieved_chunks) >= payload.limit:
                return retrieved_chunks
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


def add_retrieved_chunk_inputs(db: Session, run_id: UUID, retrieved_chunks: list[RetrievedChunk]) -> None:
    from app.services.analysis_runs import add_analysis_run_input

    for index, retrieved in enumerate(retrieved_chunks, start=1):
        add_analysis_run_input(
            db,
            run_id,
            "chunk",
            index,
            document_id=retrieved.chunk.document_id,
            chunk_id=retrieved.chunk.id,
            payload_json={"source_label": retrieved.label, "retrieval_score": retrieved.retrieval_score},
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
        raise AnalysisModuleError("LLM returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise AnalysisModuleError("LLM returned a non-object JSON value")
    return payload
