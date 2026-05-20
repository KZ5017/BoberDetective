"""research findings

Revision ID: 0021_research_findings
Revises: 0020_document_lifecycle_status
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0021_research_findings"
down_revision: str | None = "0020_document_lifecycle_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("finding_text", sa.Text(), nullable=False),
        sa.Column("suggested_type", sa.Text(), nullable=False),
        sa.Column("suggested_type_reason", sa.Text(), nullable=True),
        sa.Column("relevance_reason", sa.Text(), nullable=False),
        sa.Column("source_validation_status", sa.Text(), nullable=False),
        sa.Column("review_status", sa.Text(), nullable=False),
        sa.Column("conversion_status", sa.Text(), nullable=False),
        sa.Column("target_object_type", sa.Text(), nullable=True),
        sa.Column("target_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "suggested_type in ('claim', 'event', 'entity', 'document_reference', 'other')",
            name="ck_research_findings_suggested_type",
        ),
        sa.CheckConstraint(
            "source_validation_status in ('pending_source_validation', 'source_valid', 'source_invalid')",
            name="ck_research_findings_source_validation_status",
        ),
        sa.CheckConstraint(
            "review_status in ('new', 'needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_research_findings_review_status",
        ),
        sa.CheckConstraint(
            "conversion_status in ('not_converted', 'converted', 'ignored')",
            name="ck_research_findings_conversion_status",
        ),
        sa.CheckConstraint(
            "target_object_type is null or target_object_type in ('claim', 'event', 'entity', 'missing_item_candidate', 'summary_item', 'other')",
            name="ck_research_findings_target_object_type",
        ),
        sa.CheckConstraint(
            "(conversion_status = 'converted' and target_object_type is not null and target_object_id is not null) "
            "or (conversion_status <> 'converted' and target_object_type is null and target_object_id is null)",
            name="ck_research_findings_conversion_target_consistency",
        ),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["source_reference_id"], ["source_references.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_findings_case_created", "research_findings", ["case_id", "created_at"])
    op.create_index("ix_research_findings_source_reference", "research_findings", ["source_reference_id"])

    op.drop_constraint("ck_analysis_run_outputs_output_type", "analysis_run_outputs", type_="check")
    op.create_check_constraint(
        "ck_analysis_run_outputs_output_type",
        "analysis_run_outputs",
        "output_type in ('document', 'page', 'chunk', 'entity', 'mention', 'event', 'claim', 'contradiction_candidate', "
        "'missing_item_candidate', 'export', 'summary_item', 'source_reference', 'research_finding')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_analysis_run_outputs_output_type", "analysis_run_outputs", type_="check")
    op.create_check_constraint(
        "ck_analysis_run_outputs_output_type",
        "analysis_run_outputs",
        "output_type in ('document', 'page', 'chunk', 'entity', 'mention', 'event', 'claim', 'contradiction_candidate', "
        "'missing_item_candidate', 'export', 'summary_item', 'source_reference')",
    )

    op.drop_index("ix_research_findings_source_reference", table_name="research_findings")
    op.drop_index("ix_research_findings_case_created", table_name="research_findings")
    op.drop_table("research_findings")
