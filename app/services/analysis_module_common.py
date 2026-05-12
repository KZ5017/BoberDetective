from dataclasses import dataclass
from typing import Any
from uuid import UUID
import json
import re

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


def retrieve_chunks(db: Session, case_id: UUID, payload: AnalysisModuleRunRequest) -> list[RetrievedChunk]:
    hits = keyword_search(
        db,
        case_id,
        KeywordSearchRequest(
            query=payload.query,
            filters=SearchFilters(),
            limit=payload.limit,
            include_quotes=False,
            target="chunks",
        ),
    )
    retrieved_chunks: list[RetrievedChunk] = []
    seen_chunk_ids: set[UUID] = set()
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
    return retrieved_chunks


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
