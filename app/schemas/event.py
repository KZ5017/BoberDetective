from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.review import HumanReviewRead


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    event_type: str
    event_title: str
    event_description: str | None
    event_time_raw: str | None
    event_time_start: datetime | None
    event_time_end: datetime | None
    time_precision: str | None
    location_text: str | None
    confidence: Decimal | None
    created_by_analysis_run_id: UUID
    source_validation_status: str
    review_status: str
    created_at: datetime
    updated_at: datetime


class EventList(BaseModel):
    data: list[EventRead]


class EventSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    source_reference_id: UUID
    relevance_rank: int | None
    support_type: str
    created_at: datetime


class EventDetail(BaseModel):
    event: EventRead
    sources: list[EventSourceRead]
    reviews: list[HumanReviewRead]


class EventMergeCreate(BaseModel):
    target_event_id: UUID
    review_comment: str | None = None


class EventSourceDetachCreate(BaseModel):
    review_comment: str | None = None


class EventSourceMoveCreate(BaseModel):
    target_event_id: UUID
    review_comment: str | None = None
