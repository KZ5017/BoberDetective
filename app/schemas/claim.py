from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.review import HumanReviewRead


class ClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    claim_type: str
    claim_text: str
    claim_time_raw: str | None
    claim_time_normalized: datetime | None
    confidence: Decimal | None
    created_by_analysis_run_id: UUID
    source_validation_status: str
    review_status: str
    created_at: datetime
    updated_at: datetime


class ClaimList(BaseModel):
    data: list[ClaimRead]


class ClaimSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    claim_id: UUID
    source_reference_id: UUID
    relevance_rank: int | None
    support_type: str
    created_at: datetime


class ClaimDetail(BaseModel):
    claim: ClaimRead
    sources: list[ClaimSourceRead]
    reviews: list[HumanReviewRead]
