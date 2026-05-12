from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.review import HumanReviewRead
from app.schemas.review_report import ReviewReportFilters


class ExportCreate(BaseModel):
    export_type: str = Field(default="json", pattern="^(json|html)$")
    export_scope: str = Field(default="review_report", pattern="^review_report$")
    review_filter: str = Field(default="all", pattern="^(all|verified_only|needs_review|rejected)$")
    require_source_valid: bool = True
    report_filters: ReviewReportFilters | None = None


class ExportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    export_type: str
    export_scope: str
    file_path: str
    sha256_hash: str | None
    generated_by_analysis_run_id: UUID | None
    exported_by_user_id: UUID
    review_filter: str | None
    export_parameters: dict | None
    created_at: datetime


class ExportList(BaseModel):
    data: list[ExportRead]


class ExportItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    export_id: UUID
    object_type: str
    object_id: UUID
    source_reference_id: UUID | None
    display_order: int | None
    created_at: datetime


class ExportDetail(BaseModel):
    export: ExportRead
    items: list[ExportItemRead]
    reviews: list[HumanReviewRead]
