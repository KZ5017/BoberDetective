from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.review import HumanReviewRead


class ContradictionSourceCreate(BaseModel):
    source_reference_id: UUID
    side_label: str | None = Field(default=None, pattern="^(a|b|context)$")


class ContradictionCandidateCreate(BaseModel):
    contradiction_type: str = Field(pattern="^(time_conflict|location_conflict|identity_conflict|document_mismatch|amount_conflict|other)$")
    title: str
    description: str
    claim_id_a: UUID | None = None
    claim_id_b: UUID | None = None
    event_id_a: UUID | None = None
    event_id_b: UUID | None = None
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    severity_hint: str | None = Field(default=None, pattern="^(low|medium|high)$")
    analysis_run_id: UUID
    sources: list[ContradictionSourceCreate] = Field(min_length=2)

    @model_validator(mode="after")
    def require_comparison_pair(self) -> "ContradictionCandidateCreate":
        has_claim_pair = self.claim_id_a is not None and self.claim_id_b is not None
        has_event_pair = self.event_id_a is not None and self.event_id_b is not None
        if not has_claim_pair and not has_event_pair:
            raise ValueError("A claim pair or event pair is required")
        return self


class ManualContradictionCandidateCreate(BaseModel):
    claim_id_a: UUID
    claim_id_b: UUID
    contradiction_type: str = Field(default="other", pattern="^(time_conflict|location_conflict|identity_conflict|document_mismatch|amount_conflict|other)$")
    severity_hint: str | None = Field(default="low", pattern="^(low|medium|high)$")
    description: str = Field(min_length=3)

    @model_validator(mode="after")
    def reject_self_pair(self) -> "ManualContradictionCandidateCreate":
        if self.claim_id_a == self.claim_id_b:
            raise ValueError("Two different claims are required")
        return self


class ContradictionCandidateClaimDetachRequest(BaseModel):
    review_comment: str | None = Field(default=None, max_length=4000)


class ContradictionCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    contradiction_type: str
    title: str
    description: str
    claim_id_a: UUID | None
    claim_id_b: UUID | None
    event_id_a: UUID | None
    event_id_b: UUID | None
    confidence: Decimal | None
    severity_hint: str | None
    created_by_analysis_run_id: UUID
    source_validation_status: str
    review_status: str
    created_at: datetime
    updated_at: datetime


class ContradictionCandidateList(BaseModel):
    data: list[ContradictionCandidateRead]


class ContradictionCandidateSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contradiction_candidate_id: UUID
    source_reference_id: UUID
    side_label: str | None
    created_at: datetime


class ContradictionCandidateDetail(BaseModel):
    contradiction_candidate: ContradictionCandidateRead
    sources: list[ContradictionCandidateSourceRead]
    reviews: list[HumanReviewRead]
