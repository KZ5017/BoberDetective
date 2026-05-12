"""add document persistence tables

Revision ID: 0002_documents_pages_chunks
Revises: 0001_initial_foundation
Create Date: 2026-05-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_documents_pages_chunks"
down_revision: str | None = "0001_initial_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("file_extension", sa.Text(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256_hash", sa.Text(), nullable=False),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_type", sa.Text(), nullable=True),
        sa.Column("language_code", sa.Text(), nullable=True),
        sa.Column("is_encrypted", sa.Boolean(), nullable=False),
        sa.Column("imported_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_status", sa.Text(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("parser_name", sa.Text(), nullable=True),
        sa.Column("parser_version", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("file_size_bytes > 0", name="ck_documents_file_size_positive"),
        sa.CheckConstraint("sha256_hash ~ '^[0-9a-f]{64}$'", name="ck_documents_sha256_hash_hex"),
        sa.CheckConstraint("page_count is null or page_count >= 0", name="ck_documents_page_count_non_negative"),
        sa.CheckConstraint(
            "processing_status in ('pending', 'processing', 'processed', 'failed', 'review_required')",
            name="ck_documents_processing_status",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["imported_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("case_id", "sha256_hash", name="uq_documents_case_sha256_hash"),
    )
    op.create_index("ix_documents_case_imported_at", "documents", ["case_id", sa.text("imported_at DESC")])
    op.create_index("ix_documents_processing_status", "documents", ["processing_status"])
    op.create_index("ix_documents_document_type", "documents", ["document_type"])

    op.create_table(
        "document_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("text_source", sa.Text(), nullable=False),
        sa.Column("ocr_used", sa.Boolean(), nullable=False),
        sa.Column("ocr_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("parser_name", sa.Text(), nullable=True),
        sa.Column("parser_version", sa.Text(), nullable=True),
        sa.Column("extraction_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("superseded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("text_char_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("page_number >= 1", name="ck_document_pages_page_number_positive"),
        sa.CheckConstraint("version_no >= 1", name="ck_document_pages_version_no_positive"),
        sa.CheckConstraint("text_char_count >= 0", name="ck_document_pages_text_char_count_non_negative"),
        sa.CheckConstraint(
            "ocr_confidence is null or (ocr_confidence >= 0 and ocr_confidence <= 1)",
            name="ck_document_pages_ocr_confidence_range",
        ),
        sa.CheckConstraint("text_source in ('native', 'ocr', 'mixed', 'manual')", name="ck_document_pages_text_source"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["superseded_by_id"], ["document_pages.id"]),
        sa.UniqueConstraint("document_id", "page_number", "version_no", name="uq_document_pages_document_page_version"),
    )
    op.create_index("ix_document_pages_case_document", "document_pages", ["case_id", "document_id"])
    op.create_index("ix_document_pages_page_number", "document_pages", ["page_number"])
    op.create_index("ix_document_pages_document_page_current", "document_pages", ["document_id", "page_number", "is_current"])
    op.create_index(
        "uq_document_pages_current_page",
        "document_pages",
        ["document_id", "page_number"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_index(
        "ix_document_pages_extracted_text_fts",
        "document_pages",
        [sa.text("to_tsvector('simple', extracted_text)")],
        postgresql_using="gin",
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("chunking_strategy", sa.Text(), nullable=False),
        sa.Column("chunker_version", sa.Text(), nullable=False),
        sa.Column("embedding_provider", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.Text(), nullable=True),
        sa.Column("embedding_vector_id", sa.Text(), nullable=True),
        sa.Column("chunk_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("superseded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("page_start >= 1", name="ck_document_chunks_page_start_positive"),
        sa.CheckConstraint("page_end >= page_start", name="ck_document_chunks_page_end_after_start"),
        sa.CheckConstraint("chunk_index >= 0", name="ck_document_chunks_chunk_index_non_negative"),
        sa.CheckConstraint("version_no >= 1", name="ck_document_chunks_version_no_positive"),
        sa.CheckConstraint("token_count is null or token_count >= 0", name="ck_document_chunks_token_count_non_negative"),
        sa.CheckConstraint(
            "char_end is null or char_start is null or char_end >= char_start",
            name="ck_document_chunks_char_end_after_start",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["superseded_by_id"], ["document_chunks.id"]),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            "chunker_version",
            "version_no",
            name="uq_document_chunks_document_index_chunker_version",
        ),
    )
    op.create_index("ix_document_chunks_case_document", "document_chunks", ["case_id", "document_id"])
    op.create_index("ix_document_chunks_document_pages", "document_chunks", ["document_id", "page_start", "page_end"])
    op.create_index("ix_document_chunks_document_index_current", "document_chunks", ["document_id", "chunk_index", "is_current"])
    op.create_index("ix_document_chunks_embedding_vector_id", "document_chunks", ["embedding_vector_id"])
    op.create_index(
        "uq_document_chunks_current_index",
        "document_chunks",
        ["document_id", "chunk_index", "chunker_version"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_index(
        "ix_document_chunks_chunk_text_fts",
        "document_chunks",
        [sa.text("to_tsvector('simple', chunk_text)")],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_chunk_text_fts", table_name="document_chunks", postgresql_using="gin")
    op.drop_index("uq_document_chunks_current_index", table_name="document_chunks")
    op.drop_index("ix_document_chunks_embedding_vector_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_index_current", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_pages", table_name="document_chunks")
    op.drop_index("ix_document_chunks_case_document", table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_index("ix_document_pages_extracted_text_fts", table_name="document_pages", postgresql_using="gin")
    op.drop_index("uq_document_pages_current_page", table_name="document_pages")
    op.drop_index("ix_document_pages_document_page_current", table_name="document_pages")
    op.drop_index("ix_document_pages_page_number", table_name="document_pages")
    op.drop_index("ix_document_pages_case_document", table_name="document_pages")
    op.drop_table("document_pages")

    op.drop_index("ix_documents_document_type", table_name="documents")
    op.drop_index("ix_documents_processing_status", table_name="documents")
    op.drop_index("ix_documents_case_imported_at", table_name="documents")
    op.drop_table("documents")
