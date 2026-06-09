from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.knowledge import (
    KnowledgeChunkPreview,
    KnowledgeDocumentDetailResponse,
    KnowledgeDocumentImportResponse,
    KnowledgeIndexRequest,
    KnowledgeIndexResponse,
    KnowledgeIndexStatusResponse,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
)
from app.services.knowledge_indexing import (
    KnowledgeIndexError,
    get_knowledge_index_status,
    index_knowledge_documents,
)
from app.services.knowledge_import import (
    DuplicateKnowledgeDocumentError,
    KnowledgeDocumentNotFoundError,
    KnowledgeImportError,
    KnowledgeLifecycleError,
    KnowledgeMarkdownParseError,
    KnowledgeUploadTooLargeError,
    UnsupportedKnowledgeDocumentTypeError,
    archive_knowledge_document,
    delete_knowledge_document,
    get_knowledge_document,
    import_knowledge_document,
    list_knowledge_documents,
    read_knowledge_chunks,
    restore_knowledge_document,
)
from app.services.knowledge_query import KnowledgeQueryValidationError, run_knowledge_query

router = APIRouter()


@router.get("/knowledge/documents", response_model=KnowledgeDocumentListResponse)
def get_knowledge_documents(db: Session = Depends(get_db)) -> KnowledgeDocumentListResponse:
    return KnowledgeDocumentListResponse(
        data=[KnowledgeDocumentResponse.model_validate(document) for document in list_knowledge_documents(db)]
    )


@router.post("/knowledge/documents", response_model=KnowledgeDocumentImportResponse, status_code=status.HTTP_201_CREATED)
async def post_knowledge_document(
    file: UploadFile = File(...),
    relative_path: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> KnowledgeDocumentImportResponse:
    try:
        document = await import_knowledge_document(db, file, relative_path=relative_path)
    except DuplicateKnowledgeDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except KnowledgeUploadTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except UnsupportedKnowledgeDocumentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    except KnowledgeMarkdownParseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except KnowledgeImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return KnowledgeDocumentImportResponse(
        document=KnowledgeDocumentResponse.model_validate(document),
        chunk_count=document.chunk_count,
        frontmatter_detected=bool(document.frontmatter_json),
        quality_flags=document.quality_flags_json,
    )


@router.get("/knowledge/documents/{knowledge_document_id}", response_model=KnowledgeDocumentDetailResponse)
def get_knowledge_document_detail(
    knowledge_document_id: UUID,
    db: Session = Depends(get_db),
) -> KnowledgeDocumentDetailResponse:
    try:
        document = get_knowledge_document(db, knowledge_document_id)
    except KnowledgeDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    chunks = [
        KnowledgeChunkPreview(
            chunk_index=chunk.chunk_index,
            heading_path=chunk.heading_path,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            contains_code_block=chunk.contains_code_block,
            code_languages=chunk.code_languages,
            quality_flags=chunk.quality_flags,
            text_preview=_preview(chunk.text),
        )
        for chunk in read_knowledge_chunks(document)
    ]
    return KnowledgeDocumentDetailResponse(
        document=KnowledgeDocumentResponse.model_validate(document),
        chunks=chunks,
    )


@router.post("/knowledge/documents/{knowledge_document_id}/archive", response_model=KnowledgeDocumentResponse)
def post_knowledge_document_archive(
    knowledge_document_id: UUID,
    db: Session = Depends(get_db),
) -> KnowledgeDocumentResponse:
    try:
        document = archive_knowledge_document(db, knowledge_document_id)
    except KnowledgeDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except KnowledgeIndexError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return KnowledgeDocumentResponse.model_validate(document)


@router.post("/knowledge/documents/{knowledge_document_id}/restore", response_model=KnowledgeDocumentResponse)
def post_knowledge_document_restore(
    knowledge_document_id: UUID,
    db: Session = Depends(get_db),
) -> KnowledgeDocumentResponse:
    try:
        document = restore_knowledge_document(db, knowledge_document_id)
    except KnowledgeDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return KnowledgeDocumentResponse.model_validate(document)


@router.delete("/knowledge/documents/{knowledge_document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_document_endpoint(
    knowledge_document_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_knowledge_document(db, knowledge_document_id)
    except KnowledgeDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except KnowledgeLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except KnowledgeIndexError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return None


@router.get("/knowledge/index/status", response_model=KnowledgeIndexStatusResponse)
def get_knowledge_index_status_endpoint(db: Session = Depends(get_db)) -> KnowledgeIndexStatusResponse:
    index_status = get_knowledge_index_status(db)
    return KnowledgeIndexStatusResponse(**index_status.__dict__)


@router.post("/knowledge/index", response_model=KnowledgeIndexResponse)
def post_knowledge_index(
    request: KnowledgeIndexRequest,
    db: Session = Depends(get_db),
) -> KnowledgeIndexResponse:
    try:
        result = index_knowledge_documents(db, request)
    except KnowledgeIndexError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return KnowledgeIndexResponse(**result.__dict__)


@router.post("/knowledge/query", response_model=KnowledgeQueryResponse)
def post_knowledge_query(
    payload: KnowledgeQueryRequest,
    db: Session = Depends(get_db),
) -> KnowledgeQueryResponse:
    try:
        return run_knowledge_query(db, payload)
    except KnowledgeQueryValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _preview(text: str, limit: int = 500) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"
