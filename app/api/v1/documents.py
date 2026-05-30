from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.document import DocumentChunkModel, DocumentModel
from app.schemas.analysis import AnalysisRunRead
from app.schemas.document import (
    DocumentChunkList,
    DocumentChunkRead,
    DocumentChunkRequest,
    DocumentImportMetadata,
    DocumentLifecycleUpdateRequest,
    DocumentList,
    DocumentOcrRequest,
    DocumentPageList,
    DocumentPageRead,
    DocumentPartialOcrAcceptRequest,
    DocumentProcessRequest,
    DocumentProcessResponse,
    DocumentRead,
    document_read_with_labels,
)
from app.services.documents import (
    CaseNotFoundError,
    DocumentImportError,
    DocumentLifecycleError,
    DocumentNotFoundError,
    DocumentProcessingError,
    DuplicateDocumentError,
    PartialOcrAcceptanceError,
    PdfParserUnavailableError,
    PdfParsingError,
    UnsupportedDocumentTypeError,
    UploadTooLargeError,
    accept_partial_ocr_text_layer,
    create_document_chunks,
    discard_document,
    document_ocr_recommendation,
    import_document,
    list_document_chunks,
    list_document_pages,
    list_documents,
    ocr_document,
    process_document,
    update_document_lifecycle_status,
)
from app.services.text_store import read_chunk_text_from_store, read_page_text_from_store

router = APIRouter()


@router.get("/cases/{case_id}/documents", response_model=DocumentList)
def get_documents(case_id: UUID, db: Session = Depends(get_db)) -> DocumentList:
    return DocumentList(data=[_document_read(db, document) for document in list_documents(db, case_id)])


@router.post("/cases/{case_id}/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def post_document(
    case_id: UUID,
    file: UploadFile = File(...),
    language_code: str | None = Form(default="hu", max_length=16),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> DocumentRead:
    try:
        metadata = DocumentImportMetadata(
            language_code=language_code,
            notes=notes,
        )
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    try:
        document = await import_document(db, case_id, file, metadata)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DuplicateDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    except PdfParserUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except PdfParsingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DocumentImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _document_read(db, document)


@router.post("/cases/{case_id}/documents/{document_id}/exclude", response_model=DocumentRead)
def post_document_exclude(
    case_id: UUID,
    document_id: UUID,
    payload: DocumentLifecycleUpdateRequest | None = None,
    db: Session = Depends(get_db),
) -> DocumentRead:
    return _lifecycle_response(db, case_id, document_id, "excluded", payload)


@router.post("/cases/{case_id}/documents/{document_id}/archive", response_model=DocumentRead)
def post_document_archive(
    case_id: UUID,
    document_id: UUID,
    payload: DocumentLifecycleUpdateRequest | None = None,
    db: Session = Depends(get_db),
) -> DocumentRead:
    return _lifecycle_response(db, case_id, document_id, "archived", payload)


@router.post("/cases/{case_id}/documents/{document_id}/restore", response_model=DocumentRead)
def post_document_restore(
    case_id: UUID,
    document_id: UUID,
    payload: DocumentLifecycleUpdateRequest | None = None,
    db: Session = Depends(get_db),
) -> DocumentRead:
    return _lifecycle_response(db, case_id, document_id, "active", payload)


@router.delete("/cases/{case_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    case_id: UUID,
    document_id: UUID,
    payload: DocumentLifecycleUpdateRequest | None = None,
    db: Session = Depends(get_db),
) -> None:
    try:
        discard_document(db, case_id, document_id, reason=payload.reason if payload else None)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return None


@router.post("/cases/{case_id}/documents/{document_id}/process", response_model=DocumentProcessResponse)
def post_document_process(
    case_id: UUID,
    document_id: UUID,
    payload: DocumentProcessRequest | None = None,
    db: Session = Depends(get_db),
) -> DocumentProcessResponse:
    try:
        run = process_document(db, case_id, document_id, reason=payload.reason if payload else None)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    document = db.get(DocumentModel, document_id)
    return DocumentProcessResponse(
        document=_document_read(db, document),
        analysis_run=AnalysisRunRead.model_validate(run),
    )


@router.post("/cases/{case_id}/documents/{document_id}/chunks", response_model=DocumentProcessResponse)
def post_document_chunks(
    case_id: UUID,
    document_id: UUID,
    payload: DocumentChunkRequest | None = None,
    db: Session = Depends(get_db),
) -> DocumentProcessResponse:
    try:
        run = create_document_chunks(db, case_id, document_id, reason=payload.reason if payload else None)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    document = db.get(DocumentModel, document_id)
    return DocumentProcessResponse(
        document=_document_read(db, document),
        analysis_run=AnalysisRunRead.model_validate(run),
    )


@router.post("/cases/{case_id}/documents/{document_id}/ocr", response_model=DocumentProcessResponse)
def post_document_ocr(
    case_id: UUID,
    document_id: UUID,
    payload: DocumentOcrRequest | None = None,
    db: Session = Depends(get_db),
) -> DocumentProcessResponse:
    try:
        run = ocr_document(
            db,
            case_id,
            document_id,
            reason=payload.reason if payload else None,
            language=payload.language if payload else None,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    document = db.get(DocumentModel, document_id)
    return DocumentProcessResponse(
        document=_document_read(db, document),
        analysis_run=AnalysisRunRead.model_validate(run),
    )


@router.post("/cases/{case_id}/documents/{document_id}/ocr/accept-partial", response_model=DocumentProcessResponse)
def post_document_accept_partial_ocr(
    case_id: UUID,
    document_id: UUID,
    payload: DocumentPartialOcrAcceptRequest,
    db: Session = Depends(get_db),
) -> DocumentProcessResponse:
    try:
        run = accept_partial_ocr_text_layer(
            db,
            case_id,
            document_id,
            payload.ocr_run_id,
            page_numbers=payload.page_numbers,
            reason=payload.reason,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PartialOcrAcceptanceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DocumentProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    document = db.get(DocumentModel, document_id)
    return DocumentProcessResponse(
        document=_document_read(db, document),
        analysis_run=AnalysisRunRead.model_validate(run),
    )


@router.get("/cases/{case_id}/documents/{document_id}/pages", response_model=DocumentPageList)
def get_document_pages(case_id: UUID, document_id: UUID, db: Session = Depends(get_db)) -> DocumentPageList:
    return DocumentPageList(
        data=[_page_read(db, page) for page in list_document_pages(db, case_id, document_id)]
    )


@router.get("/cases/{case_id}/documents/{document_id}/chunks", response_model=DocumentChunkList)
def get_document_chunks(case_id: UUID, document_id: UUID, db: Session = Depends(get_db)) -> DocumentChunkList:
    return DocumentChunkList(
        data=[_chunk_read(db, chunk) for chunk in list_document_chunks(db, case_id, document_id)]
    )


def _page_read(db: Session, page) -> DocumentPageRead:
    return DocumentPageRead(
        id=page.id,
        case_id=page.case_id,
        document_id=page.document_id,
        page_number=page.page_number,
        extracted_text=read_page_text_from_store(db, page),
        text_source=page.text_source,
        ocr_used=page.ocr_used,
        ocr_confidence=page.ocr_confidence,
        parser_name=page.parser_name,
        parser_version=page.parser_version,
        version_no=page.version_no,
        is_current=page.is_current,
        text_char_count=page.text_char_count,
        created_at=page.created_at,
    )


def _chunk_read(db: Session, chunk) -> DocumentChunkRead:
    return DocumentChunkRead(
        id=chunk.id,
        case_id=chunk.case_id,
        document_id=chunk.document_id,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        chunk_index=chunk.chunk_index,
        chunk_text=read_chunk_text_from_store(db, chunk),
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        token_count=chunk.token_count,
        chunking_strategy=chunk.chunking_strategy,
        chunker_version=chunk.chunker_version,
        embedding_provider=chunk.embedding_provider,
        embedding_model=chunk.embedding_model,
        embedding_vector_id=chunk.embedding_vector_id,
        version_no=chunk.version_no,
        is_current=chunk.is_current,
        created_at=chunk.created_at,
    )


def _document_read(db: Session, document: DocumentModel) -> DocumentRead:
    current_chunk_count = int(
        db.execute(
            select(func.count())
            .select_from(DocumentChunkModel)
            .where(
                DocumentChunkModel.document_id == document.id,
                DocumentChunkModel.is_current.is_(True),
            )
        ).scalar_one()
    )
    return document_read_with_labels(document).model_copy(
        update={
            "current_chunk_count": current_chunk_count,
            "ocr_recommendation": document_ocr_recommendation(db, document),
        }
    )


def _lifecycle_response(
    db: Session,
    case_id: UUID,
    document_id: UUID,
    target_status: str,
    payload: DocumentLifecycleUpdateRequest | None,
) -> DocumentRead:
    try:
        document = update_document_lifecycle_status(
            db,
            case_id,
            document_id,
            target_status,
            reason=payload.reason if payload else None,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _document_read(db, document)
