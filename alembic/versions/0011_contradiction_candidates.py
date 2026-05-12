"""contradiction candidates

Revision ID: 0011_contradiction_candidates
Revises: 0010_summary_items
Create Date: 2026-05-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0011_contradiction_candidates"
down_revision: str | None = "0010_summary_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contradiction_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contradiction_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("claim_id_a", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("claim_id_b", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_id_a", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_id_b", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("severity_hint", sa.Text(), nullable=True),
        sa.Column("created_by_analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_validation_status", sa.Text(), nullable=False),
        sa.Column("review_status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "contradiction_type in ('time_conflict', 'location_conflict', 'identity_conflict', "
            "'document_mismatch', 'amount_conflict', 'other')",
            name="ck_contradiction_candidates_type",
        ),
        sa.CheckConstraint(
            "severity_hint is null or severity_hint in ('low', 'medium', 'high')",
            name="ck_contradiction_candidates_severity_hint",
        ),
        sa.CheckConstraint(
            "source_validation_status in ('pending_source_validation', 'source_valid', 'source_invalid')",
            name="ck_contradiction_candidates_source_validation_status",
        ),
        sa.CheckConstraint(
            "review_status in ('new', 'needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_contradiction_candidates_review_status",
        ),
        sa.CheckConstraint(
            "confidence is null or (confidence >= 0 and confidence <= 1)",
            name="ck_contradiction_candidates_confidence_range",
        ),
        sa.CheckConstraint(
            "(claim_id_a is not null and claim_id_b is not null) or (event_id_a is not null and event_id_b is not null)",
            name="ck_contradiction_candidates_has_pair",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["claim_id_a"], ["claims.id"]),
        sa.ForeignKeyConstraint(["claim_id_b"], ["claims.id"]),
        sa.ForeignKeyConstraint(["event_id_a"], ["events.id"]),
        sa.ForeignKeyConstraint(["event_id_b"], ["events.id"]),
        sa.ForeignKeyConstraint(["created_by_analysis_run_id"], ["analysis_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contradiction_candidates_case_type", "contradiction_candidates", ["case_id", "contradiction_type"])
    op.create_index("ix_contradiction_candidates_review_status", "contradiction_candidates", ["review_status"])
    op.create_index(
        "ix_contradiction_candidates_source_validation_status",
        "contradiction_candidates",
        ["source_validation_status"],
    )

    op.create_table(
        "contradiction_candidate_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contradiction_candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("side_label", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "side_label is null or side_label in ('a', 'b', 'context')",
            name="ck_contradiction_candidate_sources_side_label",
        ),
        sa.ForeignKeyConstraint(["contradiction_candidate_id"], ["contradiction_candidates.id"]),
        sa.ForeignKeyConstraint(["source_reference_id"], ["source_references.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "contradiction_candidate_id",
            "source_reference_id",
            "side_label",
            name="uq_contradiction_candidate_sources_candidate_source_side",
        ),
    )
    op.create_index(
        "ix_contradiction_candidate_sources_candidate_id",
        "contradiction_candidate_sources",
        ["contradiction_candidate_id"],
    )
    op.create_index(
        "ix_contradiction_candidate_sources_source_reference_id",
        "contradiction_candidate_sources",
        ["source_reference_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_contradiction_candidate_sources_source_reference_id", table_name="contradiction_candidate_sources")
    op.drop_index("ix_contradiction_candidate_sources_candidate_id", table_name="contradiction_candidate_sources")
    op.drop_table("contradiction_candidate_sources")
    op.drop_index("ix_contradiction_candidates_source_validation_status", table_name="contradiction_candidates")
    op.drop_index("ix_contradiction_candidates_review_status", table_name="contradiction_candidates")
    op.drop_index("ix_contradiction_candidates_case_type", table_name="contradiction_candidates")
    op.drop_table("contradiction_candidates")
