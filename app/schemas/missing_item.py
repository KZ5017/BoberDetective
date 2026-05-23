from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.review import HumanReviewRead


class MissingItemSourceCreate(BaseModel):
    source_reference_id: UUID
    relevance_rank: int = Field(default=0, ge=0)


class MissingItemCandidateCreate(BaseModel):
    missing_item_type: str = Field(pattern="^(attachment|video|expert_report|protocol|image|document_reference|other)$")
    referenced_item_text: str
    description: str
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    analysis_run_id: UUID
    sources: list[MissingItemSourceCreate] = Field(min_length=1)


class MissingItemCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    missing_item_type: str
    referenced_item_text: str
    description: str
    confidence: Decimal | None
    created_by_analysis_run_id: UUID
    source_validation_status: str
    review_status: str
    created_at: datetime
    updated_at: datetime


class MissingItemCandidateList(BaseModel):
    data: list[MissingItemCandidateRead]


class MissingItemCandidateSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    missing_item_candidate_id: UUID
    source_reference_id: UUID
    relevance_rank: int | None
    created_at: datetime


class MissingItemCandidateDetail(BaseModel):
    missing_item_candidate: MissingItemCandidateRead
    sources: list[MissingItemCandidateSourceRead]
    reviews: list[HumanReviewRead]


class MissingItemCandidateMergeCreate(BaseModel):
    target_missing_item_candidate_id: UUID
    review_comment: str | None = None


class MissingItemCandidateSourceDetachCreate(BaseModel):
    review_comment: str | None = None


class MissingItemCandidateSourceMoveCreate(BaseModel):
    target_missing_item_candidate_id: UUID
    review_comment: str | None = None
