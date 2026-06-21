"""add full document free-question answers

Revision ID: 0050_full_document_answers
Revises: 0049_contradiction_partial_pair
Create Date: 2026-06-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0050_full_document_answers"
down_revision: str | None = "0049_contradiction_partial_pair"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_OUTPUT_TYPE_CONSTRAINT = (
    "output_type in ('document', 'page', 'chunk', 'entity', 'mention', 'event', 'claim', 'contradiction_candidate', "
    "'missing_item_candidate', 'export', 'source_reference', 'research_finding', 'document_processing_item', "
    "'full_document_answer')"
)

OLD_OUTPUT_TYPE_CONSTRAINT = (
    "output_type in ('document', 'page', 'chunk', 'entity', 'mention', 'event', 'claim', 'contradiction_candidate', "
    "'missing_item_candidate', 'export', 'source_reference', 'research_finding', 'document_processing_item')"
)


def upgrade() -> None:
    op.create_table(
        "full_document_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_key", sa.Text(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("source_summary", sa.Text(), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("source_page_count", sa.Integer(), nullable=False),
        sa.Column("source_character_count", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column("prompt_template_name", sa.Text(), nullable=True),
        sa.Column("prompt_template_version", sa.Text(), nullable=True),
        sa.Column("answer_status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("profile_key in ('free_document_question')", name="ck_full_document_answers_profile_key"),
        sa.CheckConstraint("length(trim(question_text)) > 0", name="ck_full_document_answers_question_not_blank"),
        sa.CheckConstraint("length(trim(answer_text)) > 0", name="ck_full_document_answers_answer_not_blank"),
        sa.CheckConstraint("answer_status in ('active', 'deleted')", name="ck_full_document_answers_status"),
        sa.CheckConstraint("page_start >= 1", name="ck_full_document_answers_page_start_positive"),
        sa.CheckConstraint("page_end >= page_start", name="ck_full_document_answers_page_range_order"),
        sa.CheckConstraint("source_page_count >= 1", name="ck_full_document_answers_source_page_count_positive"),
        sa.CheckConstraint("source_character_count >= 0", name="ck_full_document_answers_source_char_count_non_negative"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_run_id", name="uq_full_document_answers_analysis_run"),
    )
    op.create_index("ix_full_document_answers_case_document", "full_document_answers", ["case_id", "document_id"])
    op.create_index("ix_full_document_answers_run", "full_document_answers", ["analysis_run_id"])
    op.create_index("ix_full_document_answers_status", "full_document_answers", ["case_id", "answer_status"])

    op.drop_constraint("ck_analysis_run_outputs_output_type", "analysis_run_outputs", type_="check")
    op.create_check_constraint("ck_analysis_run_outputs_output_type", "analysis_run_outputs", NEW_OUTPUT_TYPE_CONSTRAINT)


def downgrade() -> None:
    op.execute("delete from analysis_run_outputs where output_type = 'full_document_answer'")
    op.drop_constraint("ck_analysis_run_outputs_output_type", "analysis_run_outputs", type_="check")
    op.create_check_constraint("ck_analysis_run_outputs_output_type", "analysis_run_outputs", OLD_OUTPUT_TYPE_CONSTRAINT)

    op.drop_index("ix_full_document_answers_status", table_name="full_document_answers")
    op.drop_index("ix_full_document_answers_run", table_name="full_document_answers")
    op.drop_index("ix_full_document_answers_case_document", table_name="full_document_answers")
    op.drop_table("full_document_answers")
