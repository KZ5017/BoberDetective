from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.document import DocumentModel
from app.schemas.search import (
    ChunkIndexJobResponse,
    ChunkIndexRequest,
    ChunkIndexResponse,
    ChunkIndexStatusResponse,
    HybridSearchRequest,
    HybridSearchResponse,
    KeywordSearchRequest,
    KeywordSearchResponse,
    KeywordSearchResult,
)
from app.services.search import keyword_search
from app.services.vector_index import (
    VectorIndexError,
    execute_chunk_index_job,
    get_chunk_index_status,
    hybrid_chunk_search,
    index_case_chunks,
    semantic_chunk_search,
    start_chunk_index_job,
)

router = APIRouter()


@router.post("/cases/{case_id}/search/keyword", response_model=KeywordSearchResponse)
def post_keyword_search(
    case_id: UUID,
    payload: KeywordSearchRequest,
    db: Session = Depends(get_db),
) -> KeywordSearchResponse:
    hits = keyword_search(db, case_id, payload)
    return KeywordSearchResponse(data=[KeywordSearchResult(**hit.__dict__) for hit in hits])


@router.post("/cases/{case_id}/search/hybrid", response_model=HybridSearchResponse)
def post_hybrid_search(
    case_id: UUID,
    payload: HybridSearchRequest,
    db: Session = Depends(get_db),
) -> HybridSearchResponse:
    keyword_hits = keyword_search(db, case_id, KeywordSearchRequest(**payload.model_dump(exclude={"retrieval_strategy"})))
    if payload.retrieval_strategy == "keyword":
        hits = keyword_hits
    else:
        document_ids = _semantic_filter_document_ids(db, case_id, payload)
        try:
            hits = (
                semantic_chunk_search(
                    db,
                    case_id,
                    payload.query,
                    payload.limit,
                    document_ids=document_ids,
                    page_start=payload.filters.page_start,
                    page_end=payload.filters.page_end,
                )
                if payload.retrieval_strategy == "semantic"
                else hybrid_chunk_search(
                    db,
                    case_id,
                    payload.query,
                    keyword_hits,
                    payload.limit,
                    document_ids=document_ids,
                    page_start=payload.filters.page_start,
                    page_end=payload.filters.page_end,
                )
            )
        except VectorIndexError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return HybridSearchResponse(data=[KeywordSearchResult(**hit.__dict__) for hit in hits])


def _semantic_filter_document_ids(db: Session, case_id: UUID, payload: HybridSearchRequest) -> list[UUID] | None:
    filters = payload.filters
    stmt = select(DocumentModel.id).where(
        DocumentModel.case_id == case_id,
        DocumentModel.lifecycle_status == "active",
    )
    if filters.document_ids:
        stmt = stmt.where(DocumentModel.id.in_(filters.document_ids))
    return list(db.execute(stmt).scalars().all())


@router.post("/cases/{case_id}/indexes/chunks", response_model=ChunkIndexResponse)
def post_chunk_index(
    case_id: UUID,
    payload: ChunkIndexRequest,
    db: Session = Depends(get_db),
) -> ChunkIndexResponse:
    try:
        result = index_case_chunks(db, case_id, payload)
    except VectorIndexError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return ChunkIndexResponse(
        analysis_run_id=result.analysis_run_id,
        indexed_count=result.indexed_count,
        skipped_count=result.skipped_count,
        collection_name=result.collection_name,
        embedding_model=result.embedding_model,
    )


@router.post("/cases/{case_id}/indexes/chunks/jobs", response_model=ChunkIndexJobResponse)
def post_chunk_index_job(
    case_id: UUID,
    payload: ChunkIndexRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ChunkIndexJobResponse:
    try:
        result = start_chunk_index_job(db, case_id, payload)
    except VectorIndexError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    background_tasks.add_task(execute_chunk_index_job, result.analysis_run_id, case_id, payload)
    return ChunkIndexJobResponse(
        analysis_run_id=result.analysis_run_id,
        status=result.status,
        collection_name=result.collection_name,
        embedding_model=result.embedding_model,
    )


@router.get("/cases/{case_id}/indexes/chunks/status", response_model=ChunkIndexStatusResponse)
def get_chunk_index_status_endpoint(
    case_id: UUID,
    document_id: UUID | None = None,
    collection_id: UUID | None = None,
    document_ids: list[UUID] = Query(default_factory=list),
    db: Session = Depends(get_db),
) -> ChunkIndexStatusResponse:
    try:
        request = ChunkIndexRequest(
            document_id=document_id,
            collection_id=collection_id,
            document_ids=document_ids,
        )
        result = get_chunk_index_status(db, case_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ChunkIndexStatusResponse(**result.__dict__)
