import asyncio
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import UploadFile

from app.models.knowledge import KnowledgeDocumentModel
from app.models.user import UserModel
from app.services.knowledge_import import (
    KnowledgeImportConflictError,
    archive_knowledge_document,
    delete_knowledge_document,
    import_knowledge_document,
    import_knowledge_document_batch,
    preview_knowledge_document_batch,
    read_knowledge_chunks,
    restore_knowledge_document,
)


def test_import_knowledge_document_writes_original_and_chunk_manifest(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    db = _FakeDb()
    upload = UploadFile(
        filename="note.md",
        file=BytesIO(
            b"""---
tags:
  - linux
---
# Linux
## SUID

Hasznald az `id` parancsot.
"""
        ),
    )

    result = asyncio.run(import_knowledge_document(db, upload, relative_path="notes"))
    document = result.document

    assert result.action == "imported"
    assert document in db.added
    assert document.processing_status == "processed"
    assert document.relative_path == "notes/note.md"
    assert document.chunk_count == 1
    assert document.frontmatter_json == {"tags": ["linux"]}
    assert Path(document.stored_path).exists()
    assert document.stored_path.endswith("/originals/original.md")
    assert (tmp_path / document.text_layer_storage_uri).exists()
    assert (tmp_path / document.chunk_manifest_storage_uri).exists()

    chunks = read_knowledge_chunks(document)
    assert len(chunks) == 1
    assert chunks[0].heading_path == "Linux > SUID"
    assert chunks[0].frontmatter_tags == ["linux"]


def test_import_knowledge_document_uses_filename_when_relative_directory_is_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    db = _FakeDb()
    upload = UploadFile(filename="note.md", file=BytesIO(b"# Note\n\nMeaningful Markdown body.\n"))

    result = asyncio.run(import_knowledge_document(db, upload, relative_path=""))

    assert result.document.relative_path == "note.md"


def test_import_knowledge_document_rejects_unsafe_relative_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    db = _FakeDb()
    upload = UploadFile(filename="note.md", file=BytesIO(b"# Note\n"))

    try:
        asyncio.run(import_knowledge_document(db, upload, relative_path="../notes"))
    except Exception as exc:
        assert "Unsafe relative directory" in str(exc)
    else:
        raise AssertionError("Expected unsafe relative directory rejection")


def test_preview_knowledge_document_batch_counts_ready_items_without_returning_them(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    db = _FakeDb()
    uploads = [
        UploadFile(filename="first.md", file=BytesIO(b"# First\n\nMeaningful first body.\n")),
        UploadFile(filename="second.md", file=BytesIO(b"# Second\n\nMeaningful second body.\n")),
    ]

    result = asyncio.run(
        preview_knowledge_document_batch(
            db,
            uploads,
            relative_paths=["notes/linux", "notes/web"],
            client_file_ids=["a", "b"],
        )
    )

    assert result.summary.total == 2
    assert result.summary.ready == 2
    assert result.items == []
    assert db.added == []
    assert db.commits == 0


def test_preview_knowledge_document_batch_reports_same_hash(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    existing = _knowledge_document(tmp_path)
    monkeypatch.setattr("app.services.knowledge_import._find_knowledge_document_by_hash", lambda db, sha256_hash: existing)
    db = _FakeDb(document=existing)
    upload = UploadFile(filename="copy.md", file=BytesIO(b"# Copy\n\nMeaningful copied body.\n"))

    result = asyncio.run(preview_knowledge_document_batch(db, [upload], relative_paths=["notes/linux"], client_file_ids=["copy"]))

    assert result.summary.same_hash == 1
    assert result.items[0].status == "same_hash"
    assert result.items[0].conflict_type == "same_hash"
    assert result.items[0].existing_document_id == existing.id


def test_preview_knowledge_document_batch_reports_same_relative_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    existing = _knowledge_document(tmp_path)
    monkeypatch.setattr("app.services.knowledge_import._find_knowledge_document_by_hash", lambda db, sha256_hash: None)
    monkeypatch.setattr("app.services.knowledge_import._find_knowledge_document_by_relative_path", lambda db, relative_path: existing)
    db = _FakeDb(document=existing)
    upload = UploadFile(filename="note.md", file=BytesIO(b"# Updated\n\nMeaningful updated body.\n"))

    result = asyncio.run(preview_knowledge_document_batch(db, [upload], relative_paths=["notes/linux"]))

    assert result.summary.same_relative_path == 1
    assert result.items[0].status == "same_relative_path"
    assert result.items[0].resolved_relative_path == "notes/linux/note.md"
    assert result.items[0].existing_relative_path == "notes/note.md"


def test_preview_knowledge_document_batch_reports_invalid_extension(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    db = _FakeDb()
    upload = UploadFile(filename="note.txt", file=BytesIO(b"hello"))

    result = asyncio.run(preview_knowledge_document_batch(db, [upload]))

    assert result.summary.invalid == 1
    assert result.items[0].status == "invalid"
    assert result.items[0].conflict_type == "unsupported_file_type"


def test_preview_knowledge_document_batch_requires_relative_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    db = _FakeDb()
    upload = UploadFile(filename="note.md", file=BytesIO(b"# Note\n\nMeaningful body.\n"))

    result = asyncio.run(preview_knowledge_document_batch(db, [upload], relative_paths=[""]))

    assert result.summary.invalid == 1
    assert result.items[0].status == "invalid"
    assert result.items[0].conflict_type == "unsafe_relative_path"
    assert "Relative directory is required" in str(result.items[0].error)


def test_preview_knowledge_document_batch_rejects_single_segment_relative_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    db = _FakeDb()
    upload = UploadFile(filename="note.md", file=BytesIO(b"# Note\n\nMeaningful body.\n"))

    result = asyncio.run(preview_knowledge_document_batch(db, [upload], relative_paths=["boberkurwa"]))

    assert result.summary.invalid == 1
    assert result.items[0].status == "invalid"
    assert result.items[0].conflict_type == "unsafe_relative_path"
    assert "at least two path segments" in str(result.items[0].error)


def test_preview_knowledge_document_batch_reports_unsafe_relative_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    db = _FakeDb()
    upload = UploadFile(filename="note.md", file=BytesIO(b"# Note\n\nMeaningful body.\n"))

    result = asyncio.run(preview_knowledge_document_batch(db, [upload], relative_paths=["../notes"]))

    assert result.summary.invalid == 1
    assert result.items[0].status == "invalid"
    assert result.items[0].conflict_type == "unsafe_relative_path"


def test_import_knowledge_document_batch_imports_ready_and_skips_marked_items(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    db = _FakeDb()
    uploads = [
        UploadFile(filename="first.md", file=BytesIO(b"# First\n\nMeaningful first body.\n")),
        UploadFile(filename="second.md", file=BytesIO(b"# Second\n\nMeaningful second body.\n")),
    ]

    result = asyncio.run(
        import_knowledge_document_batch(
            db,
            uploads,
            relative_paths=["notes/linux", "notes/linux"],
            client_file_ids=["first", "second"],
            decisions=["import", "skip"],
        )
    )

    assert result.summary.total == 2
    assert result.summary.imported == 1
    assert result.summary.skipped == 1
    assert result.summary.failed == 0
    assert len(result.items) == 1
    assert result.items[0].action == "skipped"
    assert len([item for item in db.added if isinstance(item, KnowledgeDocumentModel)]) == 1


def test_import_knowledge_document_batch_replaces_same_relative_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    old = _knowledge_document(tmp_path, processing_status="indexed", indexed_chunk_count=2)
    old_dir = tmp_path / "knowledge" / "documents" / str(old.id)
    (old_dir / "originals").mkdir(parents=True)
    (old_dir / "originals" / "original.md").write_text("# Old\n", encoding="utf-8")
    monkeypatch.setattr("app.services.knowledge_import._find_knowledge_document_by_hash", lambda db, sha256_hash: None)
    monkeypatch.setattr("app.services.knowledge_import._find_knowledge_document_by_relative_path", lambda db, relative_path: old)
    deleted_vector_ids = []
    monkeypatch.setattr("app.services.knowledge_import._delete_knowledge_vector_points", lambda document_id: deleted_vector_ids.append(document_id))
    db = _FakeDb(document=old)
    upload = UploadFile(filename="note.md", file=BytesIO(b"# New\n\nMeaningful replacement body.\n"))

    result = asyncio.run(
        import_knowledge_document_batch(
            db,
            [upload],
            relative_paths=["notes/linux"],
            client_file_ids=["note"],
            decisions=["replace"],
        )
    )

    assert result.summary.replaced == 1
    assert result.items[0].action == "replaced"
    assert result.items[0].replaced_document_id == old.id
    assert deleted_vector_ids == [old.id]
    assert not old_dir.exists()


def test_import_knowledge_document_batch_fails_invalid_file_without_mutating(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    db = _FakeDb()
    upload = UploadFile(filename="note.txt", file=BytesIO(b"hello"))

    result = asyncio.run(import_knowledge_document_batch(db, [upload], decisions=["import"]))

    assert result.summary.failed == 1
    assert result.items[0].action == "failed"
    assert result.items[0].conflict_type == "unsupported_file_type"
    assert db.added == []
    assert db.commits == 0


def test_import_knowledge_document_batch_fails_import_decision_on_same_hash(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    existing = _knowledge_document(tmp_path)
    monkeypatch.setattr("app.services.knowledge_import._find_knowledge_document_by_hash", lambda db, sha256_hash: existing)
    db = _FakeDb(document=existing)
    upload = UploadFile(filename="copy.md", file=BytesIO(b"# Copy\n\nMeaningful body.\n"))

    result = asyncio.run(import_knowledge_document_batch(db, [upload], relative_paths=["notes/linux"], decisions=["import"]))

    assert result.summary.failed == 1
    assert result.items[0].action == "failed"
    assert result.items[0].conflict_type == "same_hash"
    assert result.items[0].existing_document_id == existing.id
    assert db.commits == 0


def test_import_knowledge_document_same_hash_skip_returns_existing_without_mutation(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    existing = _knowledge_document(tmp_path, processing_status="indexed", indexed_chunk_count=2)
    monkeypatch.setattr("app.services.knowledge_import._find_knowledge_document_by_hash", lambda db, sha256_hash: existing)
    db = _FakeDb(document=existing)
    upload = UploadFile(filename="note.md", file=BytesIO(b"# Same\n"))

    result = asyncio.run(import_knowledge_document(db, upload, relative_path="other", conflict_strategy="skip"))

    assert result.action == "skipped"
    assert result.document == existing
    assert result.conflict_type == "same_hash"
    assert result.existing_document_id == existing.id
    assert db.commits == 0
    assert db.deleted == []


def test_import_knowledge_document_same_hash_fail_raises_conflict(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    existing = _knowledge_document(tmp_path, processing_status="indexed", indexed_chunk_count=2)
    monkeypatch.setattr("app.services.knowledge_import._find_knowledge_document_by_hash", lambda db, sha256_hash: existing)
    db = _FakeDb(document=existing)
    upload = UploadFile(filename="note.md", file=BytesIO(b"# Same\n"))

    try:
        asyncio.run(import_knowledge_document(db, upload, relative_path="other", conflict_strategy="fail"))
    except KnowledgeImportConflictError as exc:
        assert exc.conflict_type == "same_hash"
        assert exc.existing_document == existing
    else:
        raise AssertionError("Expected KnowledgeImportConflictError")

    assert db.commits == 0
    assert db.deleted == []


def test_import_knowledge_document_replace_relative_path_imports_new_then_deletes_old(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    old = _knowledge_document(tmp_path, processing_status="indexed", indexed_chunk_count=2)
    old_dir = tmp_path / "knowledge" / "documents" / str(old.id)
    (old_dir / "originals").mkdir(parents=True)
    (old_dir / "originals" / "original.md").write_text("# Old\n", encoding="utf-8")
    monkeypatch.setattr("app.services.knowledge_import._find_knowledge_document_by_hash", lambda db, sha256_hash: None)
    captured_relative_paths = []
    monkeypatch.setattr(
        "app.services.knowledge_import._find_knowledge_document_by_relative_path",
        lambda db, relative_path: captured_relative_paths.append(relative_path) or old,
    )
    deleted_vector_ids = []
    monkeypatch.setattr("app.services.knowledge_import._delete_knowledge_vector_points", lambda document_id: deleted_vector_ids.append(document_id))
    db = _FakeDb(document=old)
    upload = UploadFile(filename="note.md", file=BytesIO(b"# New\n\nUpdated text.\n"))

    result = asyncio.run(import_knowledge_document(db, upload, relative_path="notes", conflict_strategy="replace"))

    assert result.action == "replaced"
    assert result.replaced_document_id == old.id
    assert result.document.id != old.id
    assert result.document.relative_path == "notes/note.md"
    assert captured_relative_paths == ["notes/note.md"]
    assert db.deleted == [old]
    assert deleted_vector_ids == [old.id]
    assert not old_dir.exists()


def test_archive_and_restore_knowledge_document_marks_reindex_required(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    deleted_vector_ids = []
    monkeypatch.setattr("app.services.knowledge_import._delete_knowledge_vector_points", lambda document_id: deleted_vector_ids.append(document_id))
    document = _knowledge_document(tmp_path, processing_status="indexed", indexed_chunk_count=2)
    db = _FakeDb(document=document)

    archived = archive_knowledge_document(db, document.id)

    assert archived.processing_status == "archived"
    assert archived.indexed_chunk_count == 0
    assert archived.indexed_at is None
    assert deleted_vector_ids == [document.id]
    assert db.commits == 1

    restored = restore_knowledge_document(db, document.id)

    assert restored.processing_status == "processed"
    assert restored.indexed_chunk_count == 0
    assert db.commits == 2


def test_delete_knowledge_document_removes_record_and_data_root_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.knowledge_import.get_settings",
        lambda: SimpleNamespace(data_root=tmp_path, max_upload_bytes=1024 * 1024),
    )
    deleted_vector_ids = []
    monkeypatch.setattr("app.services.knowledge_import._delete_knowledge_vector_points", lambda document_id: deleted_vector_ids.append(document_id))
    document = _knowledge_document(tmp_path, processing_status="indexed", indexed_chunk_count=2)
    document_dir = tmp_path / "knowledge" / "documents" / str(document.id)
    (document_dir / "originals").mkdir(parents=True)
    (document_dir / "originals" / "original.md").write_text("# Note\n", encoding="utf-8")
    db = _FakeDb(document=document)

    delete_knowledge_document(db, document.id)

    assert deleted_vector_ids == [document.id]
    assert db.deleted == [document]
    assert db.commits == 1
    assert not document_dir.exists()


class _FakeDb:
    def __init__(self, document=None) -> None:
        self.added = []
        self.document = document
        self.documents = {}
        if document is not None:
            self.documents[document.id] = document
        self.deleted = []
        self.commits = 0

    def execute(self, statement):
        del statement
        return _FakeResult()

    def get(self, model, item_id):
        del model
        return self.documents.get(item_id)

    def add(self, item) -> None:
        if isinstance(item, UserModel) and item.id is None:
            item.id = uuid4()
        if isinstance(item, KnowledgeDocumentModel):
            self.documents[item.id] = item
        self.added.append(item)

    def delete(self, item) -> None:
        self.deleted.append(item)
        self.documents.pop(item.id, None)

    def flush(self) -> None:
        pass

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, item) -> None:
        if isinstance(item, KnowledgeDocumentModel):
            self.document = item
            self.documents[item.id] = item


class _FakeResult:
    def scalar_one_or_none(self):
        return None


def _knowledge_document(tmp_path, *, processing_status: str = "processed", indexed_chunk_count: int = 0) -> KnowledgeDocumentModel:
    document_id = uuid4()
    return KnowledgeDocumentModel(
        id=document_id,
        original_filename="note.md",
        relative_path="notes/note.md",
        stored_path=str(tmp_path / "knowledge" / "documents" / str(document_id) / "originals" / "original.md"),
        mime_type="text/markdown",
        file_extension=".md",
        file_size_bytes=8,
        sha256_hash="b" * 64,
        document_kind="markdown_note",
        processing_status=processing_status,
        text_layer_storage_uri=f"knowledge/documents/{document_id}/derived/text_layer.json",
        text_layer_manifest_hash="c" * 64,
        chunk_manifest_storage_uri=f"knowledge/documents/{document_id}/derived/chunks.jsonl",
        chunk_manifest_hash="d" * 64,
        chunk_count=2,
        char_count=8,
        indexed_chunk_count=indexed_chunk_count,
        frontmatter_json={},
        heading_summary_json=[],
        quality_flags_json=[],
    )
