from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.knowledge import KnowledgeAnswerPayload, KnowledgeQueryRequest
from app.services.knowledge_import import KnowledgeStoredChunk
from app.services.knowledge_indexing import QdrantKnowledgeIndex
from app.services.knowledge_query import (
    KnowledgeRetrievedChunk,
    build_knowledge_query_user_prompt,
    parse_knowledge_answer_payload,
    parse_knowledge_llm_json_object,
    run_knowledge_query,
    _keyword_knowledge_search,
)


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


def test_knowledge_query_endpoint_wraps_service_response(monkeypatch) -> None:
    response_payload = _query_response()
    captured = {}

    def fake_run(db, payload):
        captured["payload"] = payload
        return response_payload

    monkeypatch.setattr("app.api.v1.knowledge.run_knowledge_query", fake_run)

    response = TestClient(create_app()).post(
        "/api/v1/knowledge/query",
        json={"question": "Mi a SUID?", "retrieval_strategy": "keyword"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]["answer_text"] == "Válasz."
    assert body["used_sources"][0]["heading_path"] == "Linux > SUID"
    assert captured["payload"].question == "Mi a SUID?"


def test_keyword_knowledge_search_uses_markdown_chunks(monkeypatch) -> None:
    document = _document()
    chunks = [
        _chunk("A sudoers nem releváns.", chunk_index=0),
        _chunk("A SUID bináris jogosultságemelési jegyzet.", chunk_index=1, heading_path="Linux > SUID"),
    ]
    monkeypatch.setattr("app.services.knowledge_query.read_knowledge_chunks", lambda item: chunks)

    hits = _keyword_knowledge_search([document], "SUID jogosultságemelés", 5)

    assert len(hits) == 1
    assert hits[0].document.id == document.id
    assert hits[0].chunk.heading_path == "Linux > SUID"
    assert hits[0].match_type == "keyword"


def test_qdrant_knowledge_search_filters_knowledge_payload() -> None:
    document_id = uuid4()
    chunk_id = str(uuid4())
    captured_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"result": [{"score": 0.88, "payload": {"knowledge_document_id": str(document_id), "chunk_id": chunk_id}}]},
        )

    client = httpx.Client(base_url="http://qdrant.local", transport=httpx.MockTransport(handler))

    hits = QdrantKnowledgeIndex(_settings(), client).search(
        query_embedding=[0.1, 0.2],
        limit=3,
        document_ids=[document_id],
    )

    assert hits[0].knowledge_document_id == document_id
    assert hits[0].chunk_id == chunk_id
    assert captured_payload["filter"]["must"][0]["key"] == "document_kind"
    assert captured_payload["filter"]["must"][1]["key"] == "is_current"
    assert captured_payload["filter"]["must"][2]["key"] == "knowledge_document_id"
    assert "case_id" not in json.dumps(captured_payload)


def test_build_knowledge_query_user_prompt_includes_heading_sources() -> None:
    prompt = build_knowledge_query_user_prompt(
        "Mi a SUID?",
        "detailed",
        [KnowledgeRetrievedChunk("source_1", _document(), _chunk("SUID szöveg.", heading_path="Linux > SUID"), 1.0, "keyword")],
    )

    assert "QUERY:\nMi a SUID?" in prompt
    assert "ANSWER_MODE:\ndetailed" in prompt
    assert "[source_1]" in prompt
    assert "document: note.md" in prompt
    assert "heading_path: Linux > SUID" in prompt
    assert "SUID szöveg." in prompt


def test_parse_knowledge_answer_payload_requires_boolean_insufficient_source() -> None:
    with pytest.raises(Exception):
        parse_knowledge_answer_payload(
            {"answer_text": "Válasz.", "source_summary": "", "insufficient_source": "false"},
            "detailed",
        )


def test_parse_knowledge_llm_json_object_recovers_unescaped_newline() -> None:
    parsed = parse_knowledge_llm_json_object(
        '{"answer_text":"Első sor\nMásodik sor","source_summary":"Forrás.","insufficient_source":false}'
    )

    assert parsed["answer_text"] == "Első sor\nMásodik sor"
    assert parsed["insufficient_source"] is False


def test_run_knowledge_query_returns_placeholder_without_sources(monkeypatch) -> None:
    monkeypatch.setattr("app.services.knowledge_query.select_knowledge_source_chunks", lambda db, payload: [])

    response = run_knowledge_query(object(), KnowledgeQueryRequest(question="Nincs ilyen", retrieval_strategy="keyword"))

    assert response.answer.insufficient_source is True
    assert response.used_sources == []
    assert response.retrieval_metadata.selected_chunk_count == 0
    assert response.can_save is False


def _query_response():
    from app.schemas.knowledge import KnowledgeQueryResponse, KnowledgeRetrievalMetadata, KnowledgeUsedSource

    return KnowledgeQueryResponse(
        answer=KnowledgeAnswerPayload(
            answer_text="Válasz.",
            source_summary="Forrás.",
            insufficient_source=False,
            answer_mode="detailed",
        ),
        used_sources=[
            KnowledgeUsedSource(
                knowledge_document_id=uuid4(),
                original_filename="note.md",
                relative_path="notes/note.md",
                chunk_id=str(uuid4()),
                chunk_index=0,
                heading_path="Linux > SUID",
                quote_preview="SUID szöveg.",
            )
        ],
        retrieval_metadata=KnowledgeRetrievalMetadata(
            retrieval_strategy="keyword",
            max_chunks=45,
            selected_chunk_count=1,
            document_count=1,
        ),
    )


def _document() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        original_filename="note.md",
        relative_path="notes/note.md",
        document_kind="markdown_note",
        processing_status="processed",
        imported_at=datetime.now(UTC),
    )


def _chunk(text: str, *, chunk_index: int = 0, heading_path: str = "Linux") -> KnowledgeStoredChunk:
    return KnowledgeStoredChunk(
        chunk_id=str(uuid4()),
        chunk_index=chunk_index,
        heading_path=heading_path,
        heading_level=2,
        char_start=0,
        char_end=len(text),
        text=text,
        contains_code_block=False,
        code_languages=[],
        wikilinks=[],
        tags=[],
        frontmatter_tags=[],
        quality_flags=[],
    )
