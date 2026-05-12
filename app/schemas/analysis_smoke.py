from uuid import UUID

from pydantic import BaseModel, Field


class SourceCitedAnalysisSmokeRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)


class SmokeClaim(BaseModel):
    claim_id: UUID | None = None
    claim_text: str
    quote_text: str
    source_label: str
    source_reference_id: UUID | None = None


class SourceCitedAnalysisSmokeResponse(BaseModel):
    analysis_run_id: UUID
    model: str
    claims: list[SmokeClaim]
    unsupported_claims: list[str]
    selected_document_id: UUID | None
    selected_chunk_id: UUID | None
    validation_status: str
