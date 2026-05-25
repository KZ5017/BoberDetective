from pathlib import Path
from uuid import uuid4
import json

import httpx

from app.core.config import Settings
from app.models.document import DocumentChunkModel, DocumentModel
from app.services.search import KeywordSearchHit
from app.schemas.search import ChunkIndexRequest
from app.services.llm import LLMEmbeddingResult
from app.services.vector_index import QdrantChunkIndex, SemanticChunkHit, _chunks_to_index, embed_chunks_in_batches, hybrid_chunk_search, semantic_chunk_search


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
        llm_chat_context_length=30720,
        llm_embedding_context_length=12288,
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
    document_id = uuid4()
    chunk_id = uuid4()
    captured_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"result": [{"score": 0.91, "payload": {"chunk_id": str(chunk_id)}}]},
        )

    client = httpx.Client(base_url="http://qdrant.local", transport=httpx.MockTransport(handler))

    hits = QdrantChunkIndex(_settings(), client).search(
        case_id=case_id,
        document_id=document_id,
        query_embedding=[0.1, 0.2],
        limit=3,
        page_start=50,
        page_end=120,
    )

    assert hits[0].chunk_id == chunk_id
    assert hits[0].score == 0.91
    assert captured_payload["filter"]["must"][0]["match"]["value"] == str(case_id)
    assert captured_payload["filter"]["must"][1]["match"]["value"] is True
    assert captured_payload["filter"]["must"][2]["match"]["value"] == str(document_id)
    assert captured_payload["filter"]["must"][3]["range"]["gte"] == 50
    assert captured_payload["filter"]["must"][4]["range"]["lte"] == 120


def test_qdrant_chunk_index_search_filters_by_multiple_documents() -> None:
    case_id = uuid4()
    document_ids = [uuid4(), uuid4()]
    captured_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content))
        return httpx.Response(200, json={"result": []})

    client = httpx.Client(base_url="http://qdrant.local", transport=httpx.MockTransport(handler))

    QdrantChunkIndex(_settings(), client).search(
        case_id=case_id,
        document_ids=document_ids,
        query_embedding=[0.1, 0.2],
        limit=3,
    )

    assert captured_payload["filter"]["must"][2]["match"]["any"] == [str(item) for item in document_ids]


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
    assert hits[0].score == 1.045
    assert hits[0].match_type == "hybrid"


def test_hybrid_chunk_search_prioritizes_keyword_semantic_overlap(monkeypatch) -> None:
    case_id = uuid4()
    overlap_chunk_id = uuid4()
    semantic_only_chunk_id = uuid4()
    keyword_hit = KeywordSearchHit(
        source_type="chunk",
        document_id=uuid4(),
        document_name="irat.txt",
        page_start=2,
        page_end=2,
        score=0.1,
        chunk_id=overlap_chunk_id,
        chunk_index=2,
        quote="gyilkossag helyszine",
    )
    semantic_hits = [
        KeywordSearchHit(
            source_type="chunk",
            document_id=keyword_hit.document_id,
            document_name="irat.txt",
            page_start=3,
            page_end=3,
            score=0.95,
            chunk_id=semantic_only_chunk_id,
            chunk_index=3,
            match_type="semantic",
        ),
        KeywordSearchHit(
            source_type="chunk",
            document_id=keyword_hit.document_id,
            document_name="irat.txt",
            page_start=2,
            page_end=2,
            score=0.5,
            chunk_id=overlap_chunk_id,
            chunk_index=2,
            match_type="semantic",
        ),
    ]

    monkeypatch.setattr("app.services.vector_index.semantic_chunk_search", lambda *args, **kwargs: semantic_hits)

    hits = hybrid_chunk_search(object(), case_id, "gyilkossag helyszine", [keyword_hit], 5)

    assert [hit.chunk_id for hit in hits] == [overlap_chunk_id, semantic_only_chunk_id]
    assert hits[0].match_type == "hybrid"
    assert hits[0].score > hits[1].score


def test_semantic_chunk_search_skips_inactive_documents(monkeypatch) -> None:
    case_id = uuid4()
    active_document_id = uuid4()
    inactive_document_id = uuid4()
    active_chunk_id = uuid4()
    inactive_chunk_id = uuid4()
    active_chunk = DocumentChunkModel(
        id=active_chunk_id,
        case_id=case_id,
        document_id=active_document_id,
        page_start=1,
        page_end=1,
        chunk_index=0,
        chunk_text="aktiv szoveg",
        chunking_strategy="char_window_v1",
        chunker_version="1",
        version_no=1,
        is_current=True,
    )
    inactive_chunk = DocumentChunkModel(
        id=inactive_chunk_id,
        case_id=case_id,
        document_id=inactive_document_id,
        page_start=2,
        page_end=2,
        chunk_index=1,
        chunk_text="kizart szoveg",
        chunking_strategy="char_window_v1",
        chunker_version="1",
        version_no=1,
        is_current=True,
    )
    active_document = DocumentModel(
        id=active_document_id,
        case_id=case_id,
        original_filename="aktiv.pdf",
        stored_path="/tmp/aktiv.pdf",
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=12,
        sha256_hash="a" * 64,
        imported_by_user_id=uuid4(),
        processing_status="processed",
        lifecycle_status="active",
    )
    inactive_document = DocumentModel(
        id=inactive_document_id,
        case_id=case_id,
        original_filename="kizart.pdf",
        stored_path="/tmp/kizart.pdf",
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=12,
        sha256_hash="b" * 64,
        imported_by_user_id=uuid4(),
        processing_status="processed",
        lifecycle_status="excluded",
    )

    class FakeProvider:
        def embeddings(self, model: str, texts: list[str]) -> LLMEmbeddingResult:
            return LLMEmbeddingResult(model=model, embeddings=[[0.1, 0.2]])

    class FakeIndex:
        def __init__(self, settings) -> None:
            self.settings = settings

        def search(self, **kwargs):
            return [
                SemanticChunkHit(chunk_id=inactive_chunk_id, score=0.99, match_type="semantic"),
                SemanticChunkHit(chunk_id=active_chunk_id, score=0.75, match_type="semantic"),
            ]

    class FakeDb:
        def get(self, model, object_id):
            return {
                (DocumentChunkModel, active_chunk_id): active_chunk,
                (DocumentChunkModel, inactive_chunk_id): inactive_chunk,
                (DocumentModel, active_document_id): active_document,
                (DocumentModel, inactive_document_id): inactive_document,
            }.get((model, object_id))

    monkeypatch.setattr("app.services.vector_index.ensure_semantic_index_ready", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.vector_index.get_settings", lambda: _settings())
    monkeypatch.setattr("app.services.vector_index.get_llm_provider", lambda settings: FakeProvider())
    monkeypatch.setattr("app.services.vector_index.QdrantChunkIndex", FakeIndex)

    hits = semantic_chunk_search(FakeDb(), case_id, "kerdes", 10)

    assert [hit.document_id for hit in hits] == [active_document_id]


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
