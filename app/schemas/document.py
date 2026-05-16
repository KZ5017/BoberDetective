from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
    document_type: str | None
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
    document_type: str | None = Field(default=None, max_length=200)
    language_code: str | None = Field(default="hu", max_length=16)
    notes: str | None = None


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
