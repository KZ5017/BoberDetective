from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FullDocumentProcessingProfileRead(BaseModel):
    key: str
    label: str
    description: str
    item_kinds: list[str]


class FullDocumentProcessingProfileList(BaseModel):
    data: list[FullDocumentProcessingProfileRead]


class DocumentProcessingItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    document_id: UUID
    analysis_run_id: UUID
    profile_key: str
    item_kind: str
    display_label: str
    short_description: str | None
    mentioned_forms_json: list[Any]
    source_supported_details_json: list[Any]
    relationships_json: list[Any]
    recommended_search_focus: str | None
    alternative_search_focuses_json: list[Any]
    source_evidence_json: list[Any]
    occurrence_status: str = "unique"
    work_status: str
    target_object_type: str | None
    target_object_id: UUID | None
    created_at: datetime
    updated_at: datetime


class DocumentProcessingItemList(BaseModel):
    data: list[DocumentProcessingItemRead]


class DocumentProcessingItemUpdateRequest(BaseModel):
    work_status: str = Field(pattern="^(active|set_aside|deleted)$")


class DocumentProcessingItemBulkDeleteRequest(BaseModel):
    item_ids: list[UUID]


class DocumentProcessingItemBulkDeleteResponse(BaseModel):
    deleted_count: int


class DocumentProcessingItemDetail(BaseModel):
    item: DocumentProcessingItemRead


class FullDocumentProcessingRunRequest(BaseModel):
    profile_key: str
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    question_text: str | None = Field(default=None, max_length=4000)


class FullDocumentAnswerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    document_id: UUID
    analysis_run_id: UUID
    profile_key: str
    question_text: str
    answer_text: str
    source_summary: str | None
    page_start: int
    page_end: int
    source_page_count: int
    source_character_count: int
    model_name: str | None
    prompt_template_name: str | None
    prompt_template_version: str | None
    answer_status: str
    created_at: datetime
    updated_at: datetime


class FullDocumentAnswerList(BaseModel):
    data: list[FullDocumentAnswerRead]


class FullDocumentProcessingRunResponse(BaseModel):
    analysis_run_id: UUID
    document_id: UUID
    profile_key: str
    created_item_count: int
    unsupported_count: int
    validation_status: str
    items: list[DocumentProcessingItemRead]
    unsupported_items: list[str]
    answer: FullDocumentAnswerRead | None = None
