from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field
from pydantic import model_validator

from app.core.document_taxonomy import validate_document_taxonomy


class SearchFilters(BaseModel):
    document_ids: list[UUID] = Field(default_factory=list)
    document_group_code: str | None = Field(default=None, max_length=100)
    document_type_code: str | None = Field(default=None, max_length=100)
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
    document_ids: list[UUID] = Field(default_factory=list)
    document_group_code: str | None = Field(default=None, max_length=100)
    document_type_code: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=200, ge=1, le=1000)
    force_reindex: bool = False

    @model_validator(mode="after")
    def validate_scope(self) -> "ChunkIndexRequest":
        if self.document_id is not None and (self.document_ids or self.document_group_code or self.document_type_code):
            raise ValueError("document_id cannot be combined with document_ids or taxonomy filters")
        if self.document_type_code is not None and self.document_group_code is None:
            raise ValueError("document_group_code is required when document_type_code is provided")
        if self.document_group_code is not None and self.document_type_code is not None:
            validate_document_taxonomy(self.document_group_code, self.document_type_code)
        return self


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
    document_ids: list[UUID] = Field(default_factory=list)
    document_group_code: str | None = None
    document_type_code: str | None = None
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
