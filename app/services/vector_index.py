from dataclasses import dataclass
from collections.abc import Iterator
from datetime import datetime
from uuid import UUID
import re

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models.analysis import AnalysisRunInputModel, AnalysisRunModel, AnalysisRunOutputModel
from app.models.document import DocumentChunkModel, DocumentModel
from app.schemas.search import ChunkIndexRequest
from app.services.analysis_runs import add_analysis_run_input, add_analysis_run_output, finish_analysis_run, start_analysis_run
from app.services.llm import LLMProviderError, get_llm_provider
from app.services.search import KeywordSearchHit


class VectorIndexError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChunkIndexResult:
    analysis_run_id: UUID
    indexed_count: int
    skipped_count: int
    collection_name: str
    embedding_model: str


@dataclass(frozen=True)
class ChunkIndexJobResult:
    analysis_run_id: UUID
    status: str
    collection_name: str
    embedding_model: str


@dataclass(frozen=True)
class ChunkIndexStatus:
    case_id: UUID
    document_id: UUID | None
    collection_name: str
    embedding_model: str
    current_chunk_count: int
    indexed_chunk_count: int
    missing_chunk_count: int
    is_ready: bool
    needs_indexing: bool
    latest_run_id: UUID | None
    latest_run_status: str | None
    latest_run_validation_status: str | None
    latest_run_started_at: datetime | None
    latest_run_finished_at: datetime | None
    latest_run_input_count: int
    latest_run_output_count: int
    latest_run_progress_percent: float | None


@dataclass(frozen=True)
class SemanticChunkHit:
    chunk_id: UUID
    score: float
    match_type: str


@dataclass(frozen=True)
class EmbeddingBatch:
    chunks: list[DocumentChunkModel]
    embeddings: list[list[float]]


@dataclass(frozen=True)
class HybridRankCandidate:
    hit: KeywordSearchHit
    keyword_score: float
    semantic_score: float
    keyword_rank: int | None
    semantic_rank: int | None
    exact_phrase_match: bool


HYBRID_KEYWORD_WEIGHT = 0.35
HYBRID_SEMANTIC_WEIGHT = 0.55
HYBRID_OVERLAP_BONUS = 0.20
HYBRID_EXACT_PHRASE_BONUS = 0.10


class QdrantChunkIndex:
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = client

    @property
    def collection_name(self) -> str:
        return chunk_collection_name(self._settings)

    def ensure_collection(self, vector_size: int) -> None:
        client = self._client or self._build_client()
        close_client = self._client is None
        try:
            response = client.get(f"/collections/{self.collection_name}")
            if response.status_code == 200:
                return
            if response.status_code != 404:
                response.raise_for_status()
            create_response = client.put(
                f"/collections/{self.collection_name}",
                json={"vectors": {"size": vector_size, "distance": "Cosine"}},
            )
            create_response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise VectorIndexError(_http_status_error_message(exc)) from exc
        except httpx.HTTPError as exc:
            raise VectorIndexError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

    def upsert_chunks(self, chunks: list[DocumentChunkModel], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise VectorIndexError("Chunk and embedding counts differ")
        if not chunks:
            return
        self.ensure_collection(len(embeddings[0]))
        points = [
            {
                "id": str(chunk.id),
                "vector": embedding,
                "payload": {
                    "case_id": str(chunk.case_id),
                    "document_id": str(chunk.document_id),
                    "chunk_id": str(chunk.id),
                    "chunk_index": chunk.chunk_index,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "is_current": bool(chunk.is_current),
                },
            }
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        client = self._client or self._build_client()
        close_client = self._client is None
        try:
            response = client.put(
                f"/collections/{self.collection_name}/points",
                params={"wait": "true"},
                json={"points": points},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise VectorIndexError(_http_status_error_message(exc)) from exc
        except httpx.HTTPError as exc:
            raise VectorIndexError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

    def search(
        self,
        *,
        case_id: UUID,
        query_embedding: list[float],
        limit: int,
        document_id: UUID | None = None,
        page_start: int | None = None,
        page_end: int | None = None,
    ) -> list[SemanticChunkHit]:
        filter_must = [
            {"key": "case_id", "match": {"value": str(case_id)}},
            {"key": "is_current", "match": {"value": True}},
        ]
        if document_id is not None:
            filter_must.append({"key": "document_id", "match": {"value": str(document_id)}})
        if page_start is not None:
            filter_must.append({"key": "page_end", "range": {"gte": page_start}})
        if page_end is not None:
            filter_must.append({"key": "page_start", "range": {"lte": page_end}})
        client = self._client or self._build_client()
        close_client = self._client is None
        try:
            response = client.post(
                f"/collections/{self.collection_name}/points/search",
                json={
                    "vector": query_embedding,
                    "limit": limit,
                    "with_payload": True,
                    "filter": {"must": filter_must},
                },
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return []
            raise VectorIndexError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise VectorIndexError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

        result = payload.get("result")
        if not isinstance(result, list):
            raise VectorIndexError("Qdrant returned an invalid search payload")
        hits: list[SemanticChunkHit] = []
        for item in result:
            if not isinstance(item, dict) or not isinstance(item.get("payload"), dict):
                continue
            chunk_id = item["payload"].get("chunk_id")
            score = item.get("score")
            if not chunk_id or score is None:
                continue
            hits.append(SemanticChunkHit(chunk_id=UUID(str(chunk_id)), score=float(score), match_type="semantic"))
        return hits

    def _build_client(self) -> httpx.Client:
        return httpx.Client(base_url=self._settings.qdrant_url.rstrip("/"), timeout=30)


def index_case_chunks(db: Session, case_id: UUID, request: ChunkIndexRequest) -> ChunkIndexResult:
    settings = get_settings()
    run = _start_chunk_index_run(db, case_id, request, settings, background=False)
    return _process_chunk_index_run(db, case_id, request, settings, run)


def start_chunk_index_job(db: Session, case_id: UUID, request: ChunkIndexRequest) -> ChunkIndexJobResult:
    settings = get_settings()
    run = _start_chunk_index_run(db, case_id, request, settings, background=True)
    return ChunkIndexJobResult(run.id, run.status, chunk_collection_name(settings), settings.llm_embedding_model)


def execute_chunk_index_job(analysis_run_id: UUID, case_id: UUID, request: ChunkIndexRequest) -> None:
    with SessionLocal() as db:
        settings = get_settings()
        run = db.get(AnalysisRunModel, analysis_run_id)
        if run is None or run.case_id != case_id:
            return
        _process_chunk_index_run(db, case_id, request, settings, run)


def _start_chunk_index_run(
    db: Session,
    case_id: UUID,
    request: ChunkIndexRequest,
    settings: Settings,
    *,
    background: bool,
) -> AnalysisRunModel:
    return start_analysis_run(
        db,
        case_id,
        "embed_chunks",
        provider_type=settings.llm_provider,
        model_name=settings.llm_embedding_model,
        input_parameters={
            "document_id": str(request.document_id) if request.document_id is not None else None,
            "limit": request.limit,
            "force_reindex": request.force_reindex,
            "collection_name": chunk_collection_name(settings),
            "embedding_batch_size": settings.embedding_batch_size,
            "background": background,
        },
        output_schema_name="chunk_embeddings",
        output_schema_version="v1",
        retrieval_strategy="embedding_index",
    )


def _process_chunk_index_run(
    db: Session,
    case_id: UUID,
    request: ChunkIndexRequest,
    settings: Settings,
    run: AnalysisRunModel,
) -> ChunkIndexResult:
    try:
        chunks = _chunks_to_index(db, case_id, request)
        skipped_count = max(0, _current_chunk_count(db, case_id, request.document_id) - len(chunks))
        if not chunks:
            finish_analysis_run(
                db,
                run,
                status="succeeded",
                validation_status="passed",
                output_summary={"indexed_count": 0, "skipped_count": skipped_count},
            )
            return ChunkIndexResult(run.id, 0, skipped_count, chunk_collection_name(settings), settings.llm_embedding_model)

        for index, chunk in enumerate(chunks, start=1):
            add_analysis_run_input(
                db,
                run.id,
                "chunk",
                index,
                document_id=chunk.document_id,
                chunk_id=chunk.id,
                payload_json={"input_kind": "chunk_embedding", "chunk_index": chunk.chunk_index},
            )
        db.commit()

        indexed_count = 0
        vector_index = QdrantChunkIndex(settings)
        for embedding_batch in embed_chunks_in_batches(settings, chunks):
            vector_index.upsert_chunks(embedding_batch.chunks, embedding_batch.embeddings)
            for chunk in embedding_batch.chunks:
                indexed_count += 1
                chunk.embedding_provider = settings.llm_provider
                chunk.embedding_model = settings.llm_embedding_model
                chunk.embedding_vector_id = str(chunk.id)
                chunk.chunk_run_id = run.id
                db.add(chunk)
                add_analysis_run_output(db, run.id, "chunk", chunk.id, indexed_count)
            db.commit()

        finish_analysis_run(
            db,
            run,
            status="succeeded",
            validation_status="passed",
            output_summary={
                "indexed_count": indexed_count,
                "skipped_count": skipped_count,
                "collection_name": chunk_collection_name(settings),
                "embedding_model": settings.llm_embedding_model,
                "embedding_batch_size": settings.embedding_batch_size,
                "embedding_batch_count": _batch_count(len(chunks), settings.embedding_batch_size),
            },
        )
        db.commit()
        return ChunkIndexResult(run.id, indexed_count, skipped_count, chunk_collection_name(settings), settings.llm_embedding_model)
    except (LLMProviderError, VectorIndexError, ValueError) as exc:
        if run.status == "running":
            finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=str(exc))
        raise VectorIndexError(str(exc)) from exc


def semantic_chunk_search(
    db: Session,
    case_id: UUID,
    query: str,
    limit: int,
    document_id: UUID | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
) -> list[KeywordSearchHit]:
    settings = get_settings()
    ensure_semantic_index_ready(db, case_id, document_id)
    embedding_result = get_llm_provider(settings).embeddings(settings.llm_embedding_model, [query])
    semantic_hits = QdrantChunkIndex(settings).search(
        case_id=case_id,
        query_embedding=embedding_result.embeddings[0],
        limit=limit,
        document_id=document_id,
        page_start=page_start,
        page_end=page_end,
    )
    hits: list[KeywordSearchHit] = []
    for semantic_hit in semantic_hits:
        chunk = db.get(DocumentChunkModel, semantic_hit.chunk_id)
        if chunk is None or chunk.case_id != case_id or not chunk.is_current:
            continue
        document = db.get(DocumentModel, chunk.document_id)
        if document is None or document.case_id != case_id:
            continue
        hits.append(
            KeywordSearchHit(
                source_type="chunk",
                document_id=chunk.document_id,
                document_name=document.original_filename,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                quote=None,
                score=semantic_hit.score,
                match_type=semantic_hit.match_type,
            )
        )
    return hits


def hybrid_chunk_search(
    db: Session,
    case_id: UUID,
    query: str,
    keyword_hits: list[KeywordSearchHit],
    limit: int,
    document_id: UUID | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
) -> list[KeywordSearchHit]:
    semantic_hits = semantic_chunk_search(db, case_id, query, limit, document_id, page_start, page_end)
    max_keyword_score = max((hit.score for hit in keyword_hits if hit.chunk_id is not None), default=0.0)
    candidates: dict[UUID, HybridRankCandidate] = {}
    for rank, hit in enumerate(keyword_hits, start=1):
        if hit.chunk_id is not None:
            candidates[hit.chunk_id] = HybridRankCandidate(
                hit=hit,
                keyword_score=_normalize_keyword_score(hit.score, max_keyword_score),
                semantic_score=0.0,
                keyword_rank=rank,
                semantic_rank=None,
                exact_phrase_match=_has_exact_phrase(query, hit.quote),
            )
    for rank, hit in enumerate(semantic_hits, start=1):
        if hit.chunk_id is None:
            continue
        semantic_score = _normalize_semantic_score(hit.score)
        existing = candidates.get(hit.chunk_id)
        if existing is None:
            candidates[hit.chunk_id] = HybridRankCandidate(
                hit=KeywordSearchHit(**{**hit.__dict__, "match_type": "semantic"}),
                keyword_score=0.0,
                semantic_score=semantic_score,
                keyword_rank=None,
                semantic_rank=rank,
                exact_phrase_match=False,
            )
        else:
            candidates[hit.chunk_id] = HybridRankCandidate(
                hit=KeywordSearchHit(**{**existing.hit.__dict__, "match_type": "hybrid"}),
                keyword_score=existing.keyword_score,
                semantic_score=semantic_score,
                keyword_rank=existing.keyword_rank,
                semantic_rank=rank,
                exact_phrase_match=existing.exact_phrase_match,
            )
    ranked_hits = [_ranked_hybrid_hit(candidate) for candidate in candidates.values()]
    return sorted(
        ranked_hits,
        key=lambda item: (-item.score, item.document_name, item.page_start, item.chunk_index or 0),
    )[:limit]


def get_chunk_index_status(db: Session, case_id: UUID, document_id: UUID | None = None) -> ChunkIndexStatus:
    settings = get_settings()
    current_chunk_count = _current_chunk_count(db, case_id, document_id)
    indexed_chunk_count = _indexed_chunk_count(db, case_id, document_id, settings.llm_embedding_model)
    missing_chunk_count = max(0, current_chunk_count - indexed_chunk_count)
    latest_run = _latest_chunk_index_run(db, case_id)
    latest_run_input_count = _run_chunk_input_count(db, latest_run.id) if latest_run is not None else 0
    latest_run_output_count = _run_chunk_output_count(db, latest_run.id) if latest_run is not None else 0
    latest_run_progress_percent = (
        round((latest_run_output_count / latest_run_input_count) * 100, 1) if latest_run_input_count > 0 else None
    )
    return ChunkIndexStatus(
        case_id=case_id,
        document_id=document_id,
        collection_name=chunk_collection_name(settings),
        embedding_model=settings.llm_embedding_model,
        current_chunk_count=current_chunk_count,
        indexed_chunk_count=indexed_chunk_count,
        missing_chunk_count=missing_chunk_count,
        is_ready=current_chunk_count > 0 and missing_chunk_count == 0,
        needs_indexing=current_chunk_count > 0 and missing_chunk_count > 0,
        latest_run_id=latest_run.id if latest_run is not None else None,
        latest_run_status=latest_run.status if latest_run is not None else None,
        latest_run_validation_status=latest_run.validation_status if latest_run is not None else None,
        latest_run_started_at=latest_run.started_at if latest_run is not None else None,
        latest_run_finished_at=latest_run.finished_at if latest_run is not None else None,
        latest_run_input_count=latest_run_input_count,
        latest_run_output_count=latest_run_output_count,
        latest_run_progress_percent=latest_run_progress_percent,
    )


def ensure_semantic_index_ready(db: Session, case_id: UUID, document_id: UUID | None = None) -> None:
    index_status = get_chunk_index_status(db, case_id, document_id)
    if index_status.current_chunk_count == 0:
        raise VectorIndexError("Nincs indexelheto aktualis szovegresz ebben a forraskorben.")
    if not index_status.is_ready:
        raise VectorIndexError(
            "A szemantikus vagy hybrid kereséshez előbb indexelni kell az aktuális forráskör chunkjait "
            f"az aktuális embedding modellel ({index_status.embedding_model}). "
            f"Indexelve: {index_status.indexed_chunk_count}/{index_status.current_chunk_count}."
        )


def _ranked_hybrid_hit(candidate: HybridRankCandidate) -> KeywordSearchHit:
    overlap_bonus = HYBRID_OVERLAP_BONUS if candidate.keyword_rank is not None and candidate.semantic_rank is not None else 0.0
    exact_phrase_bonus = HYBRID_EXACT_PHRASE_BONUS if candidate.exact_phrase_match else 0.0
    score = (
        (candidate.keyword_score * HYBRID_KEYWORD_WEIGHT)
        + (candidate.semantic_score * HYBRID_SEMANTIC_WEIGHT)
        + overlap_bonus
        + exact_phrase_bonus
    )
    return KeywordSearchHit(**{**candidate.hit.__dict__, "score": round(score, 6)})


def _normalize_keyword_score(score: float, max_score: float) -> float:
    if max_score <= 0:
        return 0.0
    return _clamp_score(score / max_score)


def _normalize_semantic_score(score: float) -> float:
    return _clamp_score(score)


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _has_exact_phrase(query: str, text: str | None) -> bool:
    if not text:
        return False
    normalized_query = " ".join(query.casefold().split())
    if not normalized_query:
        return False
    normalized_text = " ".join(text.casefold().split())
    return normalized_query in normalized_text


def embed_chunks_in_batches(settings: Settings, chunks: list[DocumentChunkModel]) -> Iterator[EmbeddingBatch]:
    batch_size = _valid_embedding_batch_size(settings.embedding_batch_size)
    provider = get_llm_provider(settings)
    for batch_start in range(0, len(chunks), batch_size):
        batch_chunks = chunks[batch_start : batch_start + batch_size]
        embedding_result = provider.embeddings(settings.llm_embedding_model, [chunk.chunk_text for chunk in batch_chunks])
        yield EmbeddingBatch(chunks=batch_chunks, embeddings=embedding_result.embeddings)


def _chunks_to_index(db: Session, case_id: UUID, request: ChunkIndexRequest) -> list[DocumentChunkModel]:
    stmt = (
        select(DocumentChunkModel)
        .where(DocumentChunkModel.case_id == case_id, DocumentChunkModel.is_current.is_(True))
        .order_by(DocumentChunkModel.document_id.asc(), DocumentChunkModel.chunk_index.asc())
        .limit(request.limit)
    )
    if request.document_id is not None:
        stmt = stmt.where(DocumentChunkModel.document_id == request.document_id)
    if not request.force_reindex:
        stmt = stmt.where(
            or_(
                DocumentChunkModel.embedding_vector_id.is_(None),
                DocumentChunkModel.embedding_model.is_(None),
                DocumentChunkModel.embedding_model != get_settings().llm_embedding_model,
            )
        )
    return list(db.execute(stmt).scalars())


def _current_chunk_count(db: Session, case_id: UUID, document_id: UUID | None) -> int:
    stmt = select(func.count()).select_from(DocumentChunkModel).where(DocumentChunkModel.case_id == case_id, DocumentChunkModel.is_current.is_(True))
    if document_id is not None:
        stmt = stmt.where(DocumentChunkModel.document_id == document_id)
    return int(db.execute(stmt).scalar_one())


def _indexed_chunk_count(db: Session, case_id: UUID, document_id: UUID | None, embedding_model: str) -> int:
    stmt = (
        select(func.count())
        .select_from(DocumentChunkModel)
        .where(
            DocumentChunkModel.case_id == case_id,
            DocumentChunkModel.is_current.is_(True),
            DocumentChunkModel.embedding_model == embedding_model,
            DocumentChunkModel.embedding_vector_id.is_not(None),
        )
    )
    if document_id is not None:
        stmt = stmt.where(DocumentChunkModel.document_id == document_id)
    return int(db.execute(stmt).scalar_one())


def _latest_chunk_index_run(db: Session, case_id: UUID) -> AnalysisRunModel | None:
    stmt = (
        select(AnalysisRunModel)
        .where(AnalysisRunModel.case_id == case_id, AnalysisRunModel.run_type == "embed_chunks")
        .order_by(AnalysisRunModel.started_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def _run_chunk_input_count(db: Session, analysis_run_id: UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(AnalysisRunInputModel)
        .where(AnalysisRunInputModel.analysis_run_id == analysis_run_id, AnalysisRunInputModel.input_type == "chunk")
    )
    return int(db.execute(stmt).scalar_one())


def _run_chunk_output_count(db: Session, analysis_run_id: UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(AnalysisRunOutputModel)
        .where(AnalysisRunOutputModel.analysis_run_id == analysis_run_id, AnalysisRunOutputModel.output_type == "chunk")
    )
    return int(db.execute(stmt).scalar_one())


def chunk_collection_name(settings: Settings) -> str:
    model_suffix = re.sub(r"[^a-zA-Z0-9_]+", "_", settings.llm_embedding_model).strip("_").lower()
    if not model_suffix:
        return settings.qdrant_chunk_collection
    return f"{settings.qdrant_chunk_collection}_{model_suffix}"


def _valid_embedding_batch_size(value: int) -> int:
    if value < 1:
        return 1
    return value


def _batch_count(item_count: int, batch_size: int) -> int:
    batch_size = _valid_embedding_batch_size(batch_size)
    return (item_count + batch_size - 1) // batch_size


def _http_status_error_message(exc: httpx.HTTPStatusError) -> str:
    detail = exc.response.text.strip()
    if detail:
        return f"{exc.response.status_code} {exc.response.reason_phrase}: {detail}"
    return str(exc)
