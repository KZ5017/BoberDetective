from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
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


def test_post_knowledge_document_batch_preview_maps_response(monkeypatch) -> None:
    existing_id = uuid4()

    async def fake_preview(db, files, *, relative_paths=None, client_file_ids=None):
        assert [file.filename for file in files] == ["one.md", "two.md"]
        assert relative_paths == ["notes/a", "notes/b"]
        assert client_file_ids == ["file_a", "file_b"]
        return SimpleNamespace(
            items=[
                SimpleNamespace(
                    client_file_id="file_a",
                    original_filename="one.md",
                    relative_directory="notes/a",
                    resolved_relative_path="notes/a/one.md",
                    sha256_hash="a" * 64,
                    status="ready",
                    conflict_type=None,
                    existing_document_id=None,
                    existing_original_filename=None,
                    existing_relative_path=None,
                    error=None,
                ),
                SimpleNamespace(
                    client_file_id="file_b",
                    original_filename="two.md",
                    relative_directory="notes/b",
                    resolved_relative_path="notes/b/two.md",
                    sha256_hash="b" * 64,
                    status="same_hash",
                    conflict_type="same_hash",
                    existing_document_id=existing_id,
                    existing_original_filename="two.md",
                    existing_relative_path="old/two.md",
                    error=None,
                ),
            ],
            summary=SimpleNamespace(total=2, ready=1, same_hash=1, same_relative_path=0, invalid=0),
        )

    monkeypatch.setattr("app.api.v1.knowledge.preview_knowledge_document_batch", fake_preview)

    response = TestClient(create_app()).post(
        "/api/v1/knowledge/documents/batch/preview",
        files=[
            ("relative_paths", (None, "notes/a")),
            ("relative_paths", (None, "notes/b")),
            ("client_file_ids", (None, "file_a")),
            ("client_file_ids", (None, "file_b")),
            ("files", ("one.md", b"# One\n\nBody", "text/markdown")),
            ("files", ("two.md", b"# Two\n\nBody", "text/markdown")),
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == {"total": 2, "ready": 1, "same_hash": 1, "same_relative_path": 0, "invalid": 0}
    assert body["items"][0]["resolved_relative_path"] == "notes/a/one.md"
    assert body["items"][1]["existing_document_id"] == str(existing_id)


def test_post_knowledge_document_batch_import_maps_response(monkeypatch) -> None:
    async def fake_import(db, files, *, relative_paths=None, client_file_ids=None, decisions=None):
        assert [file.filename for file in files] == ["one.md", "two.md"]
        assert relative_paths == ["notes/a", "notes/b"]
        assert client_file_ids == ["file_a", "file_b"]
        assert decisions == ["import", "skip"]
        return SimpleNamespace(summary=SimpleNamespace(total=2, imported=1, skipped=1, replaced=0, failed=0))

    monkeypatch.setattr("app.api.v1.knowledge.import_knowledge_document_batch", fake_import)

    response = TestClient(create_app()).post(
        "/api/v1/knowledge/documents/batch/import",
        files=[
            ("relative_paths", (None, "notes/a")),
            ("relative_paths", (None, "notes/b")),
            ("client_file_ids", (None, "file_a")),
            ("client_file_ids", (None, "file_b")),
            ("decisions", (None, "import")),
            ("decisions", (None, "skip")),
            ("files", ("one.md", b"# One\n\nBody", "text/markdown")),
            ("files", ("two.md", b"# Two\n\nBody", "text/markdown")),
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == {"total": 2, "imported": 1, "skipped": 1, "replaced": 0, "failed": 0}
    assert "items" not in body


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
