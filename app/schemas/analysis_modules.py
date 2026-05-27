from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.document_taxonomy import validate_document_taxonomy


class AnalysisModuleRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(default=None, max_length=500)
    source_mode: Literal["case", "document"] = "case"
    document_id: UUID | None = None
    document_ids: list[UUID] = Field(default_factory=list)
    document_group_code: str | None = Field(default=None, max_length=100)
    document_type_code: str | None = Field(default=None, max_length=100)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    max_chunks: int = Field(default=30, ge=1, le=50)
    batch_size: int = Field(default=1, ge=1, le=15)
    claim_review_scope: Literal["reviewable", "verified", "needs_review", "all_source_valid"] = "reviewable"
    retrieval_strategy: Literal["keyword", "semantic", "hybrid"] = "keyword"
    contradiction_candidate_limit: int = Field(default=5, ge=1, le=10)

    @model_validator(mode="after")
    def validate_page_range(self) -> "AnalysisModuleRunRequest":
        if self.page_start is not None and self.page_end is not None and self.page_start > self.page_end:
            raise ValueError("page_start must be less than or equal to page_end")
        if self.document_type_code is not None and self.document_group_code is None:
            raise ValueError("document_group_code is required when document_type_code is provided")
        if self.document_group_code is not None and self.document_type_code is not None:
            validate_document_taxonomy(self.document_group_code, self.document_type_code)
        if self.source_mode == "document" and (self.document_ids or self.document_group_code or self.document_type_code):
            raise ValueError("document_ids and taxonomy filters are only supported in case source mode")
        if self.source_mode == "case" and (self.page_start is not None or self.page_end is not None):
            raise ValueError("page_start and page_end are only supported in document source mode")
        return self


class AnalysisModuleContradictionCandidate(BaseModel):
    contradiction_candidate_id: UUID
    contradiction_type: str
    title: str
    description: str
    claim_id_a: UUID | None
    claim_id_b: UUID | None
    event_id_a: UUID | None = None
    event_id_b: UUID | None = None
    severity_hint: str | None
    source_reference_ids: list[UUID]

class AnalysisModuleResearchFinding(BaseModel):
    research_finding_id: UUID
    title: str
    finding_text: str
    suggested_type: str
    suggested_type_reason: str | None
    relevance_reason: str
    llm_support_status: str
    quote_text: str
    source_label: str
    source_reference_id: UUID
    document_id: UUID
    chunk_id: UUID


class AnalysisModuleRunResponse(BaseModel):
    analysis_run_id: UUID
    module_key: str
    model: str
    contradiction_candidates: list[AnalysisModuleContradictionCandidate] = []
    research_findings: list[AnalysisModuleResearchFinding] = []
    unsupported_items: list[str]
    selected_chunk_ids: list[UUID]
    validation_status: str
