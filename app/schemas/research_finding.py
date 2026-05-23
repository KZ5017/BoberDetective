from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.source_reference import SourceReferenceRead
from app.schemas.manual_entry import ManualObjectCreateResponse, ManualObjectFromSourceCreate


class ResearchFindingCreate(BaseModel):
    title: str = Field(min_length=1)
    finding_text: str = Field(min_length=1)
    suggested_type: str = Field(default="other", pattern="^(claim|event|entity|document_reference|other)$")
    suggested_type_reason: str | None = None
    relevance_reason: str = Field(min_length=1)
    source_reference_id: UUID
    analysis_run_id: UUID


class ResearchFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    analysis_run_id: UUID
    source_reference_id: UUID
    title: str
    finding_text: str
    suggested_type: str
    suggested_type_reason: str | None
    relevance_reason: str
    source_validation_status: str
    llm_support_status: str
    conversion_status: str
    target_object_type: str | None
    target_object_id: UUID | None
    created_at: datetime
    updated_at: datetime
    source_reference: SourceReferenceRead | None = None


class ResearchFindingList(BaseModel):
    data: list[ResearchFindingRead]


class ResearchFindingDetail(BaseModel):
    finding: ResearchFindingRead


class ResearchFindingConvertRequest(ManualObjectFromSourceCreate):
    pass


class ResearchFindingConvertResponse(ManualObjectCreateResponse):
    finding: ResearchFindingRead


class ResearchFindingSetAsideRequest(BaseModel):
    pass


class ResearchFindingBulkDeleteRequest(BaseModel):
    finding_ids: list[UUID] = Field(min_length=1, max_length=200)


class ResearchFindingBulkDeleteResponse(BaseModel):
    deleted_count: int
