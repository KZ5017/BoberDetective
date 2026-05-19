from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.document import DocumentModel
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
    DocumentProcessRequest,
    DocumentProcessResponse,
    DocumentRead,
    DocumentTaxonomyUpdateRequest,
    document_read_with_labels,
)
from app.services.documents import (
    CaseNotFoundError,
    DocumentImportError,
    DocumentNotFoundError,
    DocumentProcessingError,
    DocumentLifecycleError,
    DuplicateDocumentError,
    PdfParserUnavailableError,
    PdfParsingError,
    UnsupportedDocumentTypeError,
    UploadTooLargeError,
    create_document_chunks,
    discard_document,
    document_ocr_recommendation,
    import_document,
    list_document_chunks,
    list_document_pages,
    list_documents,
    ocr_document,
    process_document,
    update_document_taxonomy,
    update_document_lifecycle_status,
)

router = APIRouter()


@router.get("/cases/{case_id}/documents", response_model=DocumentList)
def get_documents(case_id: UUID, db: Session = Depends(get_db)) -> DocumentList:
    return DocumentList(data=[_document_read(db, document) for document in list_documents(db, case_id)])


@router.post("/cases/{case_id}/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def post_document(
    case_id: UUID,
    file: UploadFile = File(...),
    document_group_code: str | None = Form(default=None, max_length=100),
    document_type_code: str | None = Form(default=None, max_length=100),
    language_code: str | None = Form(default="hu", max_length=16),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> DocumentRead:
    try:
        metadata = DocumentImportMetadata(
            document_group_code=document_group_code,
            document_type_code=document_type_code,
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


@router.patch("/cases/{case_id}/documents/{document_id}/taxonomy", response_model=DocumentRead)
def patch_document_taxonomy(
    case_id: UUID,
    document_id: UUID,
    payload: DocumentTaxonomyUpdateRequest,
    db: Session = Depends(get_db),
) -> DocumentRead:
    try:
        document = update_document_taxonomy(db, case_id, document_id, payload)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
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


@router.get("/cases/{case_id}/documents/{document_id}/pages", response_model=DocumentPageList)
def get_document_pages(case_id: UUID, document_id: UUID, db: Session = Depends(get_db)) -> DocumentPageList:
    return DocumentPageList(
        data=[DocumentPageRead.model_validate(page) for page in list_document_pages(db, case_id, document_id)]
    )


@router.get("/cases/{case_id}/documents/{document_id}/chunks", response_model=DocumentChunkList)
def get_document_chunks(case_id: UUID, document_id: UUID, db: Session = Depends(get_db)) -> DocumentChunkList:
    return DocumentChunkList(
        data=[DocumentChunkRead.model_validate(chunk) for chunk in list_document_chunks(db, case_id, document_id)]
    )


def _document_read(db: Session, document: DocumentModel) -> DocumentRead:
    return document_read_with_labels(document).model_copy(
        update={"ocr_recommendation": document_ocr_recommendation(db, document)}
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
