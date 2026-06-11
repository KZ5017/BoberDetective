from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


KnowledgeDocumentKind = Literal["markdown_note"]
KnowledgeDocumentStatus = Literal["imported", "processed", "indexing", "indexed", "failed", "archived"]
KnowledgeBatchPreviewStatus = Literal["ready", "same_hash", "same_relative_path", "invalid"]
KnowledgeBatchImportAction = Literal["imported", "skipped", "replaced", "failed"]
KnowledgeBatchImportDecision = Literal["import", "skip", "replace", "keep_existing"]
KnowledgeAnswerMode = Literal["short", "detailed"]
KnowledgeRetrievalStrategy = Literal["keyword", "semantic", "hybrid"]


class KnowledgeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    relative_path: str | None
    mime_type: str
    file_extension: str
    file_size_bytes: int
    sha256_hash: str
    document_kind: str
    processing_status: str
    language_code: str | None
    parser_name: str | None
    parser_version: str | None
    chunk_count: int
    char_count: int
    embedding_provider: str | None = None
    embedding_model: str | None = None
    vector_collection: str | None = None
    indexed_chunk_count: int = 0
    indexed_at: datetime | None = None
    frontmatter_json: dict
    heading_summary_json: list
    quality_flags_json: list
    imported_at: datetime
    updated_at: datetime


class KnowledgeDocumentListResponse(BaseModel):
    data: list[KnowledgeDocumentResponse]


class KnowledgeDocumentBatchPreviewItem(BaseModel):
    client_file_id: str
    original_filename: str | None = None
    relative_directory: str | None = None
    resolved_relative_path: str | None = None
    sha256_hash: str | None = None
    status: KnowledgeBatchPreviewStatus
    conflict_type: str | None = None
    existing_document_id: UUID | None = None
    existing_original_filename: str | None = None
    existing_relative_path: str | None = None
    error: str | None = None


class KnowledgeDocumentBatchPreviewSummary(BaseModel):
    total: int
    ready: int
    same_hash: int
    same_relative_path: int
    invalid: int


class KnowledgeDocumentBatchPreviewResponse(BaseModel):
    items: list[KnowledgeDocumentBatchPreviewItem]
    summary: KnowledgeDocumentBatchPreviewSummary


class KnowledgeDocumentBatchImportSummary(BaseModel):
    total: int
    imported: int
    skipped: int
    replaced: int
    failed: int


class KnowledgeDocumentBatchImportResponse(BaseModel):
    summary: KnowledgeDocumentBatchImportSummary


class KnowledgeIndexRequest(BaseModel):
    document_ids: list[UUID] = Field(default_factory=list)
    force_reindex: bool = False
    limit: int = Field(default=1000, ge=1, le=10000)


class KnowledgeIndexResponse(BaseModel):
    indexed_document_count: int
    indexed_chunk_count: int
    skipped_document_count: int
    collection_name: str
    embedding_model: str


class KnowledgeIndexStatusResponse(BaseModel):
    collection_name: str
    embedding_model: str
    document_count: int
    chunk_count: int
    indexed_document_count: int
    indexed_chunk_count: int
    missing_document_count: int
    missing_chunk_count: int
    is_ready: bool
    needs_indexing: bool


class KnowledgeQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    document_ids: list[UUID] = Field(default_factory=list)
    answer_mode: KnowledgeAnswerMode = "detailed"
    retrieval_strategy: KnowledgeRetrievalStrategy = "hybrid"
    max_chunks: int = Field(default=30, ge=1, le=60)


class KnowledgeUsedSource(BaseModel):
    knowledge_document_id: UUID
    original_filename: str
    relative_path: str | None = None
    chunk_id: str
    chunk_index: int
    heading_path: str = ""
    quote_preview: str
    contains_code_block: bool = False
    code_languages: list[str] = Field(default_factory=list)
    retrieval_score: float | None = None
    retrieval_match_type: str | None = None


class KnowledgeChunkDetailResponse(BaseModel):
    knowledge_document_id: UUID
    original_filename: str
    relative_path: str | None = None
    chunk_id: str
    chunk_index: int
    heading_path: str = ""
    text: str
    contains_code_block: bool = False
    code_languages: list[str] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)


class KnowledgeRetrievalMetadata(BaseModel):
    retrieval_strategy: KnowledgeRetrievalStrategy
    max_chunks: int
    selected_chunk_count: int
    document_count: int
    embedding_model: str | None = None
    collection_name: str | None = None


class KnowledgeAnswerPayload(BaseModel):
    answer_text: str = Field(min_length=1)
    source_summary: str = ""
    insufficient_source: bool
    answer_mode: KnowledgeAnswerMode


class KnowledgeQueryResponse(BaseModel):
    answer: KnowledgeAnswerPayload
    used_sources: list[KnowledgeUsedSource]
    retrieval_metadata: KnowledgeRetrievalMetadata
    can_save: bool = False
