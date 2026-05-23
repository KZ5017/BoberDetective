from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DetachedSourceItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    source_reference_id: UUID
    detached_from_object_type: str
    detached_from_object_id: UUID
    detached_from_source_link_id: UUID
    detached_from_source_link_type: str
    object_title_snapshot: str
    object_body_snapshot: str | None
    object_subtype_snapshot: str | None
    object_review_status_snapshot: str | None
    source_validation_status_snapshot: str | None
    source_snapshot_json: dict | None
    handling_status: str
    reattached_to_object_type: str | None
    reattached_to_object_id: UUID | None
    reattached_to_object_title_snapshot: str | None
    detach_comment: str | None
    detached_by_user_id: UUID
    detached_at: datetime
    updated_at: datetime


class DetachedSourceItemList(BaseModel):
    data: list[DetachedSourceItemRead]


class DetachedSourceAttachCreate(BaseModel):
    target_object_id: UUID
    review_comment: str | None = None

