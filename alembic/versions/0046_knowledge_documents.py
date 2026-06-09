"""add knowledge documents

Revision ID: 0046_knowledge_documents
Revises: 0045_limit_rag_answer_modes
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0046_knowledge_documents"
down_revision: str | None = "0045_limit_rag_answer_modes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=True),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("file_extension", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256_hash", sa.Text(), nullable=False),
        sa.Column("document_kind", sa.Text(), nullable=False),
        sa.Column("processing_status", sa.Text(), nullable=False),
        sa.Column("language_code", sa.Text(), nullable=True),
        sa.Column("parser_name", sa.Text(), nullable=True),
        sa.Column("parser_version", sa.Text(), nullable=True),
        sa.Column("text_layer_storage_uri", sa.Text(), nullable=True),
        sa.Column("text_layer_manifest_hash", sa.Text(), nullable=True),
        sa.Column("chunk_manifest_storage_uri", sa.Text(), nullable=True),
        sa.Column("chunk_manifest_hash", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("frontmatter_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("heading_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("quality_flags_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("imported_by_user_id", sa.UUID(), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("file_size_bytes > 0", name="ck_knowledge_documents_file_size_positive"),
        sa.CheckConstraint("sha256_hash ~ '^[0-9a-f]{64}$'", name="ck_knowledge_documents_sha256_hash_hex"),
        sa.CheckConstraint(
            "document_kind in ('markdown_note')",
            name="ck_knowledge_documents_document_kind",
        ),
        sa.CheckConstraint(
            "processing_status in ('imported', 'processed', 'indexing', 'indexed', 'failed', 'archived')",
            name="ck_knowledge_documents_processing_status",
        ),
        sa.CheckConstraint("file_extension = '.md'", name="ck_knowledge_documents_file_extension_md"),
        sa.CheckConstraint("chunk_count >= 0", name="ck_knowledge_documents_chunk_count_non_negative"),
        sa.CheckConstraint("char_count >= 0", name="ck_knowledge_documents_char_count_non_negative"),
        sa.CheckConstraint(
            "text_layer_manifest_hash is null or text_layer_manifest_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_documents_text_layer_manifest_hash_hex",
        ),
        sa.CheckConstraint(
            "chunk_manifest_hash is null or chunk_manifest_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_documents_chunk_manifest_hash_hex",
        ),
        sa.ForeignKeyConstraint(["imported_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha256_hash", name="uq_knowledge_documents_sha256_hash"),
    )
    op.create_index(
        "ix_knowledge_documents_imported_at",
        "knowledge_documents",
        ["imported_at"],
    )
    op.create_index(
        "ix_knowledge_documents_status_imported",
        "knowledge_documents",
        ["processing_status", "imported_at"],
    )
    op.create_index(
        "ix_knowledge_documents_relative_path",
        "knowledge_documents",
        ["relative_path"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_documents_relative_path", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_status_imported", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_imported_at", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
