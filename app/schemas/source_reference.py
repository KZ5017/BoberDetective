from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceReferenceCreate(BaseModel):
    document_id: UUID
    page_id: UUID | None = None
    chunk_id: UUID | None = None
    quote_text: str = Field(min_length=1, max_length=10000)
    quote_char_start: int | None = Field(default=None, ge=0)
    quote_char_end: int | None = Field(default=None, ge=0)
    citation_label: str | None = Field(default=None, max_length=500)
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    source_kind: str = Field(default="chunk_quote", pattern="^(page_quote|chunk_quote|document_metadata|manual_note)$")

    @model_validator(mode="after")
    def validate_offsets(self) -> "SourceReferenceCreate":
        if self.quote_char_start is not None and self.quote_char_end is not None:
            if self.quote_char_end < self.quote_char_start:
                raise ValueError("quote_char_end must be greater than or equal to quote_char_start")
        return self


class SourceReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    document_id: UUID
    page_id: UUID | None
    chunk_id: UUID | None
    page_number: int | None
    quote_text: str
    quote_char_start: int | None
    quote_char_end: int | None
    citation_label: str | None
    confidence: Decimal | None
    source_kind: str
    extraction_run_id: UUID | None
    created_by_user_id: UUID | None
    created_at: datetime


class SourceReferenceList(BaseModel):
    data: list[SourceReferenceRead]


class SourceReferenceValidateRequest(BaseModel):
    source_reference_ids: list[UUID] = Field(min_length=1, max_length=100)


class SourceReferenceValidationResult(BaseModel):
    source_reference_id: UUID
    is_valid: bool
    errors: list[str] = Field(default_factory=list)


class SourceReferenceValidateResponse(BaseModel):
    data: list[SourceReferenceValidationResult]
