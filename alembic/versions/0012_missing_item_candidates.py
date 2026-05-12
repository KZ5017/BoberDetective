"""missing item candidates

Revision ID: 0012_missing_item_candidates
Revises: 0011_contradiction_candidates
Create Date: 2026-05-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0012_missing_item_candidates"
down_revision: str | None = "0011_contradiction_candidates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "missing_item_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("missing_item_type", sa.Text(), nullable=False),
        sa.Column("referenced_item_text", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("expected_document_type", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_by_analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_validation_status", sa.Text(), nullable=False),
        sa.Column("review_status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "missing_item_type in ('attachment', 'video', 'expert_report', 'protocol', 'image', 'document_reference', 'other')",
            name="ck_missing_item_candidates_type",
        ),
        sa.CheckConstraint(
            "source_validation_status in ('pending_source_validation', 'source_valid', 'source_invalid')",
            name="ck_missing_item_candidates_source_validation_status",
        ),
        sa.CheckConstraint(
            "review_status in ('new', 'needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_missing_item_candidates_review_status",
        ),
        sa.CheckConstraint(
            "confidence is null or (confidence >= 0 and confidence <= 1)",
            name="ck_missing_item_candidates_confidence_range",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["created_by_analysis_run_id"], ["analysis_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_missing_item_candidates_case_type", "missing_item_candidates", ["case_id", "missing_item_type"])
    op.create_index("ix_missing_item_candidates_review_status", "missing_item_candidates", ["review_status"])
    op.create_index(
        "ix_missing_item_candidates_source_validation_status",
        "missing_item_candidates",
        ["source_validation_status"],
    )

    op.create_table(
        "missing_item_candidate_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("missing_item_candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relevance_rank", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "relevance_rank is null or relevance_rank >= 0",
            name="ck_missing_item_candidate_sources_relevance_rank_non_negative",
        ),
        sa.ForeignKeyConstraint(["missing_item_candidate_id"], ["missing_item_candidates.id"]),
        sa.ForeignKeyConstraint(["source_reference_id"], ["source_references.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "missing_item_candidate_id",
            "source_reference_id",
            name="uq_missing_item_candidate_sources_candidate_source",
        ),
    )
    op.create_index(
        "ix_missing_item_candidate_sources_candidate_id",
        "missing_item_candidate_sources",
        ["missing_item_candidate_id"],
    )
    op.create_index(
        "ix_missing_item_candidate_sources_source_reference_id",
        "missing_item_candidate_sources",
        ["source_reference_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_missing_item_candidate_sources_source_reference_id", table_name="missing_item_candidate_sources")
    op.drop_index("ix_missing_item_candidate_sources_candidate_id", table_name="missing_item_candidate_sources")
    op.drop_table("missing_item_candidate_sources")
    op.drop_index("ix_missing_item_candidates_source_validation_status", table_name="missing_item_candidates")
    op.drop_index("ix_missing_item_candidates_review_status", table_name="missing_item_candidates")
    op.drop_index("ix_missing_item_candidates_case_type", table_name="missing_item_candidates")
    op.drop_table("missing_item_candidates")
