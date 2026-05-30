from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentModel(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("file_size_bytes > 0", name="ck_documents_file_size_positive"),
        CheckConstraint("sha256_hash ~ '^[0-9a-f]{64}$'", name="ck_documents_sha256_hash_hex"),
        CheckConstraint("page_count is null or page_count >= 0", name="ck_documents_page_count_non_negative"),
        CheckConstraint(
            "processing_status in ('pending', 'processing', 'processed', 'failed', 'review_required', 'text_review_required')",
            name="ck_documents_processing_status",
        ),
        CheckConstraint(
            "lifecycle_status in ('active', 'excluded', 'archived')",
            name="ck_documents_lifecycle_status",
        ),
        UniqueConstraint("case_id", "sha256_hash", name="uq_documents_case_sha256_hash"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_extension: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(Text, nullable=False)
    import_batch_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    language_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_encrypted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    imported_by_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    processing_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    lifecycle_status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    lifecycle_status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lifecycle_status_changed_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    lifecycle_status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parser_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    case = relationship("CaseModel")
    imported_by = relationship("UserModel", foreign_keys=[imported_by_user_id])
    lifecycle_status_changed_by = relationship("UserModel", foreign_keys=[lifecycle_status_changed_by_user_id])


class DocumentPageModel(Base):
    __tablename__ = "document_pages"
    __table_args__ = (
        CheckConstraint("page_number >= 1", name="ck_document_pages_page_number_positive"),
        CheckConstraint("version_no >= 1", name="ck_document_pages_version_no_positive"),
        CheckConstraint("text_char_count >= 0", name="ck_document_pages_text_char_count_non_negative"),
        CheckConstraint(
            "ocr_confidence is null or (ocr_confidence >= 0 and ocr_confidence <= 1)",
            name="ck_document_pages_ocr_confidence_range",
        ),
        CheckConstraint("text_source in ('native', 'ocr', 'mixed', 'manual')", name="ck_document_pages_text_source"),
        UniqueConstraint("document_id", "page_number", "version_no", name="uq_document_pages_document_page_version"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text_source: Mapped[str] = mapped_column(Text, nullable=False)
    ocr_used: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ocr_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    parser_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    superseded_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_pages.id"), nullable=True)
    text_char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    case = relationship("CaseModel")
    document = relationship("DocumentModel")
    superseded_by = relationship("DocumentPageModel", remote_side=[id])


class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint("page_start >= 1", name="ck_document_chunks_page_start_positive"),
        CheckConstraint("page_end >= page_start", name="ck_document_chunks_page_end_after_start"),
        CheckConstraint("chunk_index >= 0", name="ck_document_chunks_chunk_index_non_negative"),
        CheckConstraint("version_no >= 1", name="ck_document_chunks_version_no_positive"),
        CheckConstraint("token_count is null or token_count >= 0", name="ck_document_chunks_token_count_non_negative"),
        CheckConstraint(
            "char_end is null or char_start is null or char_end >= char_start",
            name="ck_document_chunks_char_end_after_start",
        ),
        UniqueConstraint(
            "document_id",
            "chunk_index",
            "chunker_version",
            "version_no",
            name="uq_document_chunks_document_index_chunker_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunking_strategy: Mapped[str] = mapped_column(Text, nullable=False)
    chunker_version: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_vector_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    superseded_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_chunks.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    case = relationship("CaseModel")
    document = relationship("DocumentModel")
    superseded_by = relationship("DocumentChunkModel", remote_side=[id])


class DocumentTextLayerModel(Base):
    __tablename__ = "document_text_layers"
    __table_args__ = (
        CheckConstraint("source_kind in ('native_text', 'ocr', 'manual')", name="ck_document_text_layers_source_kind"),
        CheckConstraint("page_count >= 0", name="ck_document_text_layers_page_count_non_negative"),
        CheckConstraint("char_count >= 0", name="ck_document_text_layers_char_count_non_negative"),
        CheckConstraint("version_no >= 1", name="ck_document_text_layers_version_no_positive"),
        CheckConstraint("manifest_hash ~ '^[0-9a-f]{64}$'", name="ck_document_text_layers_manifest_hash_hex"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    parser_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    language_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    case = relationship("CaseModel")
    document = relationship("DocumentModel")
    created_by_run = relationship("AnalysisRunModel")


class DocumentChunkManifestModel(Base):
    __tablename__ = "document_chunk_manifests"
    __table_args__ = (
        CheckConstraint("chunk_count >= 0", name="ck_document_chunk_manifests_chunk_count_non_negative"),
        CheckConstraint("version_no >= 1", name="ck_document_chunk_manifests_version_no_positive"),
        CheckConstraint("manifest_hash ~ '^[0-9a-f]{64}$'", name="ck_document_chunk_manifests_manifest_hash_hex"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    text_layer_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_text_layers.id"), nullable=False)
    chunking_strategy: Mapped[str] = mapped_column(Text, nullable=False)
    chunker_version: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    case = relationship("CaseModel")
    document = relationship("DocumentModel")
    text_layer = relationship("DocumentTextLayerModel")
    created_by_run = relationship("AnalysisRunModel")


class DocumentSearchEntryModel(Base):
    __tablename__ = "document_search_entries"
    __table_args__ = (
        CheckConstraint("source_type in ('page', 'chunk')", name="ck_document_search_entries_source_type"),
        CheckConstraint("page_start >= 1", name="ck_document_search_entries_page_start_positive"),
        CheckConstraint("page_end >= page_start", name="ck_document_search_entries_page_end_after_start"),
        CheckConstraint("chunk_index is null or chunk_index >= 0", name="ck_document_search_entries_chunk_index_non_negative"),
        CheckConstraint("text_hash ~ '^[0-9a-f]{64}$'", name="ck_document_search_entries_text_hash_hex"),
        CheckConstraint(
            "lifecycle_status in ('active', 'excluded', 'archived')",
            name="ck_document_search_entries_lifecycle_status",
        ),
        CheckConstraint(
            "(source_type = 'page' and page_id is not null and chunk_id is null) "
            "or (source_type = 'chunk' and chunk_id is not null and page_id is null)",
            name="ck_document_search_entries_source_link",
        ),
        Index(
            "ix_document_search_entries_vector",
            "search_vector",
            postgresql_using="gin",
        ),
        Index("ix_document_search_entries_case_source_current", "case_id", "source_type", "is_current"),
        Index("ix_document_search_entries_case_document_current", "case_id", "document_id", "is_current"),
        Index("ix_document_search_entries_page_range", "case_id", "page_start", "page_end"),
        Index(
            "uq_document_search_entries_current_page",
            "page_id",
            unique=True,
            postgresql_where=text("source_type = 'page' AND is_current = true"),
        ),
        Index(
            "uq_document_search_entries_current_chunk",
            "chunk_id",
            unique=True,
            postgresql_where=text("source_type = 'chunk' AND is_current = true"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    page_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_pages.id"), nullable=True)
    chunk_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_chunks.id"), nullable=True)
    text_layer_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_text_layers.id"), nullable=True)
    chunk_manifest_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_chunk_manifests.id"), nullable=True)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(Text, nullable=False)
    search_vector: Mapped[Any] = mapped_column(TSVECTOR, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    case = relationship("CaseModel")
    document = relationship("DocumentModel")
    page = relationship("DocumentPageModel")
    chunk = relationship("DocumentChunkModel")
    text_layer = relationship("DocumentTextLayerModel")
    chunk_manifest = relationship("DocumentChunkManifestModel")
