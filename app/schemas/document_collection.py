from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SourceScopeMode = Literal["case", "documents", "collections"]


class DocumentCollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    sort_order: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped


class DocumentCollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped


class DocumentCollectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    name: str
    description: str | None
    color: str | None
    sort_order: int
    document_count: int = 0
    active_document_count: int = 0
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class DocumentCollectionList(BaseModel):
    data: list[DocumentCollectionRead]


class DocumentCollectionMembershipChangeRequest(BaseModel):
    document_ids: list[UUID] = Field(min_length=1, max_length=5000)


class DocumentCollectionMembershipChangeResponse(BaseModel):
    collection_id: UUID
    requested_count: int
    added_count: int = 0
    removed_count: int = 0
    already_present_count: int = 0
    not_present_count: int = 0
    skipped_count: int = 0
    skipped_reasons: list[str] = Field(default_factory=list)
    active_document_count: int
    total_document_count: int


class DocumentCollectionScopeResolveRequest(BaseModel):
    source_mode: SourceScopeMode
    document_ids: list[UUID] = Field(default_factory=list, max_length=5000)
    collection_ids: list[UUID] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def validate_scope_fields(self) -> "DocumentCollectionScopeResolveRequest":
        if self.source_mode == "case":
            return self
        if self.source_mode == "documents" and not self.document_ids:
            raise ValueError("document_ids is required for documents source_mode")
        if self.source_mode == "collections" and not self.collection_ids:
            raise ValueError("collection_ids is required for collections source_mode")
        return self


class DocumentCollectionScopeResolveResponse(BaseModel):
    source_mode: SourceScopeMode
    requested_document_ids: list[UUID]
    requested_collection_ids: list[UUID]
    resolved_document_count: int
    active_document_count: int
    inactive_document_count: int
    duplicate_membership_count: int
    document_ids_preview: list[UUID]
    warnings: list[str] = Field(default_factory=list)
