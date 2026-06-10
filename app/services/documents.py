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
from app.models.audit import AuditEventModel
from app.models.case import CaseModel
from app.models.document import (
    DocumentChunkManifestModel,
    DocumentChunkModel,
    DocumentModel,
    DocumentPageModel,
    DocumentSearchEntryModel,
    DocumentTextLayerModel,
)
from app.models.source_reference import SourceReferenceModel
from app.schemas.document import DocumentImportMetadata
from app.schemas.document import DocumentOcrRecommendation
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
from app.services.lexical_index import (
    deactivate_document_search_entries,
    refresh_chunk_search_entries,
    refresh_page_search_entries,
)
from app.services.storage import StoragePaths
from app.services.text_store import (
    StoredChunkText,
    StoredPageText,
    read_page_text_from_store,
    read_pages_jsonl,
    write_chunks_jsonl,
    write_pages_jsonl,
)
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


class PartialOcrAcceptanceError(DocumentProcessingError):
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
    "retired_analysis_module",
    "detect_contradiction_candidates",
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

    db.execute(
        delete(DocumentSearchEntryModel).where(
            DocumentSearchEntryModel.case_id == case_id,
            DocumentSearchEntryModel.document_id == document.id,
        )
    )
    db.execute(
        delete(DocumentChunkManifestModel).where(
            DocumentChunkManifestModel.case_id == case_id,
            DocumentChunkManifestModel.document_id == document.id,
        )
    )
    db.execute(
        delete(DocumentTextLayerModel).where(
            DocumentTextLayerModel.case_id == case_id,
            DocumentTextLayerModel.document_id == document.id,
        )
    )
    if run_ids:
        db.execute(delete(AnalysisRunOutputModel).where(AnalysisRunOutputModel.analysis_run_id.in_(run_ids)))
        db.execute(delete(AnalysisRunInputModel).where(AnalysisRunInputModel.analysis_run_id.in_(run_ids)))
        db.query(AuditEventModel).filter(AuditEventModel.analysis_run_id.in_(run_ids)).update(
            {AuditEventModel.analysis_run_id: None},
            synchronize_session=False,
        )
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
            message="Van kinyert szoveg, de egyes oldalak uresek. Az OCR ellenorzes segithet teljesebb szovegreteget letrehozni, ha a nativ kinyeres hianyos.",
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

    chunk_count, chunk_texts = _create_chunks_from_pages(db, case_id, document, current_pages, run.id)
    current_chunks = _list_current_chunks(db, case_id, document_id)
    validation = _validate_current_document_processing(document, current_pages, current_chunks)
    text_layer = _get_current_text_layer(db, case_id, document.id)
    chunk_manifest = None
    if validation["run_status"] == "succeeded" and text_layer is not None:
        chunk_manifest = _persist_chunk_manifest(
            db,
            StoragePaths(get_settings().data_root),
            case_id,
            document,
            text_layer,
            current_chunks,
            chunk_texts,
            created_by_run_id=run.id,
        )
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
            "chunk_manifest_id": str(chunk_manifest.id) if chunk_manifest is not None else None,
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
        quality_issues = _ocr_quality_issues(result)
        quality_decision = _ocr_quality_decision(result, quality_issues)
        if quality_decision["decision"] != "passed":
            current_pages = _list_current_pages(db, case_id, document.id)
            ocr_candidate_storage_uri = None
            if quality_decision["decision"] == "partial":
                ocr_candidate_storage_uri = _write_ocr_candidate_pages(storage, case_id, document, run.id, result)
            document.page_count = len(current_pages) if current_pages else 0
            document.parser_name = result.tool_name if not current_pages else document.parser_name
            document.parser_version = result.tool_version if not current_pages else document.parser_version
            document.processing_status = document.processing_status if current_pages else "review_required"
            db.add(document)
            db.flush()
            _write_ocr_audit(db, user.id, document, run, result, True, quality_issues=quality_issues)
            finish_analysis_run(
                db,
                run,
                status="succeeded",
                validation_status="failed" if quality_decision["decision"] == "failed" else "warning",
                output_summary={
                    "document_id": str(document.id),
                    "document_status": document.processing_status,
                    "page_count": document.page_count,
                    "ocr_page_count": len(result.pages),
                    "chunk_count": 0,
                    "tool_name": result.tool_name,
                    "tool_version": result.tool_version,
                    "language": result.language,
                    "quality_issues": quality_issues,
                    "usable_page_numbers": quality_decision["usable_page_numbers"],
                    "failed_page_numbers": quality_decision["failed_page_numbers"],
                    "ocr_candidate_storage_uri": ocr_candidate_storage_uri,
                    "next_action": quality_decision["next_action"],
                    "text_layer_created": False,
                },
            )
            return run

        _deactivate_current_text_manifests(db, case_id, document.id)
        page_records, page_texts = _persist_ocr_pages(db, case_id, document, result, run.id)
        text_layer = _persist_text_layer_manifest(
            db,
            storage,
            case_id,
            document,
            page_records,
            page_texts,
            source_kind="ocr",
            parser_name=result.tool_name,
            parser_version=result.tool_version,
            language_code=result.language,
            created_by_run_id=run.id,
        )
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
                "text_layer_created": True,
                "text_layer_id": str(text_layer.id),
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


def accept_partial_ocr_text_layer(
    db: Session,
    case_id: UUID,
    document_id: UUID,
    ocr_run_id: UUID,
    *,
    page_numbers: list[int] | None = None,
    reason: str | None = None,
) -> AnalysisRunModel:
    storage = StoragePaths(get_settings().data_root)
    document = db.get(DocumentModel, document_id)
    if document is None or document.case_id != case_id:
        raise DocumentNotFoundError("Document not found")
    _ensure_active_document(document)

    ocr_run = db.get(AnalysisRunModel, ocr_run_id)
    if ocr_run is None or ocr_run.case_id != case_id or ocr_run.run_type != "ocr_document":
        raise PartialOcrAcceptanceError("OCR run not found for this case")
    if ocr_run.input_parameters is None or ocr_run.input_parameters.get("document_id") != str(document.id):
        raise PartialOcrAcceptanceError("OCR run does not belong to this document")

    candidate_path = _ocr_candidate_pages_path(storage, case_id, document.id, ocr_run.id)
    candidate_pages = read_pages_jsonl(candidate_path)
    selected_page_numbers = set(page_numbers or [page.page_number for page in candidate_pages if page.text.strip()])
    accepted_pages = [page for page in candidate_pages if page.page_number in selected_page_numbers and page.text.strip()]
    if not accepted_pages:
        raise PartialOcrAcceptanceError("No usable OCR pages were selected")

    run = start_analysis_run(
        db,
        case_id,
        "extract_pages",
        provider_type="local_pipeline",
        model_name="partial_ocr_acceptance",
        model_version="1",
        input_parameters={
            "document_id": str(document.id),
            "ocr_run_id": str(ocr_run.id),
            "reason": reason,
            "accepted_page_numbers": [page.page_number for page in accepted_pages],
        },
    )
    add_analysis_run_input(db, run.id, "document", 0, document_id=document.id)
    add_analysis_run_input(
        db,
        run.id,
        "filter",
        1,
        payload_json={
            "ocr_run_id": str(ocr_run.id),
            "accepted_page_numbers": [page.page_number for page in accepted_pages],
        },
    )

    previous_pages = _list_current_pages(db, case_id, document.id)
    previous_chunks = _list_current_chunks(db, case_id, document.id)
    _deactivate_current_text_manifests(db, case_id, document.id)
    for page in previous_pages:
        page.is_current = False
        db.add(page)
    for chunk in previous_chunks:
        chunk.is_current = False
        db.add(chunk)
    db.flush()

    next_page_version = _next_page_version(db, document.id)
    page_records: list[DocumentPageModel] = []
    page_texts: dict[UUID, str] = {}
    for output_position, accepted_page in enumerate(accepted_pages):
        page_record = DocumentPageModel(
            case_id=case_id,
            document_id=document.id,
            page_number=accepted_page.page_number,
            text_source="ocr",
            ocr_used=True,
            ocr_confidence=accepted_page.ocr_confidence,
            parser_name=ocr_run.model_name,
            parser_version=ocr_run.model_version,
            extraction_run_id=run.id,
            version_no=next_page_version,
            is_current=True,
            text_char_count=len(accepted_page.text),
        )
        db.add(page_record)
        db.flush()
        page_records.append(page_record)
        page_texts[page_record.id] = accepted_page.text
        add_analysis_run_output(db, run.id, "page", page_record.id, output_position)

    text_layer = _persist_text_layer_manifest(
        db,
        storage,
        case_id,
        document,
        page_records,
        page_texts,
        source_kind="ocr",
        parser_name=ocr_run.model_name,
        parser_version=ocr_run.model_version,
        language_code=(ocr_run.input_parameters or {}).get("language"),
        created_by_run_id=run.id,
    )
    document.page_count = max(page.page_number for page in page_records)
    document.parser_name = ocr_run.model_name
    document.parser_version = ocr_run.model_version
    document.processing_status = "text_review_required"
    db.add(document)
    db.flush()

    return finish_analysis_run(
        db,
        run,
        status="succeeded",
        validation_status="warning",
        output_summary={
            "document_id": str(document.id),
            "document_status": document.processing_status,
            "accepted_page_numbers": [page.page_number for page in accepted_pages],
            "text_layer_id": str(text_layer.id),
            "text_layer_created": True,
            "next_action": "review_text_layer_then_create_chunks",
        },
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
    page_texts = {page.id: extracted_text}

    text_chunks = _build_text_chunks(extracted_text)
    chunk_records: list[DocumentChunkModel] = []
    chunk_texts: dict[UUID, str] = {}
    for chunk_index, chunk in enumerate(text_chunks):
        chunk_record = DocumentChunkModel(
            case_id=case_id,
            document_id=document.id,
            page_start=1,
            page_end=1,
            chunk_index=chunk_index,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            token_count=None,
            chunking_strategy=CHUNKING_STRATEGY,
            chunker_version=CHUNKER_VERSION,
            version_no=1,
            is_current=True,
        )
        db.add(chunk_record)
        chunk_records.append(chunk_record)
        db.flush()
        chunk_texts[chunk_record.id] = chunk.text
    text_layer, chunk_manifest = _persist_text_store_manifests(
        db,
        storage,
        case_id,
        document,
        [page],
        chunk_records,
        page_texts,
        chunk_texts,
        source_kind="native_text",
        parser_name="txt_import",
        parser_version="1",
        language_code=metadata.language_code,
        created_by_run_id=None,
    )

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
            "chunk_count": len(text_chunks),
            "chunking_strategy": CHUNKING_STRATEGY,
            "chunker_version": CHUNKER_VERSION,
            "text_layer_id": str(text_layer.id),
            "chunk_manifest_id": str(chunk_manifest.id),
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
        quality_issues = _pdf_parse_quality_issues(parse_result.pages)
        db.add(run)
        if quality_issues:
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
                    "parsed_page_count": len(parse_result.pages),
                    "chunk_count": 0,
                    "parser_name": parse_result.parser_name,
                    "parser_version": parse_result.parser_version,
                    "parser_profile": parse_result.parser_profile,
                    "quality_issues": quality_issues,
                    "next_action": "run_ocr",
                    "text_layer_created": False,
                },
            )
            db.refresh(document)
            return document

        page_records, page_texts = _persist_parsed_pages(db, case_id, document, parse_result.pages, run.id, parse_result)
        text_layer = _persist_text_layer_manifest(
            db,
            storage,
            case_id,
            document,
            page_records,
            page_texts,
            source_kind="native_text",
            parser_name=parse_result.parser_name,
            parser_version=parse_result.parser_version,
            language_code=metadata.language_code,
            created_by_run_id=run.id,
        )
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
                "text_layer_created": True,
                "text_layer_id": str(text_layer.id),
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
                "text_layer_created": False,
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
) -> tuple[list[DocumentPageModel], dict[UUID, str]]:
    output_position = 0
    page_records: list[DocumentPageModel] = []
    page_texts: dict[UUID, str] = {}
    for page in pages:
        page_record = DocumentPageModel(
            case_id=case_id,
            document_id=document.id,
            page_number=page.page_number,
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
        page_records.append(page_record)
        page_texts[page_record.id] = page.text
        add_analysis_run_output(db, run_id, "page", page_record.id, output_position)
        output_position += 1
    return page_records, page_texts


def _persist_ocr_pages(
    db: Session,
    case_id: UUID,
    document: DocumentModel,
    result: OcrDocumentResult,
    run_id: UUID,
) -> tuple[list[DocumentPageModel], dict[UUID, str]]:
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
    page_records: list[DocumentPageModel] = []
    page_texts: dict[UUID, str] = {}
    for ocr_page in result.pages:
        page_record = DocumentPageModel(
            case_id=case_id,
            document_id=document.id,
            page_number=ocr_page.page_number,
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
        page_records.append(page_record)
        page_texts[page_record.id] = ocr_page.text
        add_analysis_run_output(db, run_id, "page", page_record.id, output_position)
        output_position += 1

    for page_number, previous_page in previous_page_by_number.items():
        if page_number in new_page_by_number:
            previous_page.superseded_by_id = new_page_by_number[page_number].id
            db.add(previous_page)
    db.flush()
    return page_records, page_texts


def _create_chunks_from_pages(
    db: Session,
    case_id: UUID,
    document: DocumentModel,
    pages: list[DocumentPageModel],
    run_id: UUID,
) -> tuple[int, dict[UUID, str]]:
    previous_chunks = _list_current_chunks(db, case_id, document.id)
    for chunk in previous_chunks:
        chunk.is_current = False
        db.add(chunk)
    db.flush()

    next_chunk_version = _next_chunk_version(db, document.id)
    output_position = 0
    next_chunk_index = 0
    chunk_texts: dict[UUID, str] = {}
    for page in pages:
        page_text = read_page_text_from_store(db, page)
        for chunk in _build_text_chunks(page_text):
            chunk_record = DocumentChunkModel(
                case_id=case_id,
                document_id=document.id,
                page_start=page.page_number,
                page_end=page.page_number,
                chunk_index=next_chunk_index,
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
            chunk_texts[chunk_record.id] = chunk.text
            add_analysis_run_output(db, run_id, "chunk", chunk_record.id, output_position)
            output_position += 1
            next_chunk_index += 1
    return next_chunk_index, chunk_texts


def _persist_text_store_manifests(
    db: Session,
    storage: StoragePaths,
    case_id: UUID,
    document: DocumentModel,
    pages: list[DocumentPageModel],
    chunks: list[DocumentChunkModel],
    page_texts: dict[UUID, str],
    chunk_texts: dict[UUID, str],
    *,
    source_kind: str,
    parser_name: str | None,
    parser_version: str | None,
    language_code: str | None,
    created_by_run_id: UUID | None,
) -> tuple[DocumentTextLayerModel, DocumentChunkManifestModel]:
    text_layer = _persist_text_layer_manifest(
        db,
        storage,
        case_id,
        document,
        pages,
        page_texts,
        source_kind=source_kind,
        parser_name=parser_name,
        parser_version=parser_version,
        language_code=language_code,
        created_by_run_id=created_by_run_id,
    )
    chunk_manifest = _persist_chunk_manifest(
        db,
        storage,
        case_id,
        document,
        text_layer,
        chunks,
        chunk_texts,
        created_by_run_id=created_by_run_id,
    )
    return text_layer, chunk_manifest


def _persist_text_layer_manifest(
    db: Session,
    storage: StoragePaths,
    case_id: UUID,
    document: DocumentModel,
    pages: list[DocumentPageModel],
    page_texts: dict[UUID, str],
    *,
    source_kind: str,
    parser_name: str | None,
    parser_version: str | None,
    language_code: str | None,
    created_by_run_id: UUID | None,
) -> DocumentTextLayerModel:
    text_layer_id = uuid4()
    text_layer_dir = storage.derived_dir(str(case_id), str(document.id)) / "text_layers" / str(text_layer_id)
    pages_path = text_layer_dir / "pages.jsonl"
    pages_result = write_pages_jsonl(
        pages_path,
        [
            StoredPageText(
                page_id=str(page.id),
                page_number=page.page_number,
                text=_required_text_store_text(page_texts, page.id, "page"),
                text_char_count=page.text_char_count,
            )
            for page in pages
        ],
    )

    text_layer = DocumentTextLayerModel(
        id=text_layer_id,
        case_id=case_id,
        document_id=document.id,
        source_kind=source_kind,
        parser_name=parser_name,
        parser_version=parser_version,
        language_code=language_code,
        page_count=len(pages),
        char_count=sum(page.text_char_count for page in pages),
        storage_uri=_storage_uri(storage, pages_result.path),
        manifest_hash=pages_result.manifest_hash,
        created_by_run_id=created_by_run_id,
        version_no=1,
        is_current=True,
    )
    db.add(text_layer)
    db.flush()
    refresh_page_search_entries(db, document, text_layer, pages)
    return text_layer


def _persist_chunk_manifest(
    db: Session,
    storage: StoragePaths,
    case_id: UUID,
    document: DocumentModel,
    text_layer: DocumentTextLayerModel,
    chunks: list[DocumentChunkModel],
    chunk_texts: dict[UUID, str],
    *,
    created_by_run_id: UUID | None,
) -> DocumentChunkManifestModel:
    chunk_manifest_id = uuid4()
    chunk_manifest_dir = storage.derived_dir(str(case_id), str(document.id)) / "chunk_manifests" / str(chunk_manifest_id)
    chunks_path = chunk_manifest_dir / "chunks.jsonl"
    chunks_result = write_chunks_jsonl(
        chunks_path,
        [
            StoredChunkText(
                chunk_id=str(chunk.id),
                chunk_index=chunk.chunk_index,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                text=_required_text_store_text(chunk_texts, chunk.id, "chunk"),
            )
            for chunk in chunks
        ],
    )
    chunk_manifest = DocumentChunkManifestModel(
        id=chunk_manifest_id,
        case_id=case_id,
        document_id=document.id,
        text_layer_id=text_layer.id,
        chunking_strategy=CHUNKING_STRATEGY,
        chunker_version=CHUNKER_VERSION,
        chunk_count=len(chunks),
        storage_uri=_storage_uri(storage, chunks_result.path),
        manifest_hash=chunks_result.manifest_hash,
        created_by_run_id=created_by_run_id,
        version_no=1,
        is_current=True,
    )
    db.add(chunk_manifest)
    db.flush()
    refresh_chunk_search_entries(db, document, chunk_manifest, chunks)
    return chunk_manifest


def _required_text_store_text(texts: dict[UUID, str], item_id: UUID, item_kind: str) -> str:
    try:
        return texts[item_id]
    except KeyError as exc:
        raise DocumentProcessingError(f"Missing text-store text for {item_kind} {item_id}") from exc


def _get_current_text_layer(
    db: Session,
    case_id: UUID,
    document_id: UUID,
) -> DocumentTextLayerModel | None:
    return db.execute(
        select(DocumentTextLayerModel)
        .where(
            DocumentTextLayerModel.case_id == case_id,
            DocumentTextLayerModel.document_id == document_id,
            DocumentTextLayerModel.is_current.is_(True),
        )
        .order_by(DocumentTextLayerModel.created_at.desc())
    ).scalars().first()


def _deactivate_current_text_manifests(db: Session, case_id: UUID, document_id: UUID) -> None:
    deactivate_document_search_entries(db, document_id)
    current_text_layers = db.execute(
        select(DocumentTextLayerModel).where(
            DocumentTextLayerModel.case_id == case_id,
            DocumentTextLayerModel.document_id == document_id,
            DocumentTextLayerModel.is_current.is_(True),
        )
    ).scalars()
    for text_layer in current_text_layers:
        text_layer.is_current = False
        db.add(text_layer)

    current_chunk_manifests = db.execute(
        select(DocumentChunkManifestModel).where(
            DocumentChunkManifestModel.case_id == case_id,
            DocumentChunkManifestModel.document_id == document_id,
            DocumentChunkManifestModel.is_current.is_(True),
        )
    ).scalars()
    for chunk_manifest in current_chunk_manifests:
        chunk_manifest.is_current = False
        db.add(chunk_manifest)
    db.flush()


def _write_ocr_candidate_pages(
    storage: StoragePaths,
    case_id: UUID,
    document: DocumentModel,
    ocr_run_id: UUID,
    result: OcrDocumentResult,
) -> str:
    path = _ocr_candidate_pages_path(storage, case_id, document.id, ocr_run_id)
    write_pages_jsonl(
        path,
        [
            StoredPageText(
                page_id=f"ocr:{ocr_run_id}:{page.page_number}",
                page_number=page.page_number,
                text=page.text,
                text_char_count=len(page.text),
                ocr_confidence=page.confidence,
            )
            for page in result.pages
        ],
    )
    return _storage_uri(storage, path)


def _ocr_candidate_pages_path(storage: StoragePaths, case_id: UUID, document_id: UUID, ocr_run_id: UUID) -> Path:
    return storage.derived_dir(str(case_id), str(document_id)) / "ocr_candidates" / str(ocr_run_id) / "pages.jsonl"


def _storage_uri(storage: StoragePaths, path: Path) -> str:
    return path.resolve().relative_to(storage.data_root).as_posix()


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


def _ocr_quality_decision(result: OcrDocumentResult, quality_issues: list[dict]) -> dict:
    usable_page_numbers = [page.page_number for page in result.pages if page.text.strip()]
    failed_page_numbers = [page.page_number for page in result.pages if not page.text.strip()]
    total_text_chars = sum(len(page.text.strip()) for page in result.pages)
    if not result.pages or total_text_chars == 0:
        return {
            "decision": "failed",
            "usable_page_numbers": usable_page_numbers,
            "failed_page_numbers": failed_page_numbers,
            "next_action": "discard_or_replace_document",
        }
    if quality_issues:
        return {
            "decision": "partial",
            "usable_page_numbers": usable_page_numbers,
            "failed_page_numbers": failed_page_numbers,
            "next_action": "review_partial_ocr_before_text_layer",
        }
    return {
        "decision": "passed",
        "usable_page_numbers": usable_page_numbers,
        "failed_page_numbers": failed_page_numbers,
        "next_action": "review_text_layer_then_create_chunks",
    }


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
    if len(set(page_numbers)) != len(page_numbers):
        issues.append({"code": "duplicate_pages", "severity": "error", "page_numbers": page_numbers})

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
