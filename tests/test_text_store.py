from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.document import DocumentChunkManifestModel, DocumentChunkModel, DocumentPageModel, DocumentTextLayerModel
from app.services.text_store import (
    StoredChunkText,
    StoredPageText,
    TextStoreError,
    read_chunks_jsonl,
    read_chunk_text_from_store,
    read_pages_jsonl,
    read_page_text_from_store,
    sha256_file,
    sha256_text,
    write_chunks_jsonl,
    write_pages_jsonl,
)


def test_page_jsonl_roundtrip_includes_hash_and_count(tmp_path: Path) -> None:
    path = tmp_path / "pages.jsonl"
    pages = [
        StoredPageText(page_id="page-1", page_number=1, text="Első oldal."),
        StoredPageText(page_id="page-2", page_number=2, text="Második oldal."),
    ]

    result = write_pages_jsonl(path, pages)

    assert result.record_count == 2
    assert result.manifest_hash == sha256_file(path)
    loaded = read_pages_jsonl(path)
    assert loaded[0].page_id == "page-1"
    assert loaded[0].text == "Első oldal."
    assert loaded[0].text_hash == sha256_text("Első oldal.")
    assert loaded[0].text_char_count == len("Első oldal.")


def test_chunk_jsonl_roundtrip_preserves_offsets(tmp_path: Path) -> None:
    path = tmp_path / "chunks.jsonl"
    chunks = [
        StoredChunkText(
            chunk_id="chunk-1",
            chunk_index=0,
            page_start=1,
            page_end=1,
            char_start=10,
            char_end=42,
            text="Forrásként idézhető rész.",
        )
    ]

    result = write_chunks_jsonl(path, chunks)

    assert result.record_count == 1
    loaded = read_chunks_jsonl(path)
    assert loaded == [
        StoredChunkText(
            chunk_id="chunk-1",
            chunk_index=0,
            page_start=1,
            page_end=1,
            char_start=10,
            char_end=42,
            text="Forrásként idézhető rész.",
            text_hash=sha256_text("Forrásként idézhető rész."),
            text_char_count=len("Forrásként idézhető rész."),
        )
    ]


def test_jsonl_reader_rejects_invalid_record(tmp_path: Path) -> None:
    path = tmp_path / "broken.jsonl"
    path.write_text("[1, 2, 3]\n", encoding="utf-8")

    with pytest.raises(TextStoreError, match="must be an object"):
        read_pages_jsonl(path)


def test_page_text_store_read_prefers_current_manifest(monkeypatch, tmp_path: Path) -> None:
    case_id = uuid4()
    document_id = uuid4()
    page_id = uuid4()
    path = tmp_path / "cases" / str(case_id) / "derived" / str(document_id) / "text_layers" / "layer-1" / "pages.jsonl"
    write_pages_jsonl(path, [StoredPageText(page_id=str(page_id), page_number=1, text="JSONL oldal szoveg.")])
    page = DocumentPageModel(
        id=page_id,
        case_id=case_id,
        document_id=document_id,
        page_number=1,
        text_source="native",
        ocr_used=False,
        version_no=1,
        is_current=True,
        text_char_count=15,
    )
    text_layer = DocumentTextLayerModel(
        id=uuid4(),
        case_id=case_id,
        document_id=document_id,
        source_kind="native_text",
        page_count=1,
        char_count=18,
        storage_uri=path.relative_to(tmp_path).as_posix(),
        manifest_hash="a" * 64,
    )
    monkeypatch.setattr("app.services.text_store.get_settings", lambda: SimpleNamespace(data_root=tmp_path))

    assert read_page_text_from_store(_FakeDb(text_layer), page) == "JSONL oldal szoveg."


def test_chunk_text_store_read_returns_empty_when_manifest_misses_chunk(monkeypatch, tmp_path: Path) -> None:
    case_id = uuid4()
    document_id = uuid4()
    path = tmp_path / "cases" / str(case_id) / "derived" / str(document_id) / "chunk_manifests" / "manifest-1" / "chunks.jsonl"
    write_chunks_jsonl(path, [StoredChunkText(chunk_id=str(uuid4()), chunk_index=0, page_start=1, page_end=1, text="Masik chunk.")])
    chunk = DocumentChunkModel(
        id=uuid4(),
        case_id=case_id,
        document_id=document_id,
        page_start=1,
        page_end=1,
        chunk_index=0,
        chunking_strategy="char_window_v2",
        chunker_version="2",
        version_no=1,
        is_current=True,
    )
    chunk_manifest = DocumentChunkManifestModel(
        id=uuid4(),
        case_id=case_id,
        document_id=document_id,
        text_layer_id=uuid4(),
        chunking_strategy="char_window_v2",
        chunker_version="2",
        chunk_count=1,
        storage_uri=path.relative_to(tmp_path).as_posix(),
        manifest_hash="a" * 64,
    )
    monkeypatch.setattr("app.services.text_store.get_settings", lambda: SimpleNamespace(data_root=tmp_path))

    assert read_chunk_text_from_store(_FakeDb(chunk_manifest), chunk) == ""


class _ScalarResult:
    def __init__(self, value) -> None:
        self.value = value

    def first(self):
        return self.value


class _ExecuteResult:
    def __init__(self, value) -> None:
        self.value = value

    def scalars(self):
        return _ScalarResult(self.value)


class _FakeDb:
    def __init__(self, value) -> None:
        self.value = value

    def execute(self, statement):
        _ = statement
        return _ExecuteResult(self.value)
