"""add claims and claim sources

Revision ID: 0005_claims
Revises: 0004_analysis_runs
Create Date: 2026-05-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_claims"
down_revision: str | None = "0004_analysis_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_type", sa.Text(), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("speaker_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("related_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("claim_time_raw", sa.Text(), nullable=True),
        sa.Column("claim_time_normalized", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_by_analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_validation_status", sa.Text(), nullable=False),
        sa.Column("review_status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "claim_type in ('witness_statement', 'document_fact', 'expert_opinion', "
            "'administrative_fact', 'inference_candidate', 'unknown')",
            name="ck_claims_claim_type",
        ),
        sa.CheckConstraint(
            "source_validation_status in ('pending_source_validation', 'source_valid', 'source_invalid')",
            name="ck_claims_source_validation_status",
        ),
        sa.CheckConstraint(
            "review_status in ('new', 'needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_claims_review_status",
        ),
        sa.CheckConstraint("confidence is null or (confidence >= 0 and confidence <= 1)", name="ck_claims_confidence_range"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["created_by_analysis_run_id"], ["analysis_runs.id"]),
    )
    op.create_index("ix_claims_case_type", "claims", ["case_id", "claim_type"])
    op.create_index("ix_claims_related_event_id", "claims", ["related_event_id"])
    op.create_index("ix_claims_source_validation_status", "claims", ["source_validation_status"])
    op.create_index("ix_claims_review_status", "claims", ["review_status"])
    op.create_index(
        "ix_claims_claim_text_fts",
        "claims",
        [sa.text("to_tsvector('simple', claim_text)")],
        postgresql_using="gin",
    )

    op.create_table(
        "claim_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relevance_rank", sa.Integer(), nullable=True),
        sa.Column("support_type", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("support_type in ('direct', 'indirect', 'contextual')", name="ck_claim_sources_support_type"),
        sa.CheckConstraint("relevance_rank is null or relevance_rank >= 0", name="ck_claim_sources_relevance_rank_non_negative"),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["source_reference_id"], ["source_references.id"]),
        sa.UniqueConstraint("claim_id", "source_reference_id", name="uq_claim_sources_claim_source_reference"),
    )
    op.create_index("ix_claim_sources_claim_id", "claim_sources", ["claim_id"])
    op.create_index("ix_claim_sources_source_reference_id", "claim_sources", ["source_reference_id"])


def downgrade() -> None:
    op.drop_index("ix_claim_sources_source_reference_id", table_name="claim_sources")
    op.drop_index("ix_claim_sources_claim_id", table_name="claim_sources")
    op.drop_table("claim_sources")

    op.drop_index("ix_claims_claim_text_fts", table_name="claims", postgresql_using="gin")
    op.drop_index("ix_claims_review_status", table_name="claims")
    op.drop_index("ix_claims_source_validation_status", table_name="claims")
    op.drop_index("ix_claims_related_event_id", table_name="claims")
    op.drop_index("ix_claims_case_type", table_name="claims")
    op.drop_table("claims")
