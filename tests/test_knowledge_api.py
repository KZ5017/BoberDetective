from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.knowledge_import import KnowledgeImportConflictError
from app.services.knowledge_import import KnowledgeStoredChunk
from app.services.knowledge_indexing import KnowledgeIndexResult, KnowledgeIndexStatus


def test_list_knowledge_documents(monkeypatch) -> None:
    document = _document()
    monkeypatch.setattr("app.api.v1.knowledge.list_knowledge_documents", lambda db: [document])

    response = TestClient(create_app()).get("/api/v1/knowledge/documents")

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == str(document.id)
    assert data[0]["original_filename"] == "note.md"


def test_get_knowledge_document_detail_returns_chunk_previews(monkeypatch) -> None:
    document = _document()
    chunk = KnowledgeStoredChunk(
        chunk_id=str(uuid4()),
        chunk_index=0,
        heading_path="Linux > SUID",
        heading_level=2,
        char_start=0,
        char_end=25,
        text="Hasznald az `id` parancsot.",
        contains_code_block=False,
        code_languages=[],
        wikilinks=[],
        tags=[],
        frontmatter_tags=[],
        quality_flags=[],
    )
    monkeypatch.setattr("app.api.v1.knowledge.get_knowledge_document", lambda db, knowledge_document_id: document)
    monkeypatch.setattr("app.api.v1.knowledge.read_knowledge_chunks", lambda item: [chunk])

    response = TestClient(create_app()).get(f"/api/v1/knowledge/documents/{document.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["document"]["id"] == str(document.id)
    assert body["chunks"][0]["heading_path"] == "Linux > SUID"
    assert body["chunks"][0]["text_preview"] == "Hasznald az `id` parancsot."


def test_post_knowledge_document_rejects_non_markdown_before_db_use() -> None:
    response = TestClient(create_app()).post(
        "/api/v1/knowledge/documents",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 415


def test_post_knowledge_document_maps_import_response(monkeypatch) -> None:
    document = _document(chunk_count=2, frontmatter_json={"tags": ["web"]})

    async def fake_import(db, file, *, relative_path=None, conflict_strategy="fail"):
        assert relative_path == "notes"
        assert conflict_strategy == "fail"
        return SimpleNamespace(
            document=document,
            action="imported",
            warning=None,
            conflict_type=None,
            existing_document_id=None,
            replaced_document_id=None,
        )

    monkeypatch.setattr("app.api.v1.knowledge.import_knowledge_document", fake_import)

    response = TestClient(create_app()).post(
        "/api/v1/knowledge/documents",
        data={"relative_path": "notes"},
        files={"file": ("note.md", b"# Title\n\nText", "text/markdown")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["document"]["id"] == str(document.id)
    assert body["chunk_count"] == 2
    assert body["frontmatter_detected"] is True
    assert body["action"] == "imported"


def test_post_knowledge_document_accepts_skip_strategy(monkeypatch) -> None:
    document = _document(chunk_count=2)

    async def fake_import(db, file, *, relative_path=None, conflict_strategy="fail"):
        assert conflict_strategy == "skip"
        return SimpleNamespace(
            document=document,
            action="skipped",
            warning="Knowledge document with this content hash already exists",
            conflict_type="same_hash",
            existing_document_id=document.id,
            replaced_document_id=None,
        )

    monkeypatch.setattr("app.api.v1.knowledge.import_knowledge_document", fake_import)

    response = TestClient(create_app()).post(
        "/api/v1/knowledge/documents",
        data={"relative_path": "notes", "conflict_strategy": "skip"},
        files={"file": ("note.md", b"# Title\n\nText", "text/markdown")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "skipped"
    assert body["conflict_type"] == "same_hash"
    assert body["existing_document_id"] == str(document.id)


def test_post_knowledge_document_returns_structured_conflict(monkeypatch) -> None:
    document = _document(chunk_count=2)

    async def fake_import(db, file, *, relative_path=None, conflict_strategy="fail"):
        raise KnowledgeImportConflictError(
            "Knowledge document with this relative_path already exists",
            conflict_type="same_relative_path",
            existing_document=document,
        )

    monkeypatch.setattr("app.api.v1.knowledge.import_knowledge_document", fake_import)

    response = TestClient(create_app()).post(
        "/api/v1/knowledge/documents",
        data={"relative_path": "notes"},
        files={"file": ("note.md", b"# Title\n\nText", "text/markdown")},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["conflict_type"] == "same_relative_path"
    assert detail["existing_document_id"] == str(document.id)


def test_get_knowledge_index_status(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.knowledge.get_knowledge_index_status",
        lambda db: KnowledgeIndexStatus(
            collection_name="knowledge_collection",
            embedding_model="embedding-model",
            document_count=2,
            chunk_count=10,
            indexed_document_count=1,
            indexed_chunk_count=4,
            missing_document_count=1,
            missing_chunk_count=6,
            is_ready=False,
            needs_indexing=True,
        ),
    )

    response = TestClient(create_app()).get("/api/v1/knowledge/index/status")

    assert response.status_code == 200
    body = response.json()
    assert body["collection_name"] == "knowledge_collection"
    assert body["missing_chunk_count"] == 6
    assert body["needs_indexing"] is True


def test_post_knowledge_index(monkeypatch) -> None:
    captured = {}

    def fake_index(db, request):
        captured["request"] = request
        return KnowledgeIndexResult(
            indexed_document_count=1,
            indexed_chunk_count=3,
            skipped_document_count=2,
            collection_name="knowledge_collection",
            embedding_model="embedding-model",
        )

    monkeypatch.setattr("app.api.v1.knowledge.index_knowledge_documents", fake_index)

    response = TestClient(create_app()).post(
        "/api/v1/knowledge/index",
        json={"document_ids": [], "force_reindex": True, "limit": 50},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["indexed_document_count"] == 1
    assert body["indexed_chunk_count"] == 3
    assert body["skipped_document_count"] == 2
    assert captured["request"].force_reindex is True
    assert captured["request"].limit == 50


def test_archive_knowledge_document_endpoint(monkeypatch) -> None:
    document = _document()
    document.processing_status = "archived"
    monkeypatch.setattr("app.api.v1.knowledge.archive_knowledge_document", lambda db, knowledge_document_id: document)

    response = TestClient(create_app()).post(f"/api/v1/knowledge/documents/{document.id}/archive")

    assert response.status_code == 200
    assert response.json()["processing_status"] == "archived"


def test_restore_knowledge_document_endpoint(monkeypatch) -> None:
    document = _document()
    document.processing_status = "processed"
    monkeypatch.setattr("app.api.v1.knowledge.restore_knowledge_document", lambda db, knowledge_document_id: document)

    response = TestClient(create_app()).post(f"/api/v1/knowledge/documents/{document.id}/restore")

    assert response.status_code == 200
    assert response.json()["processing_status"] == "processed"


def test_delete_knowledge_document_endpoint(monkeypatch) -> None:
    deleted = {}

    def fake_delete(db, knowledge_document_id):
        deleted["id"] = knowledge_document_id

    document_id = uuid4()
    monkeypatch.setattr("app.api.v1.knowledge.delete_knowledge_document", fake_delete)

    response = TestClient(create_app()).delete(f"/api/v1/knowledge/documents/{document_id}")

    assert response.status_code == 204
    assert deleted["id"] == document_id


def _document(*, chunk_count: int = 1, frontmatter_json: dict | None = None) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid4(),
        original_filename="note.md",
        relative_path=None,
        mime_type="text/markdown",
        file_extension=".md",
        file_size_bytes=24,
        sha256_hash="a" * 64,
        document_kind="markdown_note",
        processing_status="processed",
        language_code=None,
        parser_name="markdown_line_parser",
        parser_version="markdown_line_parser_v1",
        chunk_count=chunk_count,
        char_count=24,
        frontmatter_json=frontmatter_json or {},
        heading_summary_json=[],
        quality_flags_json=[],
        imported_at=now,
        updated_at=now,
    )
