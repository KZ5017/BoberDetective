"""add source references

Revision ID: 0003_source_references
Revises: 0002_documents_pages_chunks
Create Date: 2026-05-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_source_references"
down_revision: str | None = "0002_documents_pages_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("quote_text", sa.Text(), nullable=False),
        sa.Column("quote_char_start", sa.Integer(), nullable=True),
        sa.Column("quote_char_end", sa.Integer(), nullable=True),
        sa.Column("citation_label", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("extraction_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("page_number is null or page_number >= 1", name="ck_source_references_page_number_positive"),
        sa.CheckConstraint(
            "confidence is null or (confidence >= 0 and confidence <= 1)",
            name="ck_source_references_confidence_range",
        ),
        sa.CheckConstraint(
            "quote_char_end is null or quote_char_start is null or quote_char_end >= quote_char_start",
            name="ck_source_references_quote_char_end_after_start",
        ),
        sa.CheckConstraint(
            "source_kind in ('page_quote', 'chunk_quote', 'document_metadata', 'manual_note')",
            name="ck_source_references_source_kind",
        ),
        sa.CheckConstraint(
            "source_kind = 'document_metadata' or page_id is not null or chunk_id is not null",
            name="ck_source_references_source_location_required",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["page_id"], ["document_pages.id"]),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_source_references_case_document_page", "source_references", ["case_id", "document_id", "page_number"])
    op.create_index("ix_source_references_chunk_id", "source_references", ["chunk_id"])
    op.create_index("ix_source_references_extraction_run_id", "source_references", ["extraction_run_id"])
    op.create_index("ix_source_references_source_kind", "source_references", ["source_kind"])


def downgrade() -> None:
    op.drop_index("ix_source_references_source_kind", table_name="source_references")
    op.drop_index("ix_source_references_extraction_run_id", table_name="source_references")
    op.drop_index("ix_source_references_chunk_id", table_name="source_references")
    op.drop_index("ix_source_references_case_document_page", table_name="source_references")
    op.drop_table("source_references")
