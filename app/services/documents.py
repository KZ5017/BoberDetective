from pathlib import Path, PurePath
from uuid import UUID, uuid4
import hashlib

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.case import CaseModel
from app.models.document import DocumentChunkModel, DocumentModel, DocumentPageModel
from app.schemas.document import DocumentImportMetadata
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.storage import StoragePaths
from app.services.users import get_or_create_dev_user


class DocumentImportError(ValueError):
    pass


class CaseNotFoundError(DocumentImportError):
    pass


class DuplicateDocumentError(DocumentImportError):
    pass


class UnsupportedDocumentTypeError(DocumentImportError):
    pass


class UploadTooLargeError(DocumentImportError):
    pass


class InvalidTextEncodingError(DocumentImportError):
    pass


CHUNKING_STRATEGY = "char_window_v1"
CHUNKER_VERSION = "1"
DEFAULT_CHUNK_MAX_CHARS = 2000
MIN_SOFT_BREAK_CHARS = 200


def list_documents(db: Session, case_id: UUID) -> list[DocumentModel]:
    return list(
        db.execute(
            select(DocumentModel)
            .where(DocumentModel.case_id == case_id)
            .order_by(DocumentModel.imported_at.desc())
        ).scalars()
    )


def list_document_pages(db: Session, case_id: UUID, document_id: UUID) -> list[DocumentPageModel]:
    return list(
        db.execute(
            select(DocumentPageModel)
            .where(DocumentPageModel.case_id == case_id, DocumentPageModel.document_id == document_id)
            .order_by(DocumentPageModel.page_number.asc(), DocumentPageModel.version_no.desc())
        ).scalars()
    )


def list_document_chunks(db: Session, case_id: UUID, document_id: UUID) -> list[DocumentChunkModel]:
    return list(
        db.execute(
            select(DocumentChunkModel)
            .where(DocumentChunkModel.case_id == case_id, DocumentChunkModel.document_id == document_id)
            .order_by(DocumentChunkModel.chunk_index.asc(), DocumentChunkModel.version_no.desc())
        ).scalars()
    )


async def import_txt_document(
    db: Session,
    case_id: UUID,
    upload: UploadFile,
    metadata: DocumentImportMetadata,
) -> DocumentModel:
    settings = get_settings()
    storage = StoragePaths(settings.data_root)
    user = get_or_create_dev_user(db)

    case = db.get(CaseModel, case_id)
    if case is None:
        raise CaseNotFoundError("Case not found")

    original_filename = _clean_original_filename(upload.filename)
    _validate_txt_upload(original_filename, upload.content_type)
    content = await _read_limited_upload(upload, settings.max_upload_bytes)
    extracted_text = _decode_txt(content)
    sha256_hash = hashlib.sha256(content).hexdigest()

    existing_document = db.execute(
        select(DocumentModel).where(
            DocumentModel.case_id == case_id,
            DocumentModel.sha256_hash == sha256_hash,
        )
    ).scalar_one_or_none()
    if existing_document is not None:
        raise DuplicateDocumentError("Document already exists in this case")

    document_id = uuid4()
    original_dir = storage.originals_dir(str(case_id), str(document_id))
    original_dir.mkdir(parents=True, exist_ok=True)
    stored_path = original_dir / "original.txt"
    _write_immutable_file(stored_path, content)

    document = DocumentModel(
        id=document_id,
        case_id=case_id,
        original_filename=original_filename,
        stored_path=str(stored_path),
        mime_type="text/plain",
        file_extension="txt",
        file_size_bytes=len(content),
        sha256_hash=sha256_hash,
        document_type=metadata.document_type,
        language_code=metadata.language_code,
        is_encrypted=False,
        imported_by_user_id=user.id,
        processing_status="processed",
        page_count=1,
        parser_name="txt_import",
        parser_version="1",
        notes=metadata.notes,
    )
    db.add(document)
    db.flush()

    page = DocumentPageModel(
        case_id=case_id,
        document_id=document.id,
        page_number=1,
        extracted_text=extracted_text,
        text_source="native",
        ocr_used=False,
        parser_name="txt_import",
        parser_version="1",
        version_no=1,
        is_current=True,
        text_char_count=len(extracted_text),
    )
    db.add(page)
    db.flush()

    chunks = _build_text_chunks(extracted_text)
    for chunk_index, chunk in enumerate(chunks):
        db.add(
            DocumentChunkModel(
                case_id=case_id,
                document_id=document.id,
                page_start=1,
                page_end=1,
                chunk_index=chunk_index,
                chunk_text=chunk.text,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                token_count=None,
                chunking_strategy=CHUNKING_STRATEGY,
                chunker_version=CHUNKER_VERSION,
                version_no=1,
                is_current=True,
            )
        )
    db.flush()

    event = AuditEvent(
        event_type="document_imported",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="document",
        related_object_id=str(document.id),
        related_document_id=str(document.id),
        related_page_id=str(page.id),
        input_summary={
            "original_filename": original_filename,
            "mime_type": upload.content_type,
            "file_size_bytes": len(content),
        },
        output_summary={
            "document_id": str(document.id),
            "page_count": document.page_count,
            "chunk_count": len(chunks),
            "chunking_strategy": CHUNKING_STRATEGY,
            "chunker_version": CHUNKER_VERSION,
            "sha256_hash": sha256_hash,
        },
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(storage).write(event)
    db.commit()
    db.refresh(document)
    return document


def _clean_original_filename(filename: str | None) -> str:
    if filename is None or filename.strip() == "":
        raise UnsupportedDocumentTypeError("Filename is required")
    clean_name = PurePath(filename).name.strip()
    if clean_name in {"", ".", ".."} or "\x00" in clean_name:
        raise UnsupportedDocumentTypeError("Invalid filename")
    if len(clean_name) > 255:
        raise UnsupportedDocumentTypeError("Filename is too long")
    return clean_name


def _validate_txt_upload(filename: str, content_type: str | None) -> None:
    if Path(filename).suffix.lower() != ".txt":
        raise UnsupportedDocumentTypeError("Only .txt import is supported in this MVP step")
    allowed_content_types = {None, "", "text/plain", "application/octet-stream"}
    if content_type not in allowed_content_types:
        raise UnsupportedDocumentTypeError("Only text/plain TXT import is supported")


async def _read_limited_upload(upload: UploadFile, max_upload_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total_size = 0
    while chunk := await upload.read(1024 * 1024):
        total_size += len(chunk)
        if total_size > max_upload_bytes:
            raise UploadTooLargeError("Upload exceeds configured size limit")
        chunks.append(chunk)
    if total_size == 0:
        raise UnsupportedDocumentTypeError("Empty files are not importable")
    return b"".join(chunks)


def _decode_txt(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidTextEncodingError("TXT import requires UTF-8 encoded content") from exc


def _write_immutable_file(path: Path, content: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(content)


class TextChunk:
    def __init__(self, text: str, char_start: int, char_end: int) -> None:
        self.text = text
        self.char_start = char_start
        self.char_end = char_end


def _build_text_chunks(text: str, max_chars: int = DEFAULT_CHUNK_MAX_CHARS) -> list[TextChunk]:
    if max_chars < 1:
        raise ValueError("max_chars must be positive")

    chunks: list[TextChunk] = []
    position = 0
    text_length = len(text)

    while position < text_length:
        window_end = min(position + max_chars, text_length)
        if window_end < text_length:
            window_end = _find_chunk_break(text, position, window_end, max_chars)

        chunk_start, chunk_end = _trim_chunk_span(text, position, window_end)
        if chunk_start < chunk_end:
            chunks.append(TextChunk(text=text[chunk_start:chunk_end], char_start=chunk_start, char_end=chunk_end))

        position = max(window_end, position + 1)

    return chunks


def _find_chunk_break(text: str, start: int, hard_end: int, max_chars: int) -> int:
    min_soft_break = start + min(MIN_SOFT_BREAK_CHARS, max_chars)
    for separator in ("\n\n", "\n", " "):
        break_at = text.rfind(separator, start, hard_end)
        if break_at >= min_soft_break:
            return break_at + len(separator)
    return hard_end


def _trim_chunk_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end
