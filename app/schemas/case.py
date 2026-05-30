from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaseCreate(BaseModel):
    case_name: str = Field(min_length=1, max_length=300)
    case_reference: str | None = Field(default=None, max_length=200)
    description: str | None = None


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_reference: str | None
    case_name: str
    description: str | None
    status: str
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class CaseList(BaseModel):
    data: list[CaseRead]


class CaseDeleteResponse(BaseModel):
    case_id: UUID
    deleted_counts: dict[str, int]
    qdrant_collection: str
