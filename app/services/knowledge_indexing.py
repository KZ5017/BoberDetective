from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.knowledge import KnowledgeDocumentModel
from app.schemas.knowledge import KnowledgeIndexRequest
from app.services.knowledge_import import KnowledgeStoredChunk, read_knowledge_chunks
from app.services.llm import LLMProviderError, get_llm_provider
from app.services.vector_index import VectorIndexError


class KnowledgeIndexError(RuntimeError):
    pass


@dataclass(frozen=True)
class KnowledgeIndexResult:
    indexed_document_count: int
    indexed_chunk_count: int
    skipped_document_count: int
    collection_name: str
    embedding_model: str


@dataclass(frozen=True)
class KnowledgeIndexStatus:
    collection_name: str
    embedding_model: str
    document_count: int
    chunk_count: int
    indexed_document_count: int
    indexed_chunk_count: int
    missing_document_count: int
    missing_chunk_count: int
    is_ready: bool
    needs_indexing: bool


@dataclass(frozen=True)
class KnowledgeEmbeddingBatch:
    document: KnowledgeDocumentModel
    chunks: list[KnowledgeStoredChunk]
    embeddings: list[list[float]]


@dataclass(frozen=True)
class KnowledgeSemanticHit:
    knowledge_document_id: UUID
    chunk_id: str
    score: float
    match_type: str = "semantic"


class QdrantKnowledgeIndex:
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = client

    @property
    def collection_name(self) -> str:
        return knowledge_collection_name(self._settings)

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
            raise KnowledgeIndexError(_http_status_error_message(exc)) from exc
        except httpx.HTTPError as exc:
            raise KnowledgeIndexError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

    def upsert_chunks(
        self,
        document: KnowledgeDocumentModel,
        chunks: list[KnowledgeStoredChunk],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise KnowledgeIndexError("Knowledge chunk and embedding counts differ")
        if not chunks:
            return
        self.ensure_collection(len(embeddings[0]))
        points = [
            {
                "id": chunk.chunk_id,
                "vector": embedding,
                "payload": {
                    "knowledge_document_id": str(document.id),
                    "chunk_id": chunk.chunk_id,
                    "chunk_index": chunk.chunk_index,
                    "document_kind": document.document_kind,
                    "original_filename": document.original_filename,
                    "relative_path": document.relative_path,
                    "heading_path": chunk.heading_path,
                    "heading_level": chunk.heading_level,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "contains_code_block": chunk.contains_code_block,
                    "code_languages": chunk.code_languages,
                    "tags": chunk.tags,
                    "frontmatter_tags": chunk.frontmatter_tags,
                    "is_current": document.processing_status != "archived",
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
            raise KnowledgeIndexError(_http_status_error_message(exc)) from exc
        except httpx.HTTPError as exc:
            raise KnowledgeIndexError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

    def search(
        self,
        *,
        query_embedding: list[float],
        limit: int,
        document_ids: list[UUID] | None = None,
    ) -> list[KnowledgeSemanticHit]:
        filter_must = [
            {"key": "document_kind", "match": {"value": "markdown_note"}},
            {"key": "is_current", "match": {"value": True}},
        ]
        if document_ids:
            filter_must.append(
                {"key": "knowledge_document_id", "match": {"any": [str(item) for item in document_ids]}}
            )
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
            if response.status_code == 404:
                return []
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise KnowledgeIndexError(_http_status_error_message(exc)) from exc
        except httpx.HTTPError as exc:
            raise KnowledgeIndexError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

        result = payload.get("result")
        if not isinstance(result, list):
            raise KnowledgeIndexError("Qdrant returned an invalid knowledge search payload")
        hits: list[KnowledgeSemanticHit] = []
        for item in result:
            if not isinstance(item, dict) or not isinstance(item.get("payload"), dict):
                continue
            item_payload = item["payload"]
            document_id = item_payload.get("knowledge_document_id")
            chunk_id = item_payload.get("chunk_id")
            score = item.get("score")
            if not document_id or not chunk_id or score is None:
                continue
            hits.append(
                KnowledgeSemanticHit(
                    knowledge_document_id=UUID(str(document_id)),
                    chunk_id=str(chunk_id),
                    score=float(score),
                )
            )
        return hits

    def delete_document_points(self, knowledge_document_id: UUID) -> None:
        client = self._client or self._build_client()
        close_client = self._client is None
        try:
            response = client.post(
                f"/collections/{self.collection_name}/points/delete",
                params={"wait": "true"},
                json={
                    "filter": {
                        "must": [
                            {"key": "knowledge_document_id", "match": {"value": str(knowledge_document_id)}},
                        ]
                    }
                },
            )
            if response.status_code == 404:
                return
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise KnowledgeIndexError(_http_status_error_message(exc)) from exc
        except httpx.HTTPError as exc:
            raise KnowledgeIndexError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

    def _build_client(self) -> httpx.Client:
        return httpx.Client(base_url=self._settings.qdrant_url.rstrip("/"), timeout=30)


def index_knowledge_documents(db: Session, request: KnowledgeIndexRequest) -> KnowledgeIndexResult:
    settings = get_settings()
    documents = _documents_to_index(db, request, settings)
    document_count = _knowledge_document_count(db, request)
    skipped_document_count = max(0, document_count - len(documents))
    if not documents:
        return KnowledgeIndexResult(
            indexed_document_count=0,
            indexed_chunk_count=0,
            skipped_document_count=skipped_document_count,
            collection_name=knowledge_collection_name(settings),
            embedding_model=settings.llm_embedding_model,
        )

    indexed_document_count = 0
    indexed_chunk_count = 0
    vector_index = QdrantKnowledgeIndex(settings)
    try:
        for document in documents:
            chunks = read_knowledge_chunks(document)
            if not chunks:
                document.processing_status = "failed"
                document.updated_at = datetime.now(UTC)
                db.add(document)
                db.commit()
                continue

            for embedding_batch in embed_knowledge_chunks_in_batches(settings, document, chunks):
                vector_index.upsert_chunks(embedding_batch.document, embedding_batch.chunks, embedding_batch.embeddings)
                indexed_chunk_count += len(embedding_batch.chunks)

            document.processing_status = "indexed"
            document.embedding_provider = settings.llm_provider
            document.embedding_model = settings.llm_embedding_model
            document.vector_collection = knowledge_collection_name(settings)
            document.indexed_chunk_count = len(chunks)
            document.indexed_at = datetime.now(UTC)
            document.updated_at = datetime.now(UTC)
            db.add(document)
            db.commit()
            indexed_document_count += 1
    except (LLMProviderError, KnowledgeIndexError, ValueError) as exc:
        db.rollback()
        raise KnowledgeIndexError(str(exc)) from exc

    return KnowledgeIndexResult(
        indexed_document_count=indexed_document_count,
        indexed_chunk_count=indexed_chunk_count,
        skipped_document_count=skipped_document_count,
        collection_name=knowledge_collection_name(settings),
        embedding_model=settings.llm_embedding_model,
    )


def get_knowledge_index_status(db: Session, request: KnowledgeIndexRequest | None = None) -> KnowledgeIndexStatus:
    settings = get_settings()
    request = request or KnowledgeIndexRequest()
    documents = _knowledge_documents(db, request)
    document_count = len(documents)
    chunk_count = sum(max(0, document.chunk_count) for document in documents)
    indexed_documents = [
        document
        for document in documents
        if document.processing_status == "indexed"
        and document.embedding_model == settings.llm_embedding_model
        and document.vector_collection == knowledge_collection_name(settings)
        and document.indexed_chunk_count >= document.chunk_count
    ]
    indexed_document_count = len(indexed_documents)
    indexed_chunk_count = sum(max(0, document.indexed_chunk_count) for document in indexed_documents)
    missing_document_count = max(0, document_count - indexed_document_count)
    missing_chunk_count = max(0, chunk_count - indexed_chunk_count)
    return KnowledgeIndexStatus(
        collection_name=knowledge_collection_name(settings),
        embedding_model=settings.llm_embedding_model,
        document_count=document_count,
        chunk_count=chunk_count,
        indexed_document_count=indexed_document_count,
        indexed_chunk_count=indexed_chunk_count,
        missing_document_count=missing_document_count,
        missing_chunk_count=missing_chunk_count,
        is_ready=chunk_count > 0 and missing_chunk_count == 0,
        needs_indexing=chunk_count > 0 and missing_chunk_count > 0,
    )


def embed_knowledge_chunks_in_batches(
    settings: Settings,
    document: KnowledgeDocumentModel,
    chunks: list[KnowledgeStoredChunk],
) -> list[KnowledgeEmbeddingBatch]:
    batch_size = _valid_embedding_batch_size(settings.embedding_batch_size)
    provider = get_llm_provider(settings)
    batches: list[KnowledgeEmbeddingBatch] = []
    for batch_start in range(0, len(chunks), batch_size):
        batch_chunks = chunks[batch_start : batch_start + batch_size]
        embedding_result = provider.embeddings(settings.llm_embedding_model, [chunk.text for chunk in batch_chunks])
        batches.append(KnowledgeEmbeddingBatch(document, batch_chunks, embedding_result.embeddings))
    return batches


def knowledge_collection_name(settings: Settings) -> str:
    model_suffix = re.sub(r"[^a-zA-Z0-9_]+", "_", settings.llm_embedding_model).strip("_").lower()
    base_name = f"{settings.qdrant_chunk_collection}_knowledge"
    if not model_suffix:
        return base_name
    return f"{base_name}_{model_suffix}"


def _documents_to_index(
    db: Session,
    request: KnowledgeIndexRequest,
    settings: Settings,
) -> list[KnowledgeDocumentModel]:
    stmt = _knowledge_documents_stmt(request).order_by(
        KnowledgeDocumentModel.relative_path.asc().nulls_last(),
        KnowledgeDocumentModel.original_filename.asc(),
        KnowledgeDocumentModel.imported_at.asc(),
    )
    if not request.force_reindex:
        stmt = stmt.where(
            (KnowledgeDocumentModel.processing_status != "indexed")
            | (KnowledgeDocumentModel.embedding_model.is_(None))
            | (KnowledgeDocumentModel.embedding_model != settings.llm_embedding_model)
            | (KnowledgeDocumentModel.vector_collection.is_(None))
            | (KnowledgeDocumentModel.vector_collection != knowledge_collection_name(settings))
            | (KnowledgeDocumentModel.indexed_chunk_count < KnowledgeDocumentModel.chunk_count)
        )
    return list(db.execute(stmt.limit(request.limit)).scalars())


def _knowledge_documents(db: Session, request: KnowledgeIndexRequest) -> list[KnowledgeDocumentModel]:
    return list(db.execute(_knowledge_documents_stmt(request)).scalars())


def _knowledge_document_count(db: Session, request: KnowledgeIndexRequest) -> int:
    return len(_knowledge_documents(db, request))


def _knowledge_documents_stmt(request: KnowledgeIndexRequest):
    stmt = select(KnowledgeDocumentModel).where(
        KnowledgeDocumentModel.document_kind == "markdown_note",
        KnowledgeDocumentModel.processing_status != "archived",
    )
    if request.document_ids:
        requested_ids = list(dict.fromkeys(request.document_ids))
        stmt = stmt.where(KnowledgeDocumentModel.id.in_(requested_ids))
    return stmt


def _valid_embedding_batch_size(value: int) -> int:
    if value < 1:
        return 1
    return value


def _http_status_error_message(exc: httpx.HTTPStatusError) -> str:
    detail = exc.response.text.strip()
    if detail:
        return f"{exc.response.status_code} {exc.response.reason_phrase}: {detail}"
    return str(exc)
