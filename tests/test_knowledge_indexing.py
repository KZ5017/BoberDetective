from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import json

import httpx

from app.core.config import Settings
from app.services.knowledge_import import KnowledgeStoredChunk
from app.services.knowledge_indexing import QdrantKnowledgeIndex, embed_knowledge_chunks_in_batches, knowledge_collection_name
from app.services.llm import LLMEmbeddingResult


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
        llm_embedding_model="text-embedding-test/model",
        llm_timeout_seconds=1,
        llm_chat_context_length=112640,
        llm_embedding_context_length=4096,
        llm_eval_batch_size=4096,
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


def test_knowledge_collection_name_is_separate_from_case_chunk_collection() -> None:
    assert knowledge_collection_name(_settings()) == "chunks_knowledge_text_embedding_test_model"


def test_qdrant_knowledge_index_creates_collection_and_upserts_knowledge_payload() -> None:
    requests: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, payload))
        if request.method == "GET":
            return httpx.Response(404, json={})
        return httpx.Response(200, json={"result": True})

    client = httpx.Client(base_url="http://qdrant.local", transport=httpx.MockTransport(handler))
    document = _document()
    chunk = _chunk()

    QdrantKnowledgeIndex(_settings(), client).upsert_chunks(document, [chunk], [[0.1, 0.2, 0.3]])

    assert requests[0] == ("GET", "/collections/chunks_knowledge_text_embedding_test_model", None)
    assert requests[1] == (
        "PUT",
        "/collections/chunks_knowledge_text_embedding_test_model",
        {"vectors": {"size": 3, "distance": "Cosine"}},
    )
    assert requests[2][0] == "PUT"
    assert requests[2][1] == "/collections/chunks_knowledge_text_embedding_test_model/points"
    point = requests[2][2]["points"][0]
    assert point["id"] == chunk.chunk_id
    assert point["payload"]["knowledge_document_id"] == str(document.id)
    assert point["payload"]["document_kind"] == "markdown_note"
    assert "case_id" not in point["payload"]


def test_embed_knowledge_chunks_batches_texts(monkeypatch) -> None:
    calls: list[list[str]] = []

    class FakeProvider:
        def embeddings(self, model, texts):
            calls.append(texts)
            return LLMEmbeddingResult(model=model, embeddings=[[float(index), 0.1] for index, _ in enumerate(texts)])

    monkeypatch.setattr("app.services.knowledge_indexing.get_llm_provider", lambda settings: FakeProvider())
    chunks = [_chunk("elso"), _chunk("masodik"), _chunk("harmadik")]

    batches = embed_knowledge_chunks_in_batches(_settings(), _document(), chunks)

    assert calls == [["elso", "masodik"], ["harmadik"]]
    assert len(batches) == 2
    assert len(batches[0].embeddings) == 2
    assert len(batches[1].embeddings) == 1


def _document() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        document_kind="markdown_note",
        processing_status="processed",
        original_filename="note.md",
        relative_path="notes/note.md",
    )


def _chunk(text: str = "Markdown szoveg") -> KnowledgeStoredChunk:
    return KnowledgeStoredChunk(
        chunk_id=str(uuid4()),
        chunk_index=0,
        heading_path="Fo > Al",
        heading_level=2,
        char_start=0,
        char_end=len(text),
        text=text,
        contains_code_block=False,
        code_languages=[],
        wikilinks=[],
        tags=["tag"],
        frontmatter_tags=[],
        quality_flags=[],
    )
