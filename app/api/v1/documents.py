from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.document import (
    DocumentChunkList,
    DocumentChunkRead,
    DocumentImportMetadata,
    DocumentList,
    DocumentPageList,
    DocumentPageRead,
    DocumentRead,
)
from app.services.documents import (
    CaseNotFoundError,
    DocumentImportError,
    DuplicateDocumentError,
    UnsupportedDocumentTypeError,
    UploadTooLargeError,
    import_txt_document,
    list_document_chunks,
    list_document_pages,
    list_documents,
)

router = APIRouter()


@router.get("/cases/{case_id}/documents", response_model=DocumentList)
def get_documents(case_id: UUID, db: Session = Depends(get_db)) -> DocumentList:
    return DocumentList(data=[DocumentRead.model_validate(document) for document in list_documents(db, case_id)])


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
        document = await import_txt_document(db, case_id, file, metadata)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DuplicateDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    except DocumentImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return DocumentRead.model_validate(document)


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
