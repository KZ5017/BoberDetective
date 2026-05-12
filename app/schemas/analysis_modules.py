from uuid import UUID

from pydantic import BaseModel, Field


class AnalysisModuleRunRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)


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


class AnalysisModuleRunResponse(BaseModel):
    analysis_run_id: UUID
    module_key: str
    model: str
    claims: list[AnalysisModuleClaim]
    events: list[AnalysisModuleEvent] = []
    unsupported_items: list[str]
    selected_chunk_ids: list[UUID]
    validation_status: str
