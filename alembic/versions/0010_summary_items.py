"""summary items

Revision ID: 0010_summary_items
Revises: 0009_entities
Create Date: 2026-05-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0010_summary_items"
down_revision: str | None = "0009_entities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "summary_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_by_analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_validation_status", sa.Text(), nullable=False),
        sa.Column("review_status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "summary_type in ('case_overview', 'document_summary', 'timeline_summary', 'entity_summary', 'caution_note', 'other')",
            name="ck_summary_items_summary_type",
        ),
        sa.CheckConstraint(
            "source_validation_status in ('pending_source_validation', 'source_valid', 'source_invalid')",
            name="ck_summary_items_source_validation_status",
        ),
        sa.CheckConstraint(
            "review_status in ('new', 'needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_summary_items_review_status",
        ),
        sa.CheckConstraint("confidence is null or (confidence >= 0 and confidence <= 1)", name="ck_summary_items_confidence_range"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["created_by_analysis_run_id"], ["analysis_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_summary_items_case_type", "summary_items", ["case_id", "summary_type"])
    op.create_index("ix_summary_items_review_status", "summary_items", ["review_status"])
    op.create_index("ix_summary_items_source_validation_status", "summary_items", ["source_validation_status"])

    op.create_table(
        "summary_item_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relevance_rank", sa.Integer(), nullable=True),
        sa.Column("support_type", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("support_type in ('direct', 'indirect', 'contextual')", name="ck_summary_item_sources_support_type"),
        sa.CheckConstraint(
            "relevance_rank is null or relevance_rank >= 0",
            name="ck_summary_item_sources_relevance_rank_non_negative",
        ),
        sa.ForeignKeyConstraint(["source_reference_id"], ["source_references.id"]),
        sa.ForeignKeyConstraint(["summary_item_id"], ["summary_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("summary_item_id", "source_reference_id", name="uq_summary_item_sources_item_source_reference"),
    )
    op.create_index("ix_summary_item_sources_source_reference_id", "summary_item_sources", ["source_reference_id"])
    op.create_index("ix_summary_item_sources_summary_item_id", "summary_item_sources", ["summary_item_id"])

    op.drop_constraint("ck_human_reviews_object_type", "human_reviews", type_="check")
    op.create_check_constraint(
        "ck_human_reviews_object_type",
        "human_reviews",
        "object_type in ('entity', 'event', 'claim', 'contradiction_candidate', "
        "'missing_item_candidate', 'source_reference', 'export', 'summary_item')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_human_reviews_object_type", "human_reviews", type_="check")
    op.create_check_constraint(
        "ck_human_reviews_object_type",
        "human_reviews",
        "object_type in ('entity', 'event', 'claim', 'contradiction_candidate', "
        "'missing_item_candidate', 'source_reference', 'export')",
    )
    op.drop_index("ix_summary_item_sources_summary_item_id", table_name="summary_item_sources")
    op.drop_index("ix_summary_item_sources_source_reference_id", table_name="summary_item_sources")
    op.drop_table("summary_item_sources")
    op.drop_index("ix_summary_items_source_validation_status", table_name="summary_items")
    op.drop_index("ix_summary_items_review_status", table_name="summary_items")
    op.drop_index("ix_summary_items_case_type", table_name="summary_items")
    op.drop_table("summary_items")
