from uuid import UUID

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
