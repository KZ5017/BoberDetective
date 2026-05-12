from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HumanReviewCreate(BaseModel):
    action_type: str = Field(pattern="^(mark_needs_review|verify|reject|comment)$")
    review_comment: str | None = None


class HumanReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    object_type: str
    object_id: UUID
    action_type: str
    previous_review_status: str | None
    new_review_status: str | None
    review_comment: str | None
    correction_patch_json: dict | None
    performed_by_user_id: UUID
    performed_at: datetime
