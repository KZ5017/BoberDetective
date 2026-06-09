import asyncio
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import UploadFile

from app.models.knowledge import KnowledgeDocumentModel
from app.models.user import UserModel
from app.services.knowledge_import import import_knowledge_document, read_knowledge_chunks


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

    document = asyncio.run(import_knowledge_document(db, upload, relative_path="notes/note.md"))

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


class _FakeDb:
    def __init__(self) -> None:
        self.added = []

    def execute(self, statement):
        del statement
        return _FakeResult()

    def add(self, item) -> None:
        if isinstance(item, UserModel) and item.id is None:
            item.id = uuid4()
        self.added.append(item)

    def flush(self) -> None:
        pass

    def commit(self) -> None:
        pass

    def refresh(self, item) -> None:
        if isinstance(item, KnowledgeDocumentModel):
            self.document = item


class _FakeResult:
    def scalar_one_or_none(self):
        return None
