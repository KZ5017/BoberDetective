from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.review import HumanReviewRead


class ReviewReportFilters(BaseModel):
    object_types: list[str] | None = Field(default=None)
    review_statuses: list[str] | None = Field(default=None)
    source_validation_statuses: list[str] | None = Field(default=None)


class ReviewReportCounts(BaseModel):
    total: int
    needs_review: int
    verified: int
    rejected: int
    corrected: int
    new: int


class ReviewReportSource(BaseModel):
    source_reference_id: UUID
    document_id: UUID
    page_id: UUID | None
    chunk_id: UUID | None
    page_number: int | None
    citation_label: str | None
    quote_text: str
    source_kind: str
    support_type: str
    relevance_rank: int | None


class ReviewReportItem(BaseModel):
    object_type: str
    object_id: UUID
    title: str
    body_text: str | None
    subtype: str
    review_status: str
    source_validation_status: str
    created_by_analysis_run_id: UUID | None
    created_at: datetime
    updated_at: datetime
    sources: list[ReviewReportSource]
    reviews: list[HumanReviewRead]


class CaseReviewReport(BaseModel):
    case_id: UUID
    counts: ReviewReportCounts
    items: list[ReviewReportItem]
