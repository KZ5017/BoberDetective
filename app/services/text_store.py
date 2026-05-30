import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import DocumentChunkManifestModel, DocumentChunkModel, DocumentPageModel, DocumentTextLayerModel
from app.services.storage import StoragePaths


class TextStoreError(ValueError):
    pass


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class StoredPageText:
    page_id: str
    page_number: int
    text: str
    text_hash: str | None = None
    text_char_count: int | None = None
    ocr_confidence: float | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "page_id": self.page_id,
            "page_number": self.page_number,
            "text": self.text,
            "text_hash": self.text_hash or sha256_text(self.text),
            "text_char_count": self.text_char_count if self.text_char_count is not None else len(self.text),
            "ocr_confidence": self.ocr_confidence,
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> "StoredPageText":
        return cls(
            page_id=_required_str(data, "page_id"),
            page_number=_required_int(data, "page_number"),
            text=_required_str(data, "text"),
            text_hash=_required_str(data, "text_hash"),
            text_char_count=_required_int(data, "text_char_count"),
            ocr_confidence=_optional_float(data, "ocr_confidence"),
        )


@dataclass(frozen=True)
class StoredChunkText:
    chunk_id: str
    chunk_index: int
    page_start: int
    page_end: int
    text: str
    char_start: int | None = None
    char_end: int | None = None
    text_hash: str | None = None
    text_char_count: int | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "text": self.text,
            "text_hash": self.text_hash or sha256_text(self.text),
            "text_char_count": self.text_char_count if self.text_char_count is not None else len(self.text),
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> "StoredChunkText":
        return cls(
            chunk_id=_required_str(data, "chunk_id"),
            chunk_index=_required_int(data, "chunk_index"),
            page_start=_required_int(data, "page_start"),
            page_end=_required_int(data, "page_end"),
            char_start=_optional_int(data, "char_start"),
            char_end=_optional_int(data, "char_end"),
            text=_required_str(data, "text"),
            text_hash=_required_str(data, "text_hash"),
            text_char_count=_required_int(data, "text_char_count"),
        )


@dataclass(frozen=True)
class JsonlWriteResult:
    path: Path
    manifest_hash: str
    record_count: int


def write_pages_jsonl(path: Path, pages: Iterable[StoredPageText]) -> JsonlWriteResult:
    return _write_jsonl(path, (page.to_json_dict() for page in pages))


def read_pages_jsonl(path: Path) -> list[StoredPageText]:
    return [StoredPageText.from_json_dict(item) for item in _read_jsonl(path)]


def write_chunks_jsonl(path: Path, chunks: Iterable[StoredChunkText]) -> JsonlWriteResult:
    return _write_jsonl(path, (chunk.to_json_dict() for chunk in chunks))


def read_chunks_jsonl(path: Path) -> list[StoredChunkText]:
    return [StoredChunkText.from_json_dict(item) for item in _read_jsonl(path)]


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> JsonlWriteResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    record_count = 0
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            file.write("\n")
            record_count += 1
    return JsonlWriteResult(path=path, manifest_hash=sha256_file(path), record_count=record_count)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    row = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise TextStoreError(f"Invalid JSONL record at line {line_number}") from exc
                if not isinstance(row, dict):
                    raise TextStoreError(f"JSONL record at line {line_number} must be an object")
                rows.append(row)
    except OSError as exc:
        raise TextStoreError(f"Cannot read text-store JSONL file: {path}") from exc
    return rows


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise TextStoreError(f"Missing or invalid text-store string field: {key}")
    return value


def _required_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise TextStoreError(f"Missing or invalid text-store integer field: {key}")
    return value


def _optional_int(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise TextStoreError(f"Invalid text-store integer field: {key}")
    return value


def _optional_float(data: dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, int | float):
        raise TextStoreError(f"Invalid text-store numeric field: {key}")
    return float(value)


class SourceTextResolver:
    """Compatibility source-text access point for paths without a DB session.

    Active runtime code should prefer read_page_text_from_store/read_chunk_text_from_store.
    These fallbacks intentionally do not read PostgreSQL text columns. A private
    transient attribute is accepted for unit-test and in-memory helper objects.
    """

    def read_page_text(self, page: DocumentPageModel) -> str:
        return str(getattr(page, "_text_store_text", ""))

    def read_chunk_text(self, chunk: DocumentChunkModel) -> str:
        return str(getattr(chunk, "_text_store_text", ""))


_DEFAULT_SOURCE_TEXT_RESOLVER = SourceTextResolver()


def get_source_text_resolver() -> SourceTextResolver:
    return _DEFAULT_SOURCE_TEXT_RESOLVER


def read_page_text(page: DocumentPageModel) -> str:
    return get_source_text_resolver().read_page_text(page)


def read_chunk_text(chunk: DocumentChunkModel) -> str:
    return get_source_text_resolver().read_chunk_text(chunk)


def read_page_text_from_store(db: Session, page: DocumentPageModel) -> str:
    text_layer = _current_text_layer(db, page.case_id, page.document_id)
    if text_layer is None:
        return read_page_text(page)
    try:
        pages = read_pages_jsonl(_storage_uri_path(text_layer.storage_uri))
    except TextStoreError:
        return read_page_text(page)
    for stored_page in pages:
        if stored_page.page_id == str(page.id):
            return stored_page.text
    return read_page_text(page)


def read_chunk_text_from_store(db: Session, chunk: DocumentChunkModel) -> str:
    chunk_manifest = _current_chunk_manifest(db, chunk.case_id, chunk.document_id)
    if chunk_manifest is None:
        return read_chunk_text(chunk)
    try:
        chunks = read_chunks_jsonl(_storage_uri_path(chunk_manifest.storage_uri))
    except TextStoreError:
        return read_chunk_text(chunk)
    for stored_chunk in chunks:
        if stored_chunk.chunk_id == str(chunk.id):
            return stored_chunk.text
    return read_chunk_text(chunk)


def _current_text_layer(db: Session, case_id: Any, document_id: Any) -> DocumentTextLayerModel | None:
    try:
        return db.execute(
            select(DocumentTextLayerModel)
            .where(
                DocumentTextLayerModel.case_id == case_id,
                DocumentTextLayerModel.document_id == document_id,
                DocumentTextLayerModel.is_current.is_(True),
            )
            .order_by(DocumentTextLayerModel.created_at.desc())
        ).scalars().first()
    except AttributeError:
        return None


def _current_chunk_manifest(db: Session, case_id: Any, document_id: Any) -> DocumentChunkManifestModel | None:
    try:
        return db.execute(
            select(DocumentChunkManifestModel)
            .where(
                DocumentChunkManifestModel.case_id == case_id,
                DocumentChunkManifestModel.document_id == document_id,
                DocumentChunkManifestModel.is_current.is_(True),
            )
            .order_by(DocumentChunkManifestModel.created_at.desc())
        ).scalars().first()
    except AttributeError:
        return None


def _storage_uri_path(storage_uri: str) -> Path:
    storage = StoragePaths(get_settings().data_root)
    path = storage.data_root.joinpath(storage_uri).resolve()
    if not StoragePaths._is_relative_to(path, storage.data_root):
        raise TextStoreError("Text-store path escapes configured data root")
    return path
