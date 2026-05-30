from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.analysis import AnalysisRunRead


class DocumentOcrRecommendation(BaseModel):
    action: Literal["hidden", "recommended", "optional"]
    reason_code: str
    message: str


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    original_filename: str
    mime_type: str
    file_extension: str | None
    file_size_bytes: int
    sha256_hash: str
    language_code: str | None
    imported_by_user_id: UUID
    imported_at: datetime
    processing_status: str
    lifecycle_status: str
    lifecycle_status_changed_at: datetime | None = None
    lifecycle_status_changed_by_user_id: UUID | None = None
    lifecycle_status_reason: str | None = None
    page_count: int | None
    current_chunk_count: int = 0
    parser_name: str | None
    parser_version: str | None
    notes: str | None
    ocr_recommendation: DocumentOcrRecommendation | None = None


class DocumentList(BaseModel):
    data: list[DocumentRead]


class DocumentImportMetadata(BaseModel):
    language_code: str | None = Field(default="hu", max_length=16)
    notes: str | None = None


class DocumentLifecycleUpdateRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


def document_read_with_labels(document: object) -> DocumentRead:
    return DocumentRead.model_validate(document)


class DocumentProcessRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class DocumentChunkRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class DocumentProcessResponse(BaseModel):
    document: DocumentRead
    analysis_run: AnalysisRunRead


class DocumentOcrRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
    language: str | None = Field(default=None, max_length=64)


class DocumentPartialOcrAcceptRequest(BaseModel):
    ocr_run_id: UUID
    page_numbers: list[int] | None = None
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_page_numbers(self) -> "DocumentPartialOcrAcceptRequest":
        if self.page_numbers is not None:
            if not self.page_numbers:
                raise ValueError("page_numbers must not be empty when provided")
            if any(page_number < 1 for page_number in self.page_numbers):
                raise ValueError("page_numbers must contain positive page numbers")
            if len(set(self.page_numbers)) != len(self.page_numbers):
                raise ValueError("page_numbers must not contain duplicates")
            self.page_numbers = sorted(self.page_numbers)
        return self


class DocumentPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    document_id: UUID
    page_number: int
    extracted_text: str
    text_source: str
    ocr_used: bool
    ocr_confidence: float | None
    parser_name: str | None
    parser_version: str | None
    version_no: int
    is_current: bool
    text_char_count: int
    created_at: datetime


class DocumentPageList(BaseModel):
    data: list[DocumentPageRead]


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    document_id: UUID
    page_start: int
    page_end: int
    chunk_index: int
    chunk_text: str
    char_start: int | None
    char_end: int | None
    token_count: int | None
    chunking_strategy: str
    chunker_version: str
    embedding_provider: str | None
    embedding_model: str | None
    embedding_vector_id: str | None
    version_no: int
    is_current: bool
    created_at: datetime


class DocumentChunkList(BaseModel):
    data: list[DocumentChunkRead]
