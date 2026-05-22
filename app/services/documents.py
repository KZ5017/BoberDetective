from datetime import UTC, datetime
from pathlib import Path, PurePath
from uuid import UUID, uuid4
import hashlib
import shutil

from fastapi import UploadFile
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import AnalysisRunInputModel, AnalysisRunModel, AnalysisRunOutputModel
from app.models.case import CaseModel
from app.models.document import DocumentChunkModel, DocumentModel, DocumentPageModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.document import DocumentImportMetadata
from app.schemas.document import DocumentOcrRecommendation
from app.schemas.document import DocumentTaxonomyUpdateRequest
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.analysis_runs import (
    add_analysis_run_input,
    add_analysis_run_output,
    finish_analysis_run,
    start_analysis_run,
)
from app.services.pdf_parsers import (
    NoExtractedTextError,
    PdfParseResult,
    ParsedPdfPage,
    PdfParserUnavailableError,
    PdfParsingError,
    parse_pdf,
)
from app.services.ocr import OcrDocumentResult, OcrError, ocr_pdf_document
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


class DocumentProcessingError(ValueError):
    pass


class DocumentNotFoundError(DocumentProcessingError):
    pass


class UnsupportedOcrDocumentError(DocumentProcessingError):
    pass


class DocumentChunkingError(DocumentProcessingError):
    pass


class DocumentLifecycleError(DocumentProcessingError):
    pass


CHUNKING_STRATEGY = "char_window_v2"
CHUNKER_VERSION = "2"
DEFAULT_CHUNK_MAX_CHARS = 2000
MIN_SOFT_BREAK_CHARS = 200
OCR_MIN_AVG_CONFIDENCE = 0.5
OCR_MIN_TEXT_CHARS_PER_PAGE = 120
ACTIVE_DOCUMENT_STATUS = "active"
NON_DISCARDABLE_RUN_TYPES = {
    "extract_entities",
    "extract_events",
    "extract_claims",
    "detect_contradictions",
    "detect_missing_items",
    "summarize_case",
    "answer_with_citations",
    "export_bundle",
    "manual_entry",
    "embed_chunks",
    "index_chunks",
    "search_findings",
}


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
            .where(
                DocumentPageModel.case_id == case_id,
                DocumentPageModel.document_id == document_id,
                DocumentPageModel.is_current.is_(True),
            )
            .order_by(DocumentPageModel.page_number.asc())
        ).scalars()
    )


def list_document_chunks(db: Session, case_id: UUID, document_id: UUID) -> list[DocumentChunkModel]:
    return list(
        db.execute(
            select(DocumentChunkModel)
            .where(
                DocumentChunkModel.case_id == case_id,
                DocumentChunkModel.document_id == document_id,
                DocumentChunkModel.is_current.is_(True),
            )
            .order_by(DocumentChunkModel.chunk_index.asc())
        ).scalars()
    )


def update_document_taxonomy(
    db: Session,
    case_id: UUID,
    document_id: UUID,
    payload: DocumentTaxonomyUpdateRequest,
) -> DocumentModel:
    document = db.get(DocumentModel, document_id)
    if document is None or document.case_id != case_id:
        raise DocumentNotFoundError("Document not found")

    user = get_or_create_dev_user(db)
    previous_group_code = document.document_group_code
    previous_type_code = document.document_type_code
    changed = (
        previous_group_code != payload.document_group_code
        or previous_type_code != payload.document_type_code
    )

    document.document_group_code = payload.document_group_code
    document.document_type_code = payload.document_type_code
    db.add(document)
    db.flush()

    event = AuditEvent(
        event_type="document_reclassified",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="document",
        related_object_id=str(document.id),
        related_document_id=str(document.id),
        input_summary={
            "document_id": str(document.id),
            "previous_document_group_code": previous_group_code,
            "previous_document_type_code": previous_type_code,
            "new_document_group_code": payload.document_group_code,
            "new_document_type_code": payload.document_type_code,
            "comment": payload.comment,
        },
        output_summary={
            "document_id": str(document.id),
            "document_group_code": document.document_group_code,
            "document_type_code": document.document_type_code,
            "changed": changed,
        },
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(event)
    db.commit()
    db.refresh(document)
    return document


def update_document_lifecycle_status(
    db: Session,
    case_id: UUID,
    document_id: UUID,
    target_status: str,
    *,
    reason: str | None = None,
) -> DocumentModel:
    if target_status not in {"active", "excluded", "archived"}:
        raise DocumentLifecycleError("Unsupported document lifecycle status")
    document = db.get(DocumentModel, document_id)
    if document is None or document.case_id != case_id:
        raise DocumentNotFoundError("Document not found")

    user = get_or_create_dev_user(db)
    previous_status = document.lifecycle_status
    changed = previous_status != target_status
    document.lifecycle_status = target_status
    document.lifecycle_status_changed_at = datetime.now(UTC)
    document.lifecycle_status_changed_by_user_id = user.id
    document.lifecycle_status_reason = reason
    db.add(document)
    db.flush()

    event_type = {
        "active": "document_restored",
        "excluded": "document_excluded",
        "archived": "document_archived",
    }[target_status]
    event = AuditEvent(
        event_type=event_type,
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="document",
        related_object_id=str(document.id),
        related_document_id=str(document.id),
        input_summary={
            "document_id": str(document.id),
            "previous_lifecycle_status": previous_status,
            "new_lifecycle_status": target_status,
            "reason": reason,
        },
        output_summary={
            "document_id": str(document.id),
            "lifecycle_status": document.lifecycle_status,
            "changed": changed,
        },
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(event)
    db.commit()
    db.refresh(document)
    return document


def discard_document(db: Session, case_id: UUID, document_id: UUID, *, reason: str | None = None) -> None:
    document = db.get(DocumentModel, document_id)
    if document is None or document.case_id != case_id:
        raise DocumentNotFoundError("Document not found")
    _ensure_document_discardable(db, case_id, document)

    user = get_or_create_dev_user(db)
    storage = StoragePaths(get_settings().data_root)
    stored_path = _stored_document_path_under_data_root(document, storage)
    original_dir = storage.originals_dir(str(case_id), str(document.id))
    derived_dir = storage.derived_dir(str(case_id), str(document.id))
    page_ids = list(
        db.execute(select(DocumentPageModel.id).where(DocumentPageModel.case_id == case_id, DocumentPageModel.document_id == document.id)).scalars()
    )
    run_ids = _discardable_document_run_ids(db, case_id, document.id, page_ids)

    event = AuditEvent(
        event_type="document_discarded",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="document",
        related_object_id=str(document.id),
        related_document_id=str(document.id),
        input_summary={
            "document_id": str(document.id),
            "original_filename": document.original_filename,
            "lifecycle_status": document.lifecycle_status,
            "processing_status": document.processing_status,
            "reason": reason,
        },
        output_summary={
            "deleted_page_count": len(page_ids),
            "deleted_run_count": len(run_ids),
            "sha256_hash": document.sha256_hash,
        },
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(storage).write(event)

    if run_ids:
        db.execute(delete(AnalysisRunOutputModel).where(AnalysisRunOutputModel.analysis_run_id.in_(run_ids)))
        db.execute(delete(AnalysisRunInputModel).where(AnalysisRunInputModel.analysis_run_id.in_(run_ids)))
        db.execute(delete(AnalysisRunModel).where(AnalysisRunModel.id.in_(run_ids)))
    if page_ids:
        db.execute(delete(DocumentPageModel).where(DocumentPageModel.id.in_(page_ids)))
    db.delete(document)
    db.commit()

    _remove_path_if_exists(original_dir)
    _remove_path_if_exists(derived_dir)
    if stored_path.exists():
        _remove_path_if_exists(stored_path)


def _ensure_document_discardable(db: Session, case_id: UUID, document: DocumentModel) -> None:
    chunk_count = db.execute(
        select(func.count()).select_from(DocumentChunkModel).where(DocumentChunkModel.case_id == case_id, DocumentChunkModel.document_id == document.id)
    ).scalar_one()
    if int(chunk_count) > 0:
        raise DocumentLifecycleError("Document cannot be discarded after chunks have been created")

    source_reference_count = db.execute(
        select(func.count()).select_from(SourceReferenceModel).where(SourceReferenceModel.case_id == case_id, SourceReferenceModel.document_id == document.id)
    ).scalar_one()
    if int(source_reference_count) > 0:
        raise DocumentLifecycleError("Document cannot be discarded because source references exist")

    page_ids = list(
        db.execute(select(DocumentPageModel.id).where(DocumentPageModel.case_id == case_id, DocumentPageModel.document_id == document.id)).scalars()
    )
    run_ids = _document_run_ids(db, case_id, document.id, page_ids)
    if run_ids:
        blocked_count = db.execute(
            select(func.count()).select_from(AnalysisRunModel).where(
                AnalysisRunModel.id.in_(run_ids),
                AnalysisRunModel.run_type.in_(NON_DISCARDABLE_RUN_TYPES),
            )
        ).scalar_one()
        if int(blocked_count) > 0:
            raise DocumentLifecycleError("Document cannot be discarded because it has analysis history")


def _ensure_active_document(document: DocumentModel) -> None:
    if document.lifecycle_status != ACTIVE_DOCUMENT_STATUS:
        raise DocumentLifecycleError("Document is not active")


def _discardable_document_run_ids(db: Session, case_id: UUID, document_id: UUID, page_ids: list[UUID]) -> list[UUID]:
    run_ids = _document_run_ids(db, case_id, document_id, page_ids)
    if not run_ids:
        return []
    return list(
        db.execute(
            select(AnalysisRunModel.id).where(
                AnalysisRunModel.id.in_(run_ids),
                AnalysisRunModel.run_type.not_in(NON_DISCARDABLE_RUN_TYPES),
            )
        ).scalars()
    )


def _document_run_ids(db: Session, case_id: UUID, document_id: UUID, page_ids: list[UUID]) -> list[UUID]:
    conditions = [AnalysisRunInputModel.document_id == document_id]
    if page_ids:
        conditions.append(AnalysisRunInputModel.page_id.in_(page_ids))
    stmt = (
        select(AnalysisRunInputModel.analysis_run_id)
        .join(AnalysisRunModel, AnalysisRunModel.id == AnalysisRunInputModel.analysis_run_id)
        .where(AnalysisRunModel.case_id == case_id)
        .where(or_(*conditions))
        .distinct()
    )
    return list(db.execute(stmt).scalars())


def _remove_path_if_exists(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink(missing_ok=True)


def document_ocr_recommendation(db: Session, document: DocumentModel) -> DocumentOcrRecommendation:
    if document.file_extension != "pdf" or document.mime_type != "application/pdf":
        return DocumentOcrRecommendation(action="hidden", reason_code="not_pdf", message="OCR csak PDF iratoknal ertelmezett.")
    if document.processing_status == "processing":
        return DocumentOcrRecommendation(action="hidden", reason_code="processing", message="Az irat feldolgozasa folyamatban van.")

    pages = _list_current_pages(db, document.case_id, document.id)
    chunks = _list_current_chunks(db, document.case_id, document.id)
    return _ocr_recommendation_from_stats(document.processing_status, document.page_count, pages, chunks)


def _ocr_recommendation_from_stats(
    processing_status: str,
    page_count: int | None,
    pages: list[DocumentPageModel],
    chunks: list[DocumentChunkModel],
) -> DocumentOcrRecommendation:
    if processing_status in {"review_required", "failed"} and not pages:
        return DocumentOcrRecommendation(
            action="recommended",
            reason_code=f"status_{processing_status}",
            message="Az irat allapota alapjan OCR ellenorzes javasolt.",
        )
    if page_count == 0 or not pages:
        return DocumentOcrRecommendation(
            action="recommended",
            reason_code="no_pages",
            message="Nem talalhato kinyert oldal, ezert OCR javasolt.",
        )
    total_text_chars = sum(page.text_char_count for page in pages)
    if total_text_chars == 0:
        return DocumentOcrRecommendation(
            action="recommended",
            reason_code="no_text",
            message="Nem talalhato kinyert szoveg, ezert OCR javasolt.",
        )

    effective_page_count = page_count or len(pages)
    if effective_page_count > 0 and total_text_chars / effective_page_count < OCR_MIN_TEXT_CHARS_PER_PAGE:
        return DocumentOcrRecommendation(
            action="recommended",
            reason_code="very_low_text_density",
            message="Nagyon keves kinyert szoveg jut egy oldalra, ezert OCR javasolt.",
        )

    empty_pages = [page for page in pages if page.text_char_count == 0]
    if empty_pages:
        return DocumentOcrRecommendation(
            action="optional",
            reason_code="empty_pages_with_text",
            message="Van kinyert szoveg, de egyes oldalak uresek. Az OCR ellenorzes segithet, de duplikalt vagy zajos szoveget is eredmenyezhet.",
        )
    if not chunks:
        return DocumentOcrRecommendation(
            action="hidden",
            reason_code="text_layer_awaits_chunking",
            message="Van kinyert szoveg; ellenorzes utan hozd letre a szovegreszeket.",
        )

    return DocumentOcrRecommendation(
        action="hidden",
        reason_code="native_text_available",
        message="Az iratnak van feldolgozott szovege es szovegresze; OCR alapbol nem szukseges.",
    )


def process_document(db: Session, case_id: UUID, document_id: UUID, *, reason: str | None = None) -> AnalysisRunModel:
    document = db.get(DocumentModel, document_id)
    if document is None or document.case_id != case_id:
        raise DocumentNotFoundError("Document not found")
    _ensure_active_document(document)

    run = start_analysis_run(
        db,
        case_id,
        "validate_document_processing",
        provider_type="local_pipeline",
        model_name="document_processing_v1",
        input_parameters={
            "document_id": str(document.id),
            "reason": reason,
            "parser_name": document.parser_name,
            "parser_version": document.parser_version,
            "chunking_strategy": CHUNKING_STRATEGY,
            "chunker_version": CHUNKER_VERSION,
        },
    )

    document.processing_status = "processing"
    db.add(document)
    db.flush()

    add_analysis_run_input(db, run.id, "document", 0, document_id=document.id)
    current_pages = _list_current_pages(db, case_id, document_id)
    current_chunks = _list_current_chunks(db, case_id, document_id)
    for position, page in enumerate(current_pages):
        add_analysis_run_output(db, run.id, "page", page.id, position)
    for position, chunk in enumerate(current_chunks, start=len(current_pages)):
        add_analysis_run_output(db, run.id, "chunk", chunk.id, position)

    validation = _validate_current_document_processing(document, current_pages, current_chunks)
    document.processing_status = validation["document_status"]
    db.add(document)
    db.flush()

    _write_document_processing_audit(db, run, document, validation)
    return finish_analysis_run(
        db,
        run,
        status=validation["run_status"],
        validation_status=validation["validation_status"],
        error_message=validation["error_message"],
        output_summary={
            "document_id": str(document.id),
            "document_status": document.processing_status,
            "page_count": len(current_pages),
            "chunk_count": len(current_chunks),
            "issues": validation["issues"],
        },
    )


def create_document_chunks(db: Session, case_id: UUID, document_id: UUID, *, reason: str | None = None) -> AnalysisRunModel:
    document = db.get(DocumentModel, document_id)
    if document is None or document.case_id != case_id:
        raise DocumentNotFoundError("Document not found")
    _ensure_active_document(document)

    current_pages = _list_current_pages(db, case_id, document_id)
    current_chunks = _list_current_chunks(db, case_id, document_id)
    if not current_pages:
        raise DocumentChunkingError("No current text pages are available for chunking")
    if current_chunks:
        raise DocumentChunkingError("Current chunks already exist for this document")

    run = start_analysis_run(
        db,
        case_id,
        "chunk_document",
        provider_type="local_pipeline",
        model_name=CHUNKING_STRATEGY,
        model_version=CHUNKER_VERSION,
        input_parameters={
            "document_id": str(document.id),
            "reason": reason,
            "chunking_strategy": CHUNKING_STRATEGY,
            "chunker_version": CHUNKER_VERSION,
            "source_text_layer": current_pages[0].text_source if current_pages else None,
        },
    )
    add_analysis_run_input(db, run.id, "document", 0, document_id=document.id)
    for index, page in enumerate(current_pages, start=1):
        add_analysis_run_input(db, run.id, "page", index, document_id=document.id, page_id=page.id)

    document.processing_status = "processing"
    db.add(document)
    db.flush()

    chunk_count = _create_chunks_from_pages(db, case_id, document, current_pages, run.id)
    current_chunks = _list_current_chunks(db, case_id, document_id)
    validation = _validate_current_document_processing(document, current_pages, current_chunks)
    document.processing_status = validation["document_status"]
    db.add(document)
    db.flush()

    _write_document_processing_audit(db, run, document, validation)
    return finish_analysis_run(
        db,
        run,
        status=validation["run_status"],
        validation_status=validation["validation_status"],
        error_message=validation["error_message"],
        output_summary={
            "document_id": str(document.id),
            "document_status": document.processing_status,
            "page_count": len(current_pages),
            "chunk_count": chunk_count,
            "issues": validation["issues"],
        },
    )


def ocr_document(
    db: Session,
    case_id: UUID,
    document_id: UUID,
    *,
    reason: str | None = None,
    language: str | None = None,
) -> AnalysisRunModel:
    settings = get_settings()
    storage = StoragePaths(settings.data_root)
    document = db.get(DocumentModel, document_id)
    if document is None or document.case_id != case_id:
        raise DocumentNotFoundError("Document not found")
    _ensure_active_document(document)
    if document.file_extension != "pdf" or document.mime_type != "application/pdf":
        raise UnsupportedOcrDocumentError("OCR is currently supported for PDF documents only")

    pdf_path = _stored_document_path_under_data_root(document, storage)
    ocr_language = language or settings.tesseract_languages
    user = get_or_create_dev_user(db)
    run = start_analysis_run(
        db,
        case_id,
        "ocr_document",
        provider_type="local_ocr",
        model_name="tesseract",
        input_parameters={
            "document_id": str(document.id),
            "reason": reason,
            "language": ocr_language,
            "source_path": "stored_original",
            "chunking_strategy": CHUNKING_STRATEGY,
            "chunker_version": CHUNKER_VERSION,
        },
    )
    add_analysis_run_input(db, run.id, "document", 0, document_id=document.id)

    try:
        result = ocr_pdf_document(
            pdf_path,
            storage.derived_dir(str(case_id), str(document.id)) / "ocr" / str(run.id),
            tesseract_cmd=settings.tesseract_cmd,
            languages=ocr_language,
            run_id=run.id,
        )
        run.model_version = result.tool_version
        if run.input_parameters is not None:
            run.input_parameters = {**run.input_parameters, "tool_version": result.tool_version}
        db.add(run)
        _persist_ocr_pages(db, case_id, document, result, run.id)
        quality_issues = _ocr_quality_issues(result)
        document.page_count = len(result.pages)
        document.parser_name = result.tool_name
        document.parser_version = result.tool_version
        document.processing_status = "text_review_required"
        db.add(document)
        db.flush()
        _write_ocr_audit(db, user.id, document, run, result, True, quality_issues=quality_issues)
        finish_analysis_run(
            db,
            run,
            status="succeeded",
            validation_status="warning" if quality_issues else "passed",
            output_summary={
                "document_id": str(document.id),
                "document_status": document.processing_status,
                "page_count": len(result.pages),
                "chunk_count": 0,
                "tool_name": result.tool_name,
                "tool_version": result.tool_version,
                "language": result.language,
                "quality_issues": quality_issues,
                "next_action": "review_text_layer_then_create_chunks",
            },
        )
    except OcrError as exc:
        document.processing_status = "failed"
        db.add(document)
        db.flush()
        _write_ocr_audit(db, user.id, document, run, None, False, error_message=str(exc))
        finish_analysis_run(
            db,
            run,
            status="failed",
            validation_status="failed",
            error_message=str(exc),
            output_summary={"document_id": str(document.id)},
        )
        raise DocumentProcessingError(str(exc)) from exc

    return run


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
        document_group_code=metadata.document_group_code or "uncategorized",
        document_type_code=metadata.document_type_code or "uncategorized",
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


async def import_document(
    db: Session,
    case_id: UUID,
    upload: UploadFile,
    metadata: DocumentImportMetadata,
) -> DocumentModel:
    if _is_pdf_upload(upload.filename, upload.content_type):
        return await import_pdf_document(db, case_id, upload, metadata)
    return await import_txt_document(db, case_id, upload, metadata)


async def import_pdf_document(
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
    _validate_pdf_upload(original_filename, upload.content_type)
    content = await _read_limited_upload(upload, settings.max_upload_bytes)
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
    stored_path = original_dir / "original.pdf"
    _write_immutable_file(stored_path, content)

    parser_profile = settings.pdf_parser
    document = DocumentModel(
        id=document_id,
        case_id=case_id,
        original_filename=original_filename,
        stored_path=str(stored_path),
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=len(content),
        sha256_hash=sha256_hash,
        document_group_code=metadata.document_group_code or "uncategorized",
        document_type_code=metadata.document_type_code or "uncategorized",
        language_code=metadata.language_code,
        is_encrypted=False,
        imported_by_user_id=user.id,
        processing_status="processing",
        parser_name=None,
        parser_version=None,
        notes=metadata.notes,
    )
    db.add(document)
    db.flush()

    run = start_analysis_run(
        db,
        case_id,
        "parse_document",
        provider_type="local_parser",
        model_name=parser_profile,
        model_version=None,
        input_parameters={
            "document_id": str(document.id),
            "original_filename": original_filename,
            "mime_type": "application/pdf",
            "parser_profile": parser_profile,
            "chunking_strategy": CHUNKING_STRATEGY,
            "chunker_version": CHUNKER_VERSION,
        },
    )
    add_analysis_run_input(db, run.id, "document", 0, document_id=document.id)

    try:
        parse_result = parse_pdf(content, parser_profile)
        document.parser_name = parse_result.parser_name
        document.parser_version = parse_result.parser_version
        run.model_name = parse_result.parser_name
        run.model_version = parse_result.parser_version
        if run.input_parameters is not None:
            run.input_parameters = {
                **run.input_parameters,
                "parser_name": parse_result.parser_name,
                "parser_version": parse_result.parser_version,
                "parser_profile_used": parse_result.parser_profile,
            }
        db.add(run)
        _persist_parsed_pages(db, case_id, document, parse_result.pages, run.id, parse_result)
        quality_issues = _pdf_parse_quality_issues(parse_result.pages)
        document.page_count = len(parse_result.pages)
        document.processing_status = "text_review_required"
        db.add(document)
        db.flush()
        _write_pdf_import_audit(
            db,
            user.id,
            document,
            run.id,
            success=True,
            page_count=len(parse_result.pages),
            quality_issues=quality_issues,
        )
        finish_analysis_run(
            db,
            run,
            status="succeeded",
            validation_status="warning" if quality_issues else "passed",
            output_summary={
                "document_id": str(document.id),
                "document_status": document.processing_status,
                "page_count": len(parse_result.pages),
                "chunk_count": 0,
                "parser_name": parse_result.parser_name,
                "parser_version": parse_result.parser_version,
                "parser_profile": parse_result.parser_profile,
                "quality_issues": quality_issues,
                "next_action": "review_text_layer_then_create_chunks",
            },
        )
    except NoExtractedTextError as exc:
        quality_issues = [{"code": "no_native_text", "severity": "warning", "message": str(exc)}]
        document.parser_name = parser_profile
        document.parser_version = None
        document.page_count = 0
        document.processing_status = "review_required"
        db.add(document)
        db.flush()
        _write_pdf_import_audit(
            db,
            user.id,
            document,
            run.id,
            success=True,
            page_count=0,
            quality_issues=quality_issues,
        )
        finish_analysis_run(
            db,
            run,
            status="succeeded",
            validation_status="warning",
            output_summary={
                "document_id": str(document.id),
                "document_status": document.processing_status,
                "page_count": 0,
                "chunk_count": 0,
                "parser_profile": parser_profile,
                "quality_issues": quality_issues,
                "next_action": "run_ocr",
            },
        )
    except PdfParsingError as exc:
        document.processing_status = "failed"
        db.add(document)
        db.flush()
        _write_pdf_import_audit(db, user.id, document, run.id, success=False, error_message=str(exc))
        finish_analysis_run(
            db,
            run,
            status="failed",
            validation_status="failed",
            error_message=str(exc),
            output_summary={"document_id": str(document.id)},
        )
        raise

    db.refresh(document)
    return document


def parse_native_pdf_pages(content: bytes) -> list[ParsedPdfPage]:
    return parse_pdf(content, "pypdf").pages


def _persist_parsed_pages(
    db: Session,
    case_id: UUID,
    document: DocumentModel,
    pages: list[ParsedPdfPage],
    run_id: UUID,
    parse_result: PdfParseResult,
) -> None:
    output_position = 0
    for page in pages:
        page_record = DocumentPageModel(
            case_id=case_id,
            document_id=document.id,
            page_number=page.page_number,
            extracted_text=page.text,
            text_source="native",
            ocr_used=False,
            parser_name=parse_result.parser_name,
            parser_version=parse_result.parser_version,
            extraction_run_id=run_id,
            version_no=1,
            is_current=True,
            text_char_count=len(page.text),
        )
        db.add(page_record)
        db.flush()
        add_analysis_run_output(db, run_id, "page", page_record.id, output_position)
        output_position += 1


def _persist_ocr_pages(
    db: Session,
    case_id: UUID,
    document: DocumentModel,
    result: OcrDocumentResult,
    run_id: UUID,
) -> None:
    previous_pages = _list_current_pages(db, case_id, document.id)
    previous_chunks = _list_current_chunks(db, case_id, document.id)
    previous_page_by_number = {page.page_number: page for page in previous_pages}
    next_page_version = _next_page_version(db, document.id)

    for page in previous_pages:
        page.is_current = False
        db.add(page)
    for chunk in previous_chunks:
        chunk.is_current = False
        db.add(chunk)
    db.flush()

    output_position = 0
    new_page_by_number: dict[int, DocumentPageModel] = {}
    for ocr_page in result.pages:
        page_record = DocumentPageModel(
            case_id=case_id,
            document_id=document.id,
            page_number=ocr_page.page_number,
            extracted_text=ocr_page.text,
            text_source="ocr",
            ocr_used=True,
            ocr_confidence=ocr_page.confidence,
            parser_name=result.tool_name,
            parser_version=result.tool_version,
            extraction_run_id=run_id,
            version_no=next_page_version,
            is_current=True,
            text_char_count=len(ocr_page.text),
        )
        db.add(page_record)
        db.flush()
        new_page_by_number[ocr_page.page_number] = page_record
        add_analysis_run_output(db, run_id, "page", page_record.id, output_position)
        output_position += 1

    for page_number, previous_page in previous_page_by_number.items():
        if page_number in new_page_by_number:
            previous_page.superseded_by_id = new_page_by_number[page_number].id
            db.add(previous_page)
    db.flush()


def _create_chunks_from_pages(
    db: Session,
    case_id: UUID,
    document: DocumentModel,
    pages: list[DocumentPageModel],
    run_id: UUID,
) -> int:
    previous_chunks = _list_current_chunks(db, case_id, document.id)
    for chunk in previous_chunks:
        chunk.is_current = False
        db.add(chunk)
    db.flush()

    next_chunk_version = _next_chunk_version(db, document.id)
    output_position = 0
    next_chunk_index = 0
    for page in pages:
        for chunk in _build_text_chunks(page.extracted_text):
            chunk_record = DocumentChunkModel(
                case_id=case_id,
                document_id=document.id,
                page_start=page.page_number,
                page_end=page.page_number,
                chunk_index=next_chunk_index,
                chunk_text=chunk.text,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                token_count=None,
                chunking_strategy=CHUNKING_STRATEGY,
                chunker_version=CHUNKER_VERSION,
                chunk_run_id=run_id,
                version_no=next_chunk_version,
                is_current=True,
            )
            db.add(chunk_record)
            db.flush()
            add_analysis_run_output(db, run_id, "chunk", chunk_record.id, output_position)
            output_position += 1
            next_chunk_index += 1
    return next_chunk_index


def _pdf_parse_quality_issues(pages: list[ParsedPdfPage]) -> list[dict]:
    issues: list[dict] = []
    empty_page_numbers = [page.page_number for page in pages if page.text.strip() == ""]
    if empty_page_numbers:
        issues.append(
            {
                "code": "empty_pages",
                "severity": "warning",
                "page_numbers": empty_page_numbers,
            }
        )
    return issues


def _ocr_quality_issues(result: OcrDocumentResult) -> list[dict]:
    issues: list[dict] = []
    empty_page_numbers = [page.page_number for page in result.pages if page.text.strip() == ""]
    if empty_page_numbers:
        issues.append({"code": "empty_ocr_pages", "severity": "warning", "page_numbers": empty_page_numbers})
    low_confidence_pages = [
        {"page_number": page.page_number, "confidence": getattr(page, "confidence", None)}
        for page in result.pages
        if getattr(page, "confidence", None) is not None and getattr(page, "confidence") < OCR_MIN_AVG_CONFIDENCE
    ]
    if low_confidence_pages:
        issues.append(
            {
                "code": "low_ocr_confidence",
                "severity": "warning",
                "threshold": OCR_MIN_AVG_CONFIDENCE,
                "pages": low_confidence_pages,
            }
        )
    return issues


def _next_page_version(db: Session, document_id: UUID) -> int:
    versions = db.execute(
        select(DocumentPageModel.version_no).where(DocumentPageModel.document_id == document_id)
    ).scalars()
    return max(versions, default=0) + 1


def _next_chunk_version(db: Session, document_id: UUID) -> int:
    versions = db.execute(
        select(DocumentChunkModel.version_no).where(DocumentChunkModel.document_id == document_id)
    ).scalars()
    return max(versions, default=0) + 1


def _stored_document_path_under_data_root(document: DocumentModel, storage: StoragePaths) -> Path:
    path = Path(document.stored_path).expanduser().resolve()
    try:
        path.relative_to(storage.data_root)
    except ValueError as exc:
        raise DocumentProcessingError("Stored document path escapes configured data root") from exc
    return path


def _list_current_pages(db: Session, case_id: UUID, document_id: UUID) -> list[DocumentPageModel]:
    return list(
        db.execute(
            select(DocumentPageModel)
            .where(
                DocumentPageModel.case_id == case_id,
                DocumentPageModel.document_id == document_id,
                DocumentPageModel.is_current.is_(True),
            )
            .order_by(DocumentPageModel.page_number.asc())
        ).scalars()
    )


def _list_current_chunks(db: Session, case_id: UUID, document_id: UUID) -> list[DocumentChunkModel]:
    return list(
        db.execute(
            select(DocumentChunkModel)
            .where(
                DocumentChunkModel.case_id == case_id,
                DocumentChunkModel.document_id == document_id,
                DocumentChunkModel.is_current.is_(True),
            )
            .order_by(DocumentChunkModel.chunk_index.asc())
        ).scalars()
    )


def _validate_current_document_processing(
    document: DocumentModel,
    pages: list[DocumentPageModel],
    chunks: list[DocumentChunkModel],
) -> dict:
    issues: list[dict] = []
    if not pages:
        issues.append({"code": "no_current_pages", "severity": "error"})

    page_numbers = [page.page_number for page in pages]
    if page_numbers and page_numbers != list(range(1, len(page_numbers) + 1)):
        issues.append({"code": "non_contiguous_pages", "severity": "error", "page_numbers": page_numbers})

    total_text_chars = sum(page.text_char_count for page in pages)
    if pages and total_text_chars == 0:
        issues.append({"code": "no_extracted_text", "severity": "warning"})

    empty_page_numbers = [page.page_number for page in pages if page.text_char_count == 0]
    if empty_page_numbers and total_text_chars > 0:
        issues.append({"code": "empty_pages", "severity": "warning", "page_numbers": empty_page_numbers})

    if total_text_chars > 0 and not chunks:
        issues.append({"code": "no_current_chunks", "severity": "error"})

    invalid_chunk_ids = [
        str(chunk.id)
        for chunk in chunks
        if chunk.page_start < 1 or chunk.page_end < chunk.page_start or chunk.page_end > max(page_numbers, default=0)
    ]
    if invalid_chunk_ids:
        issues.append({"code": "invalid_chunk_page_range", "severity": "error", "chunk_ids": invalid_chunk_ids})

    expected_page_count = len(pages) if pages else None
    if document.page_count is not None and expected_page_count is not None and document.page_count != expected_page_count:
        issues.append(
            {
                "code": "document_page_count_mismatch",
                "severity": "warning",
                "document_page_count": document.page_count,
                "current_page_count": expected_page_count,
            }
        )

    has_errors = any(issue["severity"] == "error" for issue in issues)
    has_warnings = any(issue["severity"] == "warning" for issue in issues)
    if has_errors:
        return {
            "run_status": "failed",
            "validation_status": "failed",
            "document_status": "failed",
            "error_message": "Document processing validation failed",
            "issues": issues,
        }
    if has_warnings:
        return {
            "run_status": "succeeded",
            "validation_status": "warning",
            "document_status": "review_required",
            "error_message": None,
            "issues": issues,
        }
    return {
        "run_status": "succeeded",
        "validation_status": "passed",
        "document_status": "processed",
        "error_message": None,
        "issues": issues,
    }


def _write_document_processing_audit(
    db: Session,
    run: AnalysisRunModel,
    document: DocumentModel,
    validation: dict,
) -> None:
    if validation["document_status"] == "review_required":
        event_type = "document_processing_review_required"
        success = True
    elif validation["document_status"] == "failed":
        event_type = "document_processing_failed"
        success = False
    else:
        event_type = "document_processing_completed"
        success = True

    event = AuditEvent(
        event_type=event_type,
        success=success,
        case_id=str(document.case_id),
        user_id=str(run.started_by_user_id),
        analysis_run_id=str(run.id),
        related_object_type="document",
        related_object_id=str(document.id),
        related_document_id=str(document.id),
        input_summary={"run_type": run.run_type, "document_id": str(document.id)},
        output_summary={
            "document_status": validation["document_status"],
            "validation_status": validation["validation_status"],
            "issues": validation["issues"],
        },
        error_message=validation["error_message"],
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(event)


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


def _validate_pdf_upload(filename: str, content_type: str | None) -> None:
    if Path(filename).suffix.lower() != ".pdf":
        raise UnsupportedDocumentTypeError("Only .pdf import is supported for native PDF parsing")
    allowed_content_types = {None, "", "application/pdf", "application/octet-stream"}
    if content_type not in allowed_content_types:
        raise UnsupportedDocumentTypeError("Only application/pdf PDF import is supported")


def _is_pdf_upload(filename: str | None, content_type: str | None) -> bool:
    if filename is not None and Path(PurePath(filename).name).suffix.lower() == ".pdf":
        return True
    return content_type == "application/pdf"


def _write_pdf_import_audit(
    db: Session,
    user_id: UUID,
    document: DocumentModel,
    run_id: UUID,
    *,
    success: bool,
    page_count: int | None = None,
    quality_issues: list[dict] | None = None,
    error_message: str | None = None,
) -> None:
    if success and document.processing_status == "review_required":
        event_type = "document_processing_review_required"
    elif success:
        event_type = "document_parsing_completed"
    else:
        event_type = "document_processing_failed"

    event = AuditEvent(
        event_type=event_type,
        success=success,
        case_id=str(document.case_id),
        user_id=str(user_id),
        analysis_run_id=str(run_id),
        related_object_type="document",
        related_object_id=str(document.id),
        related_document_id=str(document.id),
        input_summary={
            "original_filename": document.original_filename,
            "mime_type": document.mime_type,
            "file_size_bytes": document.file_size_bytes,
        },
        output_summary={
            "document_id": str(document.id),
            "page_count": page_count,
            "parser_name": document.parser_name,
            "parser_version": document.parser_version,
            "document_status": document.processing_status,
            "quality_issues": quality_issues or [],
        },
        error_message=error_message,
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(event)


def _write_ocr_audit(
    db: Session,
    user_id: UUID,
    document: DocumentModel,
    run: AnalysisRunModel,
    result: OcrDocumentResult | None,
    success: bool,
    *,
    quality_issues: list[dict] | None = None,
    error_message: str | None = None,
) -> None:
    event = AuditEvent(
        event_type="document_ocr_completed" if success else "document_processing_failed",
        success=success,
        case_id=str(document.case_id),
        user_id=str(user_id),
        analysis_run_id=str(run.id),
        related_object_type="document",
        related_object_id=str(document.id),
        related_document_id=str(document.id),
        input_summary={
            "run_type": run.run_type,
            "document_id": str(document.id),
            "language": result.language if result is not None else None,
        },
        output_summary={
            "document_status": document.processing_status,
            "page_count": len(result.pages) if result is not None else None,
            "tool_name": result.tool_name if result is not None else "tesseract",
            "tool_version": result.tool_version if result is not None else None,
            "quality_issues": quality_issues or [],
        },
        error_message=error_message,
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(event)


async def _read_limited_upload(upload: UploadFile, max_upload_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total_size = 0
    while chunk := await upload.read(1024 * 1024):
        total_size += len(chunk)
        if total_size > max_upload_bytes:
            raise UploadTooLargeError(f"Upload exceeds configured size limit ({_format_size_limit(max_upload_bytes)})")
        chunks.append(chunk)
    if total_size == 0:
        raise UnsupportedDocumentTypeError("Empty files are not importable")
    return b"".join(chunks)


def _format_size_limit(byte_count: int) -> str:
    if byte_count < 1024 * 1024:
        return f"{byte_count} B"
    return f"{byte_count / (1024 * 1024):.1f}".rstrip("0").rstrip(".") + " MiB"


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
    for separator in ("\n\n",):
        break_at = text.rfind(separator, start, hard_end)
        if break_at >= min_soft_break:
            return break_at + len(separator)
    sentence_break = _find_sentence_break(text, start, hard_end, min_soft_break)
    if sentence_break is not None:
        return sentence_break
    for separator in ("\n", " "):
        break_at = text.rfind(separator, start, hard_end)
        if break_at >= min_soft_break:
            return break_at + len(separator)
    return hard_end


def _find_sentence_break(text: str, start: int, hard_end: int, min_soft_break: int) -> int | None:
    break_chars = {".", "!", "?", ":", ";", "…"}
    trailing_chars = {'"', "'", "”", "’", ")", "]", "}"}
    index = hard_end - 1
    while index >= min_soft_break:
        if text[index] in break_chars:
            break_at = index + 1
            while break_at < hard_end and text[break_at] in trailing_chars:
                break_at += 1
            if break_at < len(text) and not text[break_at].isspace():
                index -= 1
                continue
            return break_at
        index -= 1
    return None


def _trim_chunk_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end
