from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path, PurePath
import shutil
from typing import Literal
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


KnowledgeImportAction = Literal["imported", "skipped", "replaced"]
KnowledgeImportConflictStrategy = Literal["fail", "skip", "replace"]
KnowledgeBatchPreviewStatus = Literal["ready", "same_hash", "same_relative_path", "invalid"]
KnowledgeBatchImportAction = Literal["imported", "skipped", "replaced", "failed"]


class KnowledgeImportConflictError(KnowledgeImportError):
    def __init__(
        self,
        message: str,
        *,
        conflict_type: str,
        existing_document: KnowledgeDocumentModel,
    ) -> None:
        super().__init__(message)
        self.conflict_type = conflict_type
        self.existing_document = existing_document


@dataclass(frozen=True)
class KnowledgeImportResult:
    document: KnowledgeDocumentModel
    action: KnowledgeImportAction
    warning: str | None = None
    conflict_type: str | None = None
    existing_document_id: UUID | None = None
    replaced_document_id: UUID | None = None


@dataclass(frozen=True)
class KnowledgeBatchPreviewItem:
    client_file_id: str
    original_filename: str | None
    relative_directory: str | None
    resolved_relative_path: str | None
    sha256_hash: str | None
    status: KnowledgeBatchPreviewStatus
    conflict_type: str | None = None
    existing_document_id: UUID | None = None
    existing_original_filename: str | None = None
    existing_relative_path: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class KnowledgeBatchPreviewSummary:
    total: int
    ready: int
    same_hash: int
    same_relative_path: int
    invalid: int


@dataclass(frozen=True)
class KnowledgeBatchPreviewResult:
    items: list[KnowledgeBatchPreviewItem]
    summary: KnowledgeBatchPreviewSummary


@dataclass(frozen=True)
class KnowledgeBatchImportItem:
    client_file_id: str
    original_filename: str | None
    resolved_relative_path: str | None
    action: KnowledgeBatchImportAction
    decision: str
    knowledge_document_id: UUID | None = None
    existing_document_id: UUID | None = None
    replaced_document_id: UUID | None = None
    conflict_type: str | None = None
    warning: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class KnowledgeBatchImportSummary:
    total: int
    imported: int
    skipped: int
    replaced: int
    failed: int


@dataclass(frozen=True)
class KnowledgeBatchImportResult:
    items: list[KnowledgeBatchImportItem]
    summary: KnowledgeBatchImportSummary


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
    conflict_strategy: KnowledgeImportConflictStrategy = "fail",
) -> KnowledgeImportResult:
    if conflict_strategy not in {"fail", "skip", "replace"}:
        raise KnowledgeImportError("Unsupported knowledge import conflict strategy")
    _ensure_markdown_upload(upload.filename)
    original_filename = Path(upload.filename or "document.md").name
    safe_relative_path = _build_import_relative_path(relative_path, original_filename)
    settings = get_settings()
    content = await _read_limited_upload(upload, settings.max_upload_bytes)
    sha256_hash = hashlib.sha256(content).hexdigest()

    duplicate = _find_knowledge_document_by_hash(db, sha256_hash)
    if duplicate is not None:
        return _handle_import_conflict(
            duplicate,
            conflict_type="same_hash",
            conflict_strategy=conflict_strategy,
            message="Knowledge document with this content hash already exists",
        )

    path_conflict = _find_knowledge_document_by_relative_path(db, safe_relative_path)
    if path_conflict is not None:
        if conflict_strategy != "replace":
            return _handle_import_conflict(
                path_conflict,
                conflict_type="same_relative_path",
                conflict_strategy=conflict_strategy,
                message="Knowledge document with this relative_path already exists",
            )
        replacement_document = path_conflict
    else:
        replacement_document = None

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
        original_filename=original_filename,
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
    if replacement_document is not None:
        replaced_document_id = replacement_document.id
        delete_knowledge_document(db, replacement_document.id)
        return KnowledgeImportResult(
            document=document,
            action="replaced",
            warning="A korábbi azonos relatív útvonalú tudásbázis dokumentum törölve lett.",
            conflict_type="same_relative_path",
            replaced_document_id=replaced_document_id,
        )
    return KnowledgeImportResult(document=document, action="imported")


async def preview_knowledge_document_batch(
    db: Session,
    uploads: list[UploadFile],
    *,
    relative_paths: list[str] | None = None,
    client_file_ids: list[str] | None = None,
) -> KnowledgeBatchPreviewResult:
    settings = get_settings()
    items: list[KnowledgeBatchPreviewItem] = []
    for index, upload in enumerate(uploads):
        client_file_id = _batch_value(client_file_ids, index) or f"file_{index + 1}"
        relative_directory = _batch_value(relative_paths, index)
        items.append(await _preview_knowledge_document(db, upload, settings.max_upload_bytes, client_file_id, relative_directory))
    return KnowledgeBatchPreviewResult(
        items=[item for item in items if item.status != "ready"],
        summary=_batch_preview_summary(items),
    )


async def import_knowledge_document_batch(
    db: Session,
    uploads: list[UploadFile],
    *,
    relative_paths: list[str] | None = None,
    client_file_ids: list[str] | None = None,
    decisions: list[str] | None = None,
) -> KnowledgeBatchImportResult:
    settings = get_settings()
    items: list[KnowledgeBatchImportItem] = []
    for index, upload in enumerate(uploads):
        client_file_id = _batch_value(client_file_ids, index) or f"file_{index + 1}"
        relative_directory = _batch_value(relative_paths, index)
        decision = (_batch_value(decisions, index) or "import").strip()
        preview = await _preview_knowledge_document(db, upload, settings.max_upload_bytes, client_file_id, relative_directory)
        await upload.seek(0)
        items.append(await _import_knowledge_document_from_batch_decision(db, upload, relative_directory, decision, preview))
    return KnowledgeBatchImportResult(
        items=[item for item in items if item.action != "imported"],
        summary=_batch_import_summary(items),
    )


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


async def _preview_knowledge_document(
    db: Session,
    upload: UploadFile,
    max_upload_bytes: int,
    client_file_id: str,
    relative_directory: str | None,
) -> KnowledgeBatchPreviewItem:
    original_filename = Path(upload.filename or "").name or None
    try:
        _ensure_markdown_upload(upload.filename)
        resolved_relative_path = _build_import_relative_path(
            relative_directory,
            original_filename or "document.md",
            require_relative_directory=True,
        )
        content = await _read_limited_upload(upload, max_upload_bytes)
        sha256_hash = hashlib.sha256(content).hexdigest()
    except UnsupportedKnowledgeDocumentTypeError as exc:
        return KnowledgeBatchPreviewItem(
            client_file_id=client_file_id,
            original_filename=original_filename,
            relative_directory=relative_directory,
            resolved_relative_path=None,
            sha256_hash=None,
            status="invalid",
            conflict_type="unsupported_file_type",
            error=str(exc),
        )
    except KnowledgeUploadTooLargeError as exc:
        return KnowledgeBatchPreviewItem(
            client_file_id=client_file_id,
            original_filename=original_filename,
            relative_directory=relative_directory,
            resolved_relative_path=None,
            sha256_hash=None,
            status="invalid",
            conflict_type="invalid_file",
            error=str(exc),
        )
    except KnowledgeImportError as exc:
        return KnowledgeBatchPreviewItem(
            client_file_id=client_file_id,
            original_filename=original_filename,
            relative_directory=relative_directory,
            resolved_relative_path=None,
            sha256_hash=None,
            status="invalid",
            conflict_type="unsafe_relative_path",
            error=str(exc),
        )

    duplicate = _find_knowledge_document_by_hash(db, sha256_hash)
    if duplicate is not None:
        return _batch_preview_conflict_item(
            client_file_id,
            original_filename,
            relative_directory,
            resolved_relative_path,
            sha256_hash,
            "same_hash",
            duplicate,
        )

    path_conflict = _find_knowledge_document_by_relative_path(db, resolved_relative_path)
    if path_conflict is not None:
        return _batch_preview_conflict_item(
            client_file_id,
            original_filename,
            relative_directory,
            resolved_relative_path,
            sha256_hash,
            "same_relative_path",
            path_conflict,
        )

    return KnowledgeBatchPreviewItem(
        client_file_id=client_file_id,
        original_filename=original_filename,
        relative_directory=_normalize_relative_directory(relative_directory),
        resolved_relative_path=resolved_relative_path,
        sha256_hash=sha256_hash,
        status="ready",
    )


def _batch_preview_conflict_item(
    client_file_id: str,
    original_filename: str | None,
    relative_directory: str | None,
    resolved_relative_path: str,
    sha256_hash: str,
    status: Literal["same_hash", "same_relative_path"],
    existing_document: KnowledgeDocumentModel,
) -> KnowledgeBatchPreviewItem:
    return KnowledgeBatchPreviewItem(
        client_file_id=client_file_id,
        original_filename=original_filename,
        relative_directory=_normalize_relative_directory(relative_directory),
        resolved_relative_path=resolved_relative_path,
        sha256_hash=None,
        status=status,
        conflict_type=status,
        existing_document_id=existing_document.id,
        existing_original_filename=existing_document.original_filename,
        existing_relative_path=existing_document.relative_path,
    )


def _batch_preview_summary(items: list[KnowledgeBatchPreviewItem]) -> KnowledgeBatchPreviewSummary:
    return KnowledgeBatchPreviewSummary(
        total=len(items),
        ready=sum(1 for item in items if item.status == "ready"),
        same_hash=sum(1 for item in items if item.status == "same_hash"),
        same_relative_path=sum(1 for item in items if item.status == "same_relative_path"),
        invalid=sum(1 for item in items if item.status == "invalid"),
    )


async def _import_knowledge_document_from_batch_decision(
    db: Session,
    upload: UploadFile,
    relative_directory: str | None,
    decision: str,
    preview: KnowledgeBatchPreviewItem,
) -> KnowledgeBatchImportItem:
    normalized_decision = decision.casefold()
    if normalized_decision == "keep_existing":
        normalized_decision = "skip"
    if normalized_decision not in {"import", "skip", "replace"}:
        return _batch_import_failed(preview, decision, f"Unsupported batch import decision: {decision}")

    if normalized_decision == "skip":
        return KnowledgeBatchImportItem(
            client_file_id=preview.client_file_id,
            original_filename=preview.original_filename,
            resolved_relative_path=preview.resolved_relative_path,
            action="skipped",
            decision=decision,
            existing_document_id=preview.existing_document_id,
            conflict_type=preview.conflict_type,
            warning="A fájl kihagyva.",
        )

    if preview.status == "invalid":
        return _batch_import_failed(preview, decision, preview.error or "A fájl nem importálható.")
    if normalized_decision == "replace" and preview.status != "same_relative_path":
        return _batch_import_failed(preview, decision, "Csere csak azonos relatív útvonalú ütközésnél engedélyezett.")
    if normalized_decision == "import" and preview.status in {"same_hash", "same_relative_path"}:
        return _batch_import_failed(preview, decision, "Az import döntés nem használható meglévő ütközés mellett.")

    conflict_strategy: KnowledgeImportConflictStrategy = "replace" if normalized_decision == "replace" else "fail"
    try:
        result = await import_knowledge_document(
            db,
            upload,
            relative_path=relative_directory,
            conflict_strategy=conflict_strategy,
        )
    except KnowledgeImportConflictError as exc:
        return _batch_import_failed(preview, decision, str(exc), conflict_type=exc.conflict_type, existing_document_id=exc.existing_document.id)
    except KnowledgeImportError as exc:
        return _batch_import_failed(preview, decision, str(exc))

    document = result.document
    action: KnowledgeBatchImportAction = "replaced" if result.action == "replaced" else "imported"
    return KnowledgeBatchImportItem(
        client_file_id=preview.client_file_id,
        original_filename=document.original_filename,
        resolved_relative_path=document.relative_path,
        action=action,
        decision=decision,
        knowledge_document_id=document.id,
        replaced_document_id=result.replaced_document_id,
        conflict_type=result.conflict_type,
        warning=result.warning,
    )


def _batch_import_failed(
    preview: KnowledgeBatchPreviewItem,
    decision: str,
    error: str,
    *,
    conflict_type: str | None = None,
    existing_document_id: UUID | None = None,
) -> KnowledgeBatchImportItem:
    return KnowledgeBatchImportItem(
        client_file_id=preview.client_file_id,
        original_filename=preview.original_filename,
        resolved_relative_path=preview.resolved_relative_path,
        action="failed",
        decision=decision,
        existing_document_id=existing_document_id or preview.existing_document_id,
        conflict_type=conflict_type or preview.conflict_type,
        error=error,
    )


def _batch_import_summary(items: list[KnowledgeBatchImportItem]) -> KnowledgeBatchImportSummary:
    return KnowledgeBatchImportSummary(
        total=len(items),
        imported=sum(1 for item in items if item.action == "imported"),
        skipped=sum(1 for item in items if item.action == "skipped"),
        replaced=sum(1 for item in items if item.action == "replaced"),
        failed=sum(1 for item in items if item.action == "failed"),
    )


def _batch_value(values: list[str] | None, index: int) -> str | None:
    if values is None or index >= len(values):
        return None
    value = values[index]
    return value if value != "" else None


def _find_knowledge_document_by_hash(db: Session, sha256_hash: str) -> KnowledgeDocumentModel | None:
    return db.execute(
        select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.sha256_hash == sha256_hash)
    ).scalar_one_or_none()


def _find_knowledge_document_by_relative_path(db: Session, relative_path: str | None) -> KnowledgeDocumentModel | None:
    if relative_path is None:
        return None
    return db.execute(
        select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.relative_path == relative_path)
    ).scalar_one_or_none()


def _handle_import_conflict(
    existing_document: KnowledgeDocumentModel,
    *,
    conflict_type: str,
    conflict_strategy: KnowledgeImportConflictStrategy,
    message: str,
) -> KnowledgeImportResult:
    if conflict_strategy == "fail":
        raise KnowledgeImportConflictError(
            message,
            conflict_type=conflict_type,
            existing_document=existing_document,
        )
    return KnowledgeImportResult(
        document=existing_document,
        action="skipped",
        warning=message,
        conflict_type=conflict_type,
        existing_document_id=existing_document.id,
    )


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


def _build_import_relative_path(relative_directory: str | None, filename: str, *, require_relative_directory: bool = False) -> str:
    safe_filename = Path(filename).name
    if not safe_filename or safe_filename in {".", ".."}:
        raise KnowledgeImportError("Unsafe knowledge filename")
    directory = _normalize_relative_directory(relative_directory)
    if directory is None:
        if require_relative_directory:
            raise KnowledgeImportError("Relative directory is required for knowledge batch import")
        return safe_filename
    if require_relative_directory:
        _validate_path_like_relative_directory(directory)
    return PurePath(directory, safe_filename).as_posix()


def _normalize_relative_directory(relative_directory: str | None) -> str | None:
    if relative_directory is None or relative_directory.strip() == "":
        return None
    normalized = relative_directory.strip().replace("\\", "/").strip("/")
    if normalized == "":
        return None
    pure = PurePath(normalized)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise KnowledgeImportError("Unsafe relative directory")
    return pure.as_posix()


def _validate_path_like_relative_directory(relative_directory: str) -> None:
    parts = PurePath(relative_directory).parts
    if len(parts) < 2:
        raise KnowledgeImportError("Relative directory must contain at least two path segments")
    for part in parts:
        if not any(character.isalnum() for character in part):
            raise KnowledgeImportError("Relative directory contains an invalid path segment")


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
