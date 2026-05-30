"""add document text layer and chunk manifest tables

Revision ID: 0035_text_layer_manifests
Revises: 0034_review_edit_text
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0035_text_layer_manifests"
down_revision: str | None = "0034_review_edit_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_text_layers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("parser_name", sa.Text(), nullable=True),
        sa.Column("parser_version", sa.Text(), nullable=True),
        sa.Column("language_code", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("manifest_hash", sa.Text(), nullable=False),
        sa.Column("created_by_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("source_kind in ('native_text', 'ocr', 'manual')", name="ck_document_text_layers_source_kind"),
        sa.CheckConstraint("page_count >= 0", name="ck_document_text_layers_page_count_non_negative"),
        sa.CheckConstraint("char_count >= 0", name="ck_document_text_layers_char_count_non_negative"),
        sa.CheckConstraint("version_no >= 1", name="ck_document_text_layers_version_no_positive"),
        sa.CheckConstraint("manifest_hash ~ '^[0-9a-f]{64}$'", name="ck_document_text_layers_manifest_hash_hex"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["created_by_run_id"], ["analysis_runs.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_text_layers_case_document", "document_text_layers", ["case_id", "document_id"])
    op.create_index(
        "ix_document_text_layers_current",
        "document_text_layers",
        ["document_id", "is_current"],
    )

    op.create_table(
        "document_chunk_manifests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text_layer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunking_strategy", sa.Text(), nullable=False),
        sa.Column("chunker_version", sa.Text(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("manifest_hash", sa.Text(), nullable=False),
        sa.Column("created_by_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("chunk_count >= 0", name="ck_document_chunk_manifests_chunk_count_non_negative"),
        sa.CheckConstraint("version_no >= 1", name="ck_document_chunk_manifests_version_no_positive"),
        sa.CheckConstraint("manifest_hash ~ '^[0-9a-f]{64}$'", name="ck_document_chunk_manifests_manifest_hash_hex"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["created_by_run_id"], ["analysis_runs.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["text_layer_id"], ["document_text_layers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_chunk_manifests_case_document",
        "document_chunk_manifests",
        ["case_id", "document_id"],
    )
    op.create_index(
        "ix_document_chunk_manifests_text_layer",
        "document_chunk_manifests",
        ["text_layer_id"],
    )
    op.create_index(
        "ix_document_chunk_manifests_current",
        "document_chunk_manifests",
        ["document_id", "is_current"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunk_manifests_current", table_name="document_chunk_manifests")
    op.drop_index("ix_document_chunk_manifests_text_layer", table_name="document_chunk_manifests")
    op.drop_index("ix_document_chunk_manifests_case_document", table_name="document_chunk_manifests")
    op.drop_table("document_chunk_manifests")
    op.drop_index("ix_document_text_layers_current", table_name="document_text_layers")
    op.drop_index("ix_document_text_layers_case_document", table_name="document_text_layers")
    op.drop_table("document_text_layers")
