from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    document_ids: list[UUID] = Field(default_factory=list)
    document_type: str | None = Field(default=None, max_length=200)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)


class KeywordSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=20, ge=1, le=100)
    include_quotes: bool = True
    target: str = Field(default="chunks", pattern="^(chunks|pages|all)$")


class KeywordSearchResult(BaseModel):
    source_type: str
    document_id: UUID
    document_name: str
    page_id: UUID | None = None
    chunk_id: UUID | None = None
    page_start: int
    page_end: int
    chunk_index: int | None = None
    quote: str | None = None
    score: float
    match_type: str = "keyword"


class KeywordSearchResponse(BaseModel):
    data: list[KeywordSearchResult]


class ChunkIndexRequest(BaseModel):
    document_id: UUID | None = None
    limit: int = Field(default=200, ge=1, le=1000)
    force_reindex: bool = False


class ChunkIndexResponse(BaseModel):
    analysis_run_id: UUID
    indexed_count: int
    skipped_count: int
    collection_name: str
    embedding_model: str


class ChunkIndexJobResponse(BaseModel):
    analysis_run_id: UUID
    status: str
    collection_name: str
    embedding_model: str


class ChunkIndexStatusResponse(BaseModel):
    case_id: UUID
    document_id: UUID | None = None
    collection_name: str
    embedding_model: str
    current_chunk_count: int
    indexed_chunk_count: int
    missing_chunk_count: int
    is_ready: bool
    needs_indexing: bool
    latest_run_id: UUID | None = None
    latest_run_status: str | None = None
    latest_run_validation_status: str | None = None
    latest_run_started_at: datetime | None = None
    latest_run_finished_at: datetime | None = None
    latest_run_input_count: int = 0
    latest_run_output_count: int = 0
    latest_run_progress_percent: float | None = None


class HybridSearchRequest(KeywordSearchRequest):
    retrieval_strategy: str = Field(default="hybrid", pattern="^(keyword|semantic|hybrid)$")


class HybridSearchResponse(BaseModel):
    data: list[KeywordSearchResult]
