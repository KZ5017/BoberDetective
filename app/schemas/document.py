from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.document_taxonomy import (
    default_document_taxonomy_codes,
    document_taxonomy_labels,
    validate_document_taxonomy,
)

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
    document_group_code: str
    document_group_label: str | None = None
    document_type_code: str
    document_type_label: str | None = None
    language_code: str | None
    imported_by_user_id: UUID
    imported_at: datetime
    processing_status: str
    page_count: int | None
    parser_name: str | None
    parser_version: str | None
    notes: str | None
    ocr_recommendation: DocumentOcrRecommendation | None = None


class DocumentList(BaseModel):
    data: list[DocumentRead]


class DocumentImportMetadata(BaseModel):
    document_group_code: str | None = Field(default=None, max_length=100)
    document_type_code: str | None = Field(default=None, max_length=100)
    language_code: str | None = Field(default="hu", max_length=16)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_taxonomy(self) -> "DocumentImportMetadata":
        default_group, default_type = default_document_taxonomy_codes()
        group_code = self.document_group_code or default_group
        type_code = self.document_type_code or default_type
        validate_document_taxonomy(group_code, type_code)
        self.document_group_code = group_code
        self.document_type_code = type_code
        return self


class DocumentTaxonomyUpdateRequest(BaseModel):
    document_group_code: str = Field(max_length=100)
    document_type_code: str = Field(max_length=100)
    comment: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_taxonomy(self) -> "DocumentTaxonomyUpdateRequest":
        validate_document_taxonomy(self.document_group_code, self.document_type_code)
        return self


def document_read_with_labels(document: object) -> DocumentRead:
    read = DocumentRead.model_validate(document)
    group_label, type_label = document_taxonomy_labels(read.document_group_code, read.document_type_code)
    return read.model_copy(update={"document_group_label": group_label, "document_type_label": type_label})


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
