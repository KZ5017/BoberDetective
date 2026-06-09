from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class KnowledgeDocumentModel(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        CheckConstraint("file_size_bytes > 0", name="ck_knowledge_documents_file_size_positive"),
        CheckConstraint("sha256_hash ~ '^[0-9a-f]{64}$'", name="ck_knowledge_documents_sha256_hash_hex"),
        CheckConstraint(
            "document_kind in ('markdown_note')",
            name="ck_knowledge_documents_document_kind",
        ),
        CheckConstraint(
            "processing_status in ('imported', 'processed', 'indexing', 'indexed', 'failed', 'archived')",
            name="ck_knowledge_documents_processing_status",
        ),
        CheckConstraint("file_extension = '.md'", name="ck_knowledge_documents_file_extension_md"),
        CheckConstraint("chunk_count >= 0", name="ck_knowledge_documents_chunk_count_non_negative"),
        CheckConstraint("char_count >= 0", name="ck_knowledge_documents_char_count_non_negative"),
        CheckConstraint(
            "text_layer_manifest_hash is null or text_layer_manifest_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_documents_text_layer_manifest_hash_hex",
        ),
        CheckConstraint(
            "chunk_manifest_hash is null or chunk_manifest_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_documents_chunk_manifest_hash_hex",
        ),
        UniqueConstraint("sha256_hash", name="uq_knowledge_documents_sha256_hash"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    relative_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_extension: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(Text, nullable=False)
    document_kind: Mapped[str] = mapped_column(Text, nullable=False, default="markdown_note")
    processing_status: Mapped[str] = mapped_column(Text, nullable=False, default="imported")
    language_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_layer_storage_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_layer_manifest_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_manifest_storage_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_manifest_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding_provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    vector_collection: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexed_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    frontmatter_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    heading_summary_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    quality_flags_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    imported_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    imported_by = relationship("UserModel")
