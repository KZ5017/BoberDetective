from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.review import HumanReviewRead


class SummaryItemCreate(BaseModel):
    summary_type: str = Field(pattern="^(case_overview|document_summary|timeline_summary|entity_summary|caution_note|other)$")
    title: str
    body_text: str
    source_reference_id: UUID
    analysis_run_id: UUID
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    support_type: str = Field(default="direct", pattern="^(direct|indirect|contextual)$")
    relevance_rank: int = Field(default=0, ge=0)


class SummaryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    summary_type: str
    title: str
    body_text: str
    confidence: Decimal | None
    created_by_analysis_run_id: UUID
    source_validation_status: str
    review_status: str
    created_at: datetime
    updated_at: datetime


class SummaryItemList(BaseModel):
    data: list[SummaryItemRead]


class SummaryItemSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    summary_item_id: UUID
    source_reference_id: UUID
    relevance_rank: int | None
    support_type: str
    created_at: datetime


class SummaryItemDetail(BaseModel):
    summary_item: SummaryItemRead
    sources: list[SummaryItemSourceRead]
    reviews: list[HumanReviewRead]
