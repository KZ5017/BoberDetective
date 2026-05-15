from pathlib import Path
from uuid import uuid4
import json

import httpx

from app.core.config import Settings
from app.models.document import DocumentChunkModel
from app.services.search import KeywordSearchHit
from app.schemas.search import ChunkIndexRequest
from app.services.llm import LLMEmbeddingResult
from app.services.vector_index import QdrantChunkIndex, _chunks_to_index, embed_chunks_in_batches, hybrid_chunk_search


def _settings() -> Settings:
    return Settings(
        environment="test",
        data_root=Path("/tmp/boberdetective-test"),
        api_prefix="/api/v1",
        database_url="postgresql+psycopg://example",
        llm_provider="lm_studio",
        llm_base_url="http://llm.local/v1",
        llm_api_key="secret",
        llm_chat_model="chat-model",
        llm_embedding_model="embedding-model",
        llm_timeout_seconds=1,
        llm_context_length=12288,
        llm_eval_batch_size=6144,
        llm_flash_attention=True,
        llm_offload_kv_cache_to_gpu=True,
        llm_auto_load_chat_model=True,
        llm_auto_load_embedding_model=True,
        embedding_batch_size=2,
        pdf_parser="docling_then_pypdf",
        tesseract_cmd="tesseract",
        tesseract_languages="hun+eng",
        max_upload_bytes=1024,
        qdrant_url="http://qdrant.local",
        qdrant_chunk_collection="chunks",
    )


def test_qdrant_chunk_index_creates_collection_and_upserts_points() -> None:
    requests: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, payload))
        if request.method == "GET":
            return httpx.Response(404, json={})
        return httpx.Response(200, json={"result": True})

    client = httpx.Client(base_url="http://qdrant.local", transport=httpx.MockTransport(handler))
    chunk = DocumentChunkModel(
        id=uuid4(),
        case_id=uuid4(),
        document_id=uuid4(),
        page_start=1,
        page_end=1,
        chunk_index=0,
        chunk_text="A forras szovege.",
        chunking_strategy="char_window_v1",
        chunker_version="1",
        version_no=1,
        is_current=True,
    )

    QdrantChunkIndex(_settings(), client).upsert_chunks([chunk], [[0.1, 0.2, 0.3]])

    assert ("GET", "/collections/chunks_embedding_model", None) in requests
    assert requests[1] == ("PUT", "/collections/chunks_embedding_model", {"vectors": {"size": 3, "distance": "Cosine"}})
    assert requests[2][0] == "PUT"
    assert requests[2][1] == "/collections/chunks_embedding_model/points"
    assert requests[2][2]["points"][0]["id"] == str(chunk.id)
    assert requests[2][2]["points"][0]["payload"]["case_id"] == str(chunk.case_id)


def test_qdrant_chunk_index_search_filters_by_case_and_current_payload() -> None:
    case_id = uuid4()
    chunk_id = uuid4()
    captured_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"result": [{"score": 0.91, "payload": {"chunk_id": str(chunk_id)}}]},
        )

    client = httpx.Client(base_url="http://qdrant.local", transport=httpx.MockTransport(handler))

    hits = QdrantChunkIndex(_settings(), client).search(case_id=case_id, query_embedding=[0.1, 0.2], limit=3)

    assert hits[0].chunk_id == chunk_id
    assert hits[0].score == 0.91
    assert captured_payload["filter"]["must"][0]["match"]["value"] == str(case_id)
    assert captured_payload["filter"]["must"][1]["match"]["value"] is True


def test_hybrid_chunk_search_merges_keyword_and_semantic_hits(monkeypatch) -> None:
    case_id = uuid4()
    chunk_id = uuid4()
    keyword_hit = KeywordSearchHit(
        source_type="chunk",
        document_id=uuid4(),
        document_name="irat.txt",
        page_start=1,
        page_end=1,
        score=0.2,
        chunk_id=chunk_id,
        chunk_index=0,
    )
    semantic_hit = KeywordSearchHit(
        source_type="chunk",
        document_id=keyword_hit.document_id,
        document_name="irat.txt",
        page_start=1,
        page_end=1,
        score=0.9,
        chunk_id=chunk_id,
        chunk_index=0,
        match_type="semantic",
    )

    monkeypatch.setattr("app.services.vector_index.semantic_chunk_search", lambda *args, **kwargs: [semantic_hit])

    hits = hybrid_chunk_search(object(), case_id, "kerdes", [keyword_hit], 5)

    assert len(hits) == 1
    assert hits[0].chunk_id == chunk_id
    assert hits[0].score == 0.9
    assert hits[0].match_type == "hybrid"


def test_embed_chunks_in_batches_splits_embedding_requests(monkeypatch) -> None:
    calls: list[list[str]] = []

    class FakeProvider:
        def embeddings(self, model: str, texts: list[str]) -> LLMEmbeddingResult:
            calls.append(texts)
            return LLMEmbeddingResult(model=model, embeddings=[[float(len(calls)), 0.0] for _ in texts])

    chunks = [
        DocumentChunkModel(
            id=uuid4(),
            case_id=uuid4(),
            document_id=uuid4(),
            page_start=1,
            page_end=1,
            chunk_index=index,
            chunk_text=f"chunk {index}",
            chunking_strategy="char_window_v1",
            chunker_version="1",
            version_no=1,
            is_current=True,
        )
        for index in range(5)
    ]
    monkeypatch.setattr("app.services.vector_index.get_llm_provider", lambda settings: FakeProvider())

    batches = list(embed_chunks_in_batches(_settings(), chunks))

    assert calls == [["chunk 0", "chunk 1"], ["chunk 2", "chunk 3"], ["chunk 4"]]
    assert [len(batch.chunks) for batch in batches] == [2, 2, 1]
    assert [batch.embeddings[0][0] for batch in batches] == [1.0, 2.0, 3.0]


def test_chunks_to_index_reindexes_chunks_from_a_different_embedding_model(monkeypatch) -> None:
    captured_stmt = None

    class FakeResult:
        def scalars(self) -> list:
            return []

    class FakeDb:
        def execute(self, stmt):
            nonlocal captured_stmt
            captured_stmt = stmt
            return FakeResult()

    monkeypatch.setattr("app.services.vector_index.get_settings", lambda: _settings())

    _chunks_to_index(FakeDb(), uuid4(), ChunkIndexRequest(force_reindex=False))

    compiled = str(captured_stmt)
    assert "document_chunks.embedding_vector_id IS NULL" in compiled
    assert "document_chunks.embedding_model IS NULL" in compiled
    assert "document_chunks.embedding_model !=" in compiled
