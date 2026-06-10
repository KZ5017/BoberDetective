from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.knowledge import (
    KnowledgeDocumentBatchImportResponse,
    KnowledgeDocumentBatchImportSummary,
    KnowledgeDocumentBatchPreviewItem,
    KnowledgeDocumentBatchPreviewResponse,
    KnowledgeDocumentBatchPreviewSummary,
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
    KnowledgeDocumentNotFoundError,
    KnowledgeLifecycleError,
    archive_knowledge_document,
    delete_knowledge_document,
    import_knowledge_document_batch,
    list_knowledge_documents,
    preview_knowledge_document_batch,
    restore_knowledge_document,
)
from app.services.knowledge_query import KnowledgeQueryValidationError, run_knowledge_query

router = APIRouter()


@router.get("/knowledge/documents", response_model=KnowledgeDocumentListResponse)
def get_knowledge_documents(db: Session = Depends(get_db)) -> KnowledgeDocumentListResponse:
    return KnowledgeDocumentListResponse(
        data=[KnowledgeDocumentResponse.model_validate(document) for document in list_knowledge_documents(db)]
    )


@router.post("/knowledge/documents/batch/preview", response_model=KnowledgeDocumentBatchPreviewResponse)
async def post_knowledge_document_batch_preview(
    files: list[UploadFile] = File(...),
    relative_paths: list[str] | None = Form(default=None),
    client_file_ids: list[str] | None = Form(default=None),
    db: Session = Depends(get_db),
) -> KnowledgeDocumentBatchPreviewResponse:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one Markdown file is required")
    result = await preview_knowledge_document_batch(
        db,
        files,
        relative_paths=relative_paths,
        client_file_ids=client_file_ids,
    )
    return KnowledgeDocumentBatchPreviewResponse(
        items=[KnowledgeDocumentBatchPreviewItem(**item.__dict__) for item in result.items],
        summary=KnowledgeDocumentBatchPreviewSummary(**result.summary.__dict__),
    )


@router.post("/knowledge/documents/batch/import", response_model=KnowledgeDocumentBatchImportResponse)
async def post_knowledge_document_batch_import(
    files: list[UploadFile] = File(...),
    relative_paths: list[str] | None = Form(default=None),
    client_file_ids: list[str] | None = Form(default=None),
    decisions: list[str] | None = Form(default=None),
    db: Session = Depends(get_db),
) -> KnowledgeDocumentBatchImportResponse:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one Markdown file is required")
    result = await import_knowledge_document_batch(
        db,
        files,
        relative_paths=relative_paths,
        client_file_ids=client_file_ids,
        decisions=decisions,
    )
    return KnowledgeDocumentBatchImportResponse(
        summary=KnowledgeDocumentBatchImportSummary(**result.summary.__dict__),
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
