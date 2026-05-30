"""add document search entries

Revision ID: 0036_search_entries
Revises: 0035_text_layer_manifests
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0036_search_entries"
down_revision: str | None = "0035_text_layer_manifests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_search_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("text_layer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chunk_manifest_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.Column("document_group_code", sa.Text(), nullable=False),
        sa.Column("document_type_code", sa.Text(), nullable=False),
        sa.Column("lifecycle_status", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.Text(), nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("source_type in ('page', 'chunk')", name="ck_document_search_entries_source_type"),
        sa.CheckConstraint("page_start >= 1", name="ck_document_search_entries_page_start_positive"),
        sa.CheckConstraint("page_end >= page_start", name="ck_document_search_entries_page_end_after_start"),
        sa.CheckConstraint("chunk_index is null or chunk_index >= 0", name="ck_document_search_entries_chunk_index_non_negative"),
        sa.CheckConstraint("text_hash ~ '^[0-9a-f]{64}$'", name="ck_document_search_entries_text_hash_hex"),
        sa.CheckConstraint(
            "lifecycle_status in ('active', 'excluded', 'archived')",
            name="ck_document_search_entries_lifecycle_status",
        ),
        sa.CheckConstraint(
            "(source_type = 'page' and page_id is not null and chunk_id is null) "
            "or (source_type = 'chunk' and chunk_id is not null and page_id is null)",
            name="ck_document_search_entries_source_link",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"]),
        sa.ForeignKeyConstraint(["chunk_manifest_id"], ["document_chunk_manifests.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["page_id"], ["document_pages.id"]),
        sa.ForeignKeyConstraint(["text_layer_id"], ["document_text_layers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_search_entries_vector",
        "document_search_entries",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_document_search_entries_case_source_current",
        "document_search_entries",
        ["case_id", "source_type", "is_current"],
    )
    op.create_index(
        "ix_document_search_entries_case_document_current",
        "document_search_entries",
        ["case_id", "document_id", "is_current"],
    )
    op.create_index(
        "ix_document_search_entries_taxonomy_current",
        "document_search_entries",
        ["case_id", "document_group_code", "document_type_code", "is_current"],
    )
    op.create_index(
        "ix_document_search_entries_page_range",
        "document_search_entries",
        ["case_id", "page_start", "page_end"],
    )
    op.create_index(
        "uq_document_search_entries_current_page",
        "document_search_entries",
        ["page_id"],
        unique=True,
        postgresql_where=sa.text("source_type = 'page' AND is_current = true"),
    )
    op.create_index(
        "uq_document_search_entries_current_chunk",
        "document_search_entries",
        ["chunk_id"],
        unique=True,
        postgresql_where=sa.text("source_type = 'chunk' AND is_current = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_document_search_entries_current_chunk", table_name="document_search_entries")
    op.drop_index("uq_document_search_entries_current_page", table_name="document_search_entries")
    op.drop_index("ix_document_search_entries_page_range", table_name="document_search_entries")
    op.drop_index("ix_document_search_entries_taxonomy_current", table_name="document_search_entries")
    op.drop_index("ix_document_search_entries_case_document_current", table_name="document_search_entries")
    op.drop_index("ix_document_search_entries_case_source_current", table_name="document_search_entries")
    op.drop_index("ix_document_search_entries_vector", table_name="document_search_entries")
    op.drop_table("document_search_entries")
