from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


RagSourceMode = Literal["case", "document", "collection"]
RagAnswerMode = Literal["short", "detailed"]
RagRetrievalStrategy = Literal["keyword", "semantic", "hybrid"]


class RagQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    source_mode: RagSourceMode = "case"
    document_id: UUID | None = None
    document_ids: list[UUID] = Field(default_factory=list)
    collection_id: UUID | None = None
    answer_mode: RagAnswerMode = "detailed"
    retrieval_strategy: RagRetrievalStrategy = "hybrid"
    max_chunks: int = Field(default=45, ge=1, le=90)
    include_sources: bool = True

    @model_validator(mode="after")
    def validate_source_scope(self) -> "RagQueryRequest":
        if self.source_mode == "document" and self.document_id is None:
            raise ValueError("document_id is required for document source mode")
        if self.source_mode != "document" and self.document_id is not None:
            raise ValueError("document_id is only allowed for document source mode")
        if self.source_mode != "case" and self.document_ids:
            raise ValueError("document_ids is only allowed for case source mode")
        if self.source_mode == "collection" and self.collection_id is None:
            raise ValueError("collection_id is required for collection source mode")
        if self.source_mode != "collection" and self.collection_id is not None:
            raise ValueError("collection_id is only allowed for collection source mode")
        return self


class RagSaveAnswerRequest(BaseModel):
    title: str | None = Field(default=None, max_length=240)
    note: str | None = Field(default=None, max_length=4000)


class RagUsedSource(BaseModel):
    document_id: UUID
    document_filename: str
    page_number: int | None = None
    chunk_id: UUID
    chunk_index: int
    quote_preview: str
    retrieval_score: float | None = None
    retrieval_match_type: str | None = None


class RagSourceScopeSummary(BaseModel):
    source_mode: RagSourceMode
    case_id: UUID
    document_id: UUID | None = None
    collection_id: UUID | None = None
    resolved_document_count: int
    resolved_chunk_count: int
    inactive_document_count: int = 0
    duplicate_membership_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class RagRetrievalMetadata(BaseModel):
    retrieval_strategy: RagRetrievalStrategy
    max_chunks: int
    selected_chunk_count: int
    document_answer_count: int = 0
    embedding_model: str | None = None
    collection_name: str | None = None


class RagAnswerPayload(BaseModel):
    answer_text: str = Field(min_length=1)
    source_summary: str = ""
    insufficient_source: bool
    answer_mode: RagAnswerMode


class RagQueryResponse(BaseModel):
    run_id: UUID
    answer: RagAnswerPayload
    source_scope: RagSourceScopeSummary
    used_sources: list[RagUsedSource]
    retrieval_metadata: RagRetrievalMetadata
    can_save: bool


class RagSaveAnswerResponse(BaseModel):
    answer_id: UUID
    run_id: UUID
    saved: bool


class RagLatestRunSummary(BaseModel):
    analysis_run_id: UUID
    status: str
    validation_status: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    question: str | None = None
    source_mode: RagSourceMode | None = None
    document_id: UUID | None = None
    collection_id: UUID | None = None
    answer_mode: RagAnswerMode | None = None
    retrieval_strategy: RagRetrievalStrategy | None = None
    max_chunks: int | None = None
    selected_chunk_count: int = 0
    document_answer_count: int = 0
    used_source_count: int = 0
    insufficient_source: bool | None = None
    saved_answer_id: UUID | None = None
    error_message: str | None = None


class RagLatestRunSummaryResponse(BaseModel):
    latest_run: RagLatestRunSummary | None = None


class RagSavedAnswerListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None
    question: str
    answer_mode: str
    source_mode: str
    source_label: str | None
    created_at: datetime
    used_source_count: int


class RagSavedAnswerList(BaseModel):
    data: list[RagSavedAnswerListItem]


class RagSavedAnswerDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    analysis_run_id: UUID
    title: str | None
    question: str
    answer_text: str
    source_summary: str
    answer_mode: str
    source_scope: dict
    used_sources: list
    retrieval_metadata: dict
    model_name: str | None
    note: str | None
    created_at: datetime
