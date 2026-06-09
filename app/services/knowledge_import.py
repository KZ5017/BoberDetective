from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path, PurePath
import shutil
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.knowledge import KnowledgeDocumentModel
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.markdown_parser import CHUNKING_STRATEGY, PARSER_NAME, PARSER_VERSION, MarkdownChunk, parse_markdown_bytes
from app.services.storage import StoragePathError, StoragePaths
from app.services.text_store import sha256_file, sha256_text
from app.services.users import get_or_create_dev_user


class KnowledgeImportError(ValueError):
    pass


class DuplicateKnowledgeDocumentError(KnowledgeImportError):
    pass


class KnowledgeDocumentNotFoundError(KnowledgeImportError):
    pass


class UnsupportedKnowledgeDocumentTypeError(KnowledgeImportError):
    pass


class KnowledgeUploadTooLargeError(KnowledgeImportError):
    pass


class KnowledgeMarkdownParseError(KnowledgeImportError):
    pass


class KnowledgeLifecycleError(KnowledgeImportError):
    pass


@dataclass(frozen=True)
class KnowledgeStoredChunk:
    chunk_id: str
    chunk_index: int
    heading_path: str
    heading_level: int | None
    char_start: int
    char_end: int
    text: str
    contains_code_block: bool
    code_languages: list[str]
    wikilinks: list[str]
    tags: list[str]
    frontmatter_tags: list[str]
    quality_flags: list[str]

    @classmethod
    def from_markdown_chunk(cls, chunk: MarkdownChunk) -> "KnowledgeStoredChunk":
        return cls(
            chunk_id=str(uuid4()),
            chunk_index=chunk.chunk_index,
            heading_path=chunk.heading_path,
            heading_level=chunk.heading_level,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            text=chunk.text,
            contains_code_block=chunk.contains_code_block,
            code_languages=chunk.code_languages,
            wikilinks=chunk.wikilinks,
            tags=chunk.tags,
            frontmatter_tags=chunk.frontmatter_tags,
            quality_flags=chunk.quality_flags,
        )

    def to_json_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "heading_path": self.heading_path,
            "heading_level": self.heading_level,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "text": self.text,
            "text_hash": sha256_text(self.text),
            "text_char_count": len(self.text),
            "contains_code_block": self.contains_code_block,
            "code_languages": self.code_languages,
            "wikilinks": self.wikilinks,
            "tags": self.tags,
            "frontmatter_tags": self.frontmatter_tags,
            "quality_flags": self.quality_flags,
        }

    @classmethod
    def from_json_dict(cls, data: dict) -> "KnowledgeStoredChunk":
        return cls(
            chunk_id=str(data["chunk_id"]),
            chunk_index=int(data["chunk_index"]),
            heading_path=str(data.get("heading_path") or ""),
            heading_level=data.get("heading_level") if data.get("heading_level") is None else int(data["heading_level"]),
            char_start=int(data["char_start"]),
            char_end=int(data["char_end"]),
            text=str(data["text"]),
            contains_code_block=bool(data.get("contains_code_block")),
            code_languages=[str(item) for item in data.get("code_languages", [])],
            wikilinks=[str(item) for item in data.get("wikilinks", [])],
            tags=[str(item) for item in data.get("tags", [])],
            frontmatter_tags=[str(item) for item in data.get("frontmatter_tags", [])],
            quality_flags=[str(item) for item in data.get("quality_flags", [])],
        )


def list_knowledge_documents(db: Session) -> list[KnowledgeDocumentModel]:
    return list(
        db.execute(
            select(KnowledgeDocumentModel).order_by(
                KnowledgeDocumentModel.imported_at.desc(),
                KnowledgeDocumentModel.original_filename.asc(),
            )
        ).scalars()
    )


def get_knowledge_document(db: Session, knowledge_document_id: UUID) -> KnowledgeDocumentModel:
    document = db.get(KnowledgeDocumentModel, knowledge_document_id)
    if document is None:
        raise KnowledgeDocumentNotFoundError("Knowledge document not found")
    return document


def archive_knowledge_document(db: Session, knowledge_document_id: UUID) -> KnowledgeDocumentModel:
    document = get_knowledge_document(db, knowledge_document_id)
    if document.processing_status == "archived":
        return document
    _delete_knowledge_vector_points(document.id)
    previous_status = document.processing_status
    document.processing_status = "archived"
    document.indexed_chunk_count = 0
    document.indexed_at = None
    document.updated_at = datetime.now(UTC)
    db.add(document)
    _write_knowledge_audit_event(
        db,
        event_type="knowledge_document_archived",
        document=document,
        input_summary={"previous_processing_status": previous_status},
        output_summary={"processing_status": document.processing_status},
    )
    db.commit()
    db.refresh(document)
    return document


def restore_knowledge_document(db: Session, knowledge_document_id: UUID) -> KnowledgeDocumentModel:
    document = get_knowledge_document(db, knowledge_document_id)
    if document.processing_status != "archived":
        return document
    document.processing_status = "processed"
    document.indexed_chunk_count = 0
    document.indexed_at = None
    document.updated_at = datetime.now(UTC)
    db.add(document)
    _write_knowledge_audit_event(
        db,
        event_type="knowledge_document_restored",
        document=document,
        input_summary={"previous_processing_status": "archived"},
        output_summary={"processing_status": document.processing_status, "requires_reindex": True},
    )
    db.commit()
    db.refresh(document)
    return document


def delete_knowledge_document(db: Session, knowledge_document_id: UUID) -> None:
    document = get_knowledge_document(db, knowledge_document_id)
    storage = StoragePaths(get_settings().data_root)
    document_dir = storage.knowledge_document_dir(str(document.id))
    _delete_knowledge_vector_points(document.id)
    _write_knowledge_audit_event(
        db,
        event_type="knowledge_document_deleted",
        document=document,
        input_summary={
            "processing_status": document.processing_status,
            "stored_path": document.stored_path,
            "text_layer_storage_uri": document.text_layer_storage_uri,
            "chunk_manifest_storage_uri": document.chunk_manifest_storage_uri,
            "vector_collection": document.vector_collection,
            "indexed_chunk_count": document.indexed_chunk_count,
        },
        output_summary={"knowledge_document_id": str(document.id), "data_root_directory_removed": True},
    )
    db.delete(document)
    _remove_knowledge_document_dir(document_dir, storage.data_root)
    db.commit()


async def import_knowledge_document(
    db: Session,
    upload: UploadFile,
    *,
    relative_path: str | None = None,
) -> KnowledgeDocumentModel:
    _ensure_markdown_upload(upload.filename)
    safe_relative_path = _normalize_relative_path(relative_path)
    settings = get_settings()
    content = await _read_limited_upload(upload, settings.max_upload_bytes)
    sha256_hash = hashlib.sha256(content).hexdigest()

    duplicate = db.execute(
        select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.sha256_hash == sha256_hash)
    ).scalar_one_or_none()
    if duplicate is not None:
        raise DuplicateKnowledgeDocumentError("Knowledge document with this content hash already exists")

    parsed = parse_markdown_bytes(content)
    if parsed.has_fatal_error:
        raise KnowledgeMarkdownParseError(f"Markdown parsing failed: {', '.join(parsed.quality_flags)}")

    user = get_or_create_dev_user(db)
    storage = StoragePaths(settings.data_root)
    document_id = uuid4()
    original_dir = storage.knowledge_document_originals_dir(str(document_id))
    derived_dir = storage.knowledge_document_derived_dir(str(document_id))
    original_path = original_dir / "original.md"
    text_layer_path = derived_dir / "text_layer.json"
    chunks_path = derived_dir / "chunks.jsonl"

    _write_immutable_file(original_path, content)
    text_layer_hash = _write_json(text_layer_path, _text_layer_payload(parsed))
    stored_chunks = [KnowledgeStoredChunk.from_markdown_chunk(chunk) for chunk in parsed.chunks]
    chunk_manifest_hash = _write_chunks_jsonl(chunks_path, stored_chunks)

    document = KnowledgeDocumentModel(
        id=document_id,
        original_filename=Path(upload.filename or "document.md").name,
        relative_path=safe_relative_path,
        stored_path=str(original_path),
        mime_type=upload.content_type or "text/markdown",
        file_extension=".md",
        file_size_bytes=len(content),
        sha256_hash=sha256_hash,
        document_kind="markdown_note",
        processing_status="processed",
        language_code=None,
        parser_name=PARSER_NAME,
        parser_version=PARSER_VERSION,
        text_layer_storage_uri=text_layer_path.relative_to(storage.data_root).as_posix(),
        text_layer_manifest_hash=text_layer_hash,
        chunk_manifest_storage_uri=chunks_path.relative_to(storage.data_root).as_posix(),
        chunk_manifest_hash=chunk_manifest_hash,
        chunk_count=len(stored_chunks),
        char_count=len(parsed.text),
        frontmatter_json=parsed.frontmatter,
        heading_summary_json=parsed.headings,
        quality_flags_json=parsed.quality_flags,
        imported_by_user_id=user.id,
        imported_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(document)

    event = AuditEvent(
        event_type="knowledge_document_imported",
        success=True,
        user_id=str(user.id),
        related_object_type="knowledge_document",
        related_object_id=str(document.id),
        input_summary={
            "filename": document.original_filename,
            "relative_path": document.relative_path,
            "file_size_bytes": document.file_size_bytes,
            "sha256_hash": document.sha256_hash,
            "chunking_strategy": CHUNKING_STRATEGY,
        },
        output_summary={
            "knowledge_document_id": str(document.id),
            "chunk_count": document.chunk_count,
            "char_count": document.char_count,
            "quality_flags": document.quality_flags_json,
        },
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(storage).write_global(event)
    db.commit()
    db.refresh(document)
    return document


def read_knowledge_chunks(document: KnowledgeDocumentModel) -> list[KnowledgeStoredChunk]:
    if not document.chunk_manifest_storage_uri:
        return []
    data_root = StoragePaths(get_settings().data_root).data_root
    path = (data_root / document.chunk_manifest_storage_uri).resolve()
    if not _is_relative_to(path, data_root) or not path.exists():
        return []
    rows: list[KnowledgeStoredChunk] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(KnowledgeStoredChunk.from_json_dict(json.loads(stripped)))
    return rows


def _delete_knowledge_vector_points(knowledge_document_id: UUID) -> None:
    from app.services.knowledge_indexing import QdrantKnowledgeIndex

    QdrantKnowledgeIndex().delete_document_points(knowledge_document_id)


def _write_knowledge_audit_event(
    db: Session,
    *,
    event_type: str,
    document: KnowledgeDocumentModel,
    input_summary: dict,
    output_summary: dict,
) -> None:
    storage = StoragePaths(get_settings().data_root)
    user = get_or_create_dev_user(db)
    event = AuditEvent(
        event_type=event_type,
        success=True,
        user_id=str(user.id),
        related_object_type="knowledge_document",
        related_object_id=str(document.id),
        input_summary={
            "filename": document.original_filename,
            "relative_path": document.relative_path,
            "sha256_hash": document.sha256_hash,
            **input_summary,
        },
        output_summary=output_summary,
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(storage).write_global(event)


def _remove_knowledge_document_dir(document_dir: Path, data_root: Path) -> None:
    resolved_dir = document_dir.resolve()
    if not _is_relative_to(resolved_dir, data_root):
        raise KnowledgeLifecycleError("Knowledge document path escapes configured data root")
    if resolved_dir.exists():
        shutil.rmtree(resolved_dir)


def _ensure_markdown_upload(filename: str | None) -> None:
    if not filename or Path(filename).suffix.casefold() != ".md":
        raise UnsupportedKnowledgeDocumentTypeError("Only .md Markdown files can be imported into the knowledge base")


def _normalize_relative_path(relative_path: str | None) -> str | None:
    if relative_path is None or relative_path.strip() == "":
        return None
    normalized = relative_path.strip().replace("\\", "/")
    pure = PurePath(normalized)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise KnowledgeImportError("Unsafe relative_path")
    return pure.as_posix()


async def _read_limited_upload(upload: UploadFile, max_upload_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total_size = 0
    while chunk := await upload.read(1024 * 1024):
        total_size += len(chunk)
        if total_size > max_upload_bytes:
            raise KnowledgeUploadTooLargeError(f"Upload exceeds configured size limit ({_format_size_limit(max_upload_bytes)})")
        chunks.append(chunk)
    if total_size == 0:
        raise UnsupportedKnowledgeDocumentTypeError("Empty files are not importable")
    return b"".join(chunks)


def _format_size_limit(byte_count: int) -> str:
    if byte_count < 1024 * 1024:
        return f"{byte_count} B"
    return f"{byte_count / (1024 * 1024):.1f}".rstrip("0").rstrip(".") + " MiB"


def _write_immutable_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(content)


def _text_layer_payload(parsed) -> dict:
    return {
        "parser_name": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "chunking_strategy": CHUNKING_STRATEGY,
        "text": parsed.text,
        "text_hash": sha256_text(parsed.text),
        "text_char_count": len(parsed.text),
        "frontmatter": parsed.frontmatter,
        "frontmatter_raw": parsed.frontmatter_raw,
        "headings": parsed.headings,
        "quality_flags": parsed.quality_flags,
    }


def _write_json(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    return sha256_file(path)


def _write_chunks_jsonl(path: Path, chunks: list[KnowledgeStoredChunk]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk.to_json_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
    return sha256_file(path)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
