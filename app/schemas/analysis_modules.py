from uuid import UUID
from typing import Literal

from pydantic import BaseModel, Field


class AnalysisModuleRunRequest(BaseModel):
    query: str | None = Field(default=None, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)
    source_mode: Literal["focused_query", "document", "case"] = "focused_query"
    document_id: UUID | None = None
    max_chunks: int = Field(default=50, ge=1, le=200)
    batch_size: int = Field(default=5, ge=1, le=10)
    claim_review_scope: Literal["reviewable", "verified", "needs_review", "all_source_valid"] = "reviewable"
    retrieval_strategy: Literal["keyword", "semantic", "hybrid"] = "keyword"


class AnalysisModuleClaim(BaseModel):
    claim_id: UUID
    claim_type: str
    claim_text: str
    quote_text: str
    source_label: str
    source_reference_id: UUID
    document_id: UUID
    chunk_id: UUID


class AnalysisModuleEvent(BaseModel):
    event_id: UUID
    event_type: str
    event_title: str
    event_description: str | None
    event_time_raw: str | None
    time_precision: str | None
    location_text: str | None
    quote_text: str
    source_label: str
    source_reference_id: UUID
    document_id: UUID
    chunk_id: UUID


class AnalysisModuleEntity(BaseModel):
    entity_id: UUID
    mention_id: UUID
    entity_type: str
    canonical_name: str
    normalized_value: str | None
    description: str | None
    surface_text: str
    quote_text: str
    source_label: str
    source_reference_id: UUID
    document_id: UUID
    chunk_id: UUID


class AnalysisModuleSummaryItem(BaseModel):
    summary_item_id: UUID
    summary_type: str
    title: str
    body_text: str
    quote_text: str
    source_label: str
    source_reference_id: UUID
    document_id: UUID
    chunk_id: UUID


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


class AnalysisModuleMissingItemCandidate(BaseModel):
    missing_item_candidate_id: UUID
    missing_item_type: str
    referenced_item_text: str
    description: str
    expected_document_type: str | None
    quote_text: str
    source_label: str
    source_reference_id: UUID
    document_id: UUID
    chunk_id: UUID


class AnalysisModuleRunResponse(BaseModel):
    analysis_run_id: UUID
    module_key: str
    model: str
    claims: list[AnalysisModuleClaim]
    events: list[AnalysisModuleEvent] = []
    entities: list[AnalysisModuleEntity] = []
    summary_items: list[AnalysisModuleSummaryItem] = []
    contradiction_candidates: list[AnalysisModuleContradictionCandidate] = []
    missing_item_candidates: list[AnalysisModuleMissingItemCandidate] = []
    unsupported_items: list[str]
    selected_chunk_ids: list[UUID]
    validation_status: str
