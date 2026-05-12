from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.review import HumanReviewRead


class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    entity_type: str
    canonical_name: str
    normalized_value: str | None
    description: str | None
    confidence: Decimal | None
    created_by_analysis_run_id: UUID | None
    created_by_user_id: UUID | None
    review_status: str
    created_at: datetime
    updated_at: datetime


class EntityList(BaseModel):
    data: list[EntityRead]


class EntityMentionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    entity_id: UUID
    document_id: UUID
    page_id: UUID | None
    chunk_id: UUID | None
    page_number: int | None
    surface_text: str
    char_start: int | None
    char_end: int | None
    source_reference_id: UUID | None
    confidence: Decimal | None
    created_by_analysis_run_id: UUID | None
    created_at: datetime


class EntityDetail(BaseModel):
    entity: EntityRead
    mentions: list[EntityMentionRead]
    reviews: list[HumanReviewRead]
