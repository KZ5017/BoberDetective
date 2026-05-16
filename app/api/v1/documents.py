from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.document import DocumentModel
from app.schemas.analysis import AnalysisRunRead
from app.schemas.document import (
    DocumentChunkList,
    DocumentChunkRead,
    DocumentChunkRequest,
    DocumentImportMetadata,
    DocumentList,
    DocumentOcrRequest,
    DocumentPageList,
    DocumentPageRead,
    DocumentProcessRequest,
    DocumentProcessResponse,
    DocumentRead,
)
from app.services.documents import (
    CaseNotFoundError,
    DocumentImportError,
    DocumentNotFoundError,
    DocumentProcessingError,
    DuplicateDocumentError,
    PdfParserUnavailableError,
    PdfParsingError,
    UnsupportedDocumentTypeError,
    UploadTooLargeError,
    create_document_chunks,
    document_ocr_recommendation,
    import_document,
    list_document_chunks,
    list_document_pages,
    list_documents,
    ocr_document,
    process_document,
)

router = APIRouter()


@router.get("/cases/{case_id}/documents", response_model=DocumentList)
def get_documents(case_id: UUID, db: Session = Depends(get_db)) -> DocumentList:
    return DocumentList(data=[_document_read(db, document) for document in list_documents(db, case_id)])


@router.post("/cases/{case_id}/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def post_document(
    case_id: UUID,
    file: UploadFile = File(...),
    document_type: str | None = Form(default=None, max_length=200),
    language_code: str | None = Form(default="hu", max_length=16),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> DocumentRead:
    metadata = DocumentImportMetadata(document_type=document_type, language_code=language_code, notes=notes)
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
    return DocumentRead.model_validate(document).model_copy(
        update={"ocr_recommendation": document_ocr_recommendation(db, document)}
    )
