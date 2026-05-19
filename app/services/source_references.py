from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import DocumentChunkModel, DocumentModel, DocumentPageModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.source_reference import SourceReferenceCreate
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.storage import StoragePaths
from app.services.users import get_or_create_dev_user


class SourceReferenceError(ValueError):
    pass


class SourceReferenceNotFoundError(SourceReferenceError):
    pass


class SourceReferenceValidationError(SourceReferenceError):
    pass


@dataclass(frozen=True)
class SourceReferenceValidation:
    source_reference_id: UUID
    is_valid: bool
    errors: list[str]


def list_source_references(db: Session, case_id: UUID) -> list[SourceReferenceModel]:
    return list(
        db.execute(
            select(SourceReferenceModel)
            .where(SourceReferenceModel.case_id == case_id)
            .order_by(SourceReferenceModel.created_at.desc())
        ).scalars()
    )


def get_source_reference(db: Session, case_id: UUID, source_reference_id: UUID) -> SourceReferenceModel:
    source_reference = db.get(SourceReferenceModel, source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise SourceReferenceNotFoundError("Source reference not found")
    return source_reference


def create_source_reference(db: Session, case_id: UUID, payload: SourceReferenceCreate) -> SourceReferenceModel:
    return create_source_reference_for_run(db, case_id, payload, extraction_run_id=None)


def create_source_reference_for_run(
    db: Session,
    case_id: UUID,
    payload: SourceReferenceCreate,
    extraction_run_id: UUID | None = None,
) -> SourceReferenceModel:
    document = _get_case_document(db, case_id, payload.document_id)
    page = _get_case_page(db, case_id, payload.page_id, payload.document_id)
    chunk = _get_case_chunk(db, case_id, payload.chunk_id, payload.document_id)
    _validate_source_kind(payload, page, chunk)

    quote_char_start = payload.quote_char_start
    quote_char_end = payload.quote_char_end
    page_number = page.page_number if page is not None else None

    source_text = None
    if payload.source_kind == "chunk_quote":
        source_text = chunk.chunk_text if chunk is not None else None
        page_number = chunk.page_start if chunk is not None else page_number
    elif payload.source_kind == "page_quote":
        source_text = page.extracted_text if page is not None else None

    if source_text is not None:
        quote_char_start, quote_char_end = _resolve_quote_span(
            source_text,
            payload.quote_text,
            quote_char_start,
            quote_char_end,
        )

    user = get_or_create_dev_user(db)
    source_reference = SourceReferenceModel(
        case_id=case_id,
        document_id=document.id,
        page_id=page.id if page is not None else None,
        chunk_id=chunk.id if chunk is not None else None,
        page_number=page_number,
        quote_text=payload.quote_text,
        quote_char_start=quote_char_start,
        quote_char_end=quote_char_end,
        citation_label=payload.citation_label or _make_citation_label(document, page_number, chunk),
        confidence=payload.confidence,
        source_kind=payload.source_kind,
        extraction_run_id=extraction_run_id,
        created_by_user_id=user.id,
    )
    db.add(source_reference)
    db.flush()

    event = AuditEvent(
        event_type="source_reference_created",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        analysis_run_id=str(extraction_run_id) if extraction_run_id is not None else None,
        related_object_type="source_reference",
        related_object_id=str(source_reference.id),
        related_document_id=str(document.id),
        related_page_id=str(page.id) if page is not None else None,
        related_chunk_id=str(chunk.id) if chunk is not None else None,
        input_summary={"source_kind": payload.source_kind, "quote_length": len(payload.quote_text)},
        output_summary={"source_reference_id": str(source_reference.id), "citation_label": source_reference.citation_label},
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(event)
    db.commit()
    db.refresh(source_reference)
    return source_reference


def validate_source_references(
    db: Session,
    case_id: UUID,
    source_reference_ids: list[UUID],
) -> list[SourceReferenceValidation]:
    validations: list[SourceReferenceValidation] = []
    for source_reference_id in source_reference_ids:
        source_reference = db.get(SourceReferenceModel, source_reference_id)
        if source_reference is None or source_reference.case_id != case_id:
            validations.append(SourceReferenceValidation(source_reference_id, False, ["source_reference_not_found"]))
            continue
        validations.append(_validate_existing_source_reference(db, source_reference))
    return validations


def source_reference_document_is_active(
    db: Session,
    case_id: UUID,
    source_reference: SourceReferenceModel,
) -> bool:
    document = db.get(DocumentModel, source_reference.document_id)
    return document is not None and document.case_id == case_id and document.lifecycle_status == "active"


def ensure_source_reference_document_is_active(
    db: Session,
    case_id: UUID,
    source_reference: SourceReferenceModel,
    error_type: type[ValueError] = SourceReferenceValidationError,
) -> None:
    if not source_reference_document_is_active(db, case_id, source_reference):
        raise error_type("Source reference document is not active")


def _get_case_document(db: Session, case_id: UUID, document_id: UUID) -> DocumentModel:
    document = db.get(DocumentModel, document_id)
    if document is None or document.case_id != case_id:
        raise SourceReferenceValidationError("Document not found in this case")
    if document.lifecycle_status != "active":
        raise SourceReferenceValidationError("Document is not active")
    return document


def _get_case_page(
    db: Session,
    case_id: UUID,
    page_id: UUID | None,
    document_id: UUID,
) -> DocumentPageModel | None:
    if page_id is None:
        return None
    page = db.get(DocumentPageModel, page_id)
    if page is None or page.case_id != case_id or page.document_id != document_id:
        raise SourceReferenceValidationError("Page not found for this document and case")
    return page


def _get_case_chunk(
    db: Session,
    case_id: UUID,
    chunk_id: UUID | None,
    document_id: UUID,
) -> DocumentChunkModel | None:
    if chunk_id is None:
        return None
    chunk = db.get(DocumentChunkModel, chunk_id)
    if chunk is None or chunk.case_id != case_id or chunk.document_id != document_id:
        raise SourceReferenceValidationError("Chunk not found for this document and case")
    return chunk


def _validate_source_kind(
    payload: SourceReferenceCreate,
    page: DocumentPageModel | None,
    chunk: DocumentChunkModel | None,
) -> None:
    if payload.source_kind == "page_quote" and page is None:
        raise SourceReferenceValidationError("page_quote requires page_id")
    if payload.source_kind == "chunk_quote" and chunk is None:
        raise SourceReferenceValidationError("chunk_quote requires chunk_id")
    if payload.source_kind != "document_metadata" and page is None and chunk is None:
        raise SourceReferenceValidationError("Source reference requires page_id or chunk_id")


def _resolve_quote_span(
    source_text: str,
    quote_text: str,
    quote_char_start: int | None,
    quote_char_end: int | None,
) -> tuple[int, int]:
    if quote_char_start is not None or quote_char_end is not None:
        if quote_char_start is None or quote_char_end is None:
            raise SourceReferenceValidationError("Both quote_char_start and quote_char_end are required together")
        if source_text[quote_char_start:quote_char_end] != quote_text:
            raise SourceReferenceValidationError("Quote span does not match source text")
        return quote_char_start, quote_char_end

    found_at = source_text.find(quote_text)
    if found_at < 0:
        raise SourceReferenceValidationError("Quote text was not found in the referenced source text")
    return found_at, found_at + len(quote_text)


def _validate_existing_source_reference(
    db: Session,
    source_reference: SourceReferenceModel,
) -> SourceReferenceValidation:
    errors: list[str] = []
    if db.get(DocumentModel, source_reference.document_id) is None:
        errors.append("document_not_found")
    if source_reference.source_kind == "page_quote":
        page = db.get(DocumentPageModel, source_reference.page_id) if source_reference.page_id else None
        if page is None:
            errors.append("page_not_found")
        else:
            errors.extend(_quote_errors(page.extracted_text, source_reference))
    if source_reference.source_kind == "chunk_quote":
        chunk = db.get(DocumentChunkModel, source_reference.chunk_id) if source_reference.chunk_id else None
        if chunk is None:
            errors.append("chunk_not_found")
        else:
            errors.extend(_quote_errors(chunk.chunk_text, source_reference))
    if source_reference.source_kind != "document_metadata" and source_reference.page_id is None and source_reference.chunk_id is None:
        errors.append("source_location_missing")
    return SourceReferenceValidation(source_reference.id, len(errors) == 0, errors)


def _quote_errors(source_text: str, source_reference: SourceReferenceModel) -> list[str]:
    try:
        _resolve_quote_span(
            source_text,
            source_reference.quote_text,
            source_reference.quote_char_start,
            source_reference.quote_char_end,
        )
    except SourceReferenceValidationError as exc:
        return [str(exc)]
    return []


def _make_citation_label(
    document: DocumentModel,
    page_number: int | None,
    chunk: DocumentChunkModel | None,
) -> str:
    parts = [document.original_filename]
    if page_number is not None:
        parts.append(f"p. {page_number}")
    if chunk is not None:
        parts.append(f"chunk {chunk.chunk_index}")
    return ", ".join(parts)
