"""add rag answers

Revision ID: 0044_rag_answers
Revises: 0043_document_collections
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0044_rag_answers"
down_revision: str | None = "0043_document_collections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ANALYSIS_RUN_TYPES = (
    "'import_document', 'inspect_document', 'parse_document', 'ocr_document', 'extract_pages', "
    "'chunk_document', 'embed_chunks', 'index_chunks', 'validate_document_processing', "
    "'retired_analysis_module', 'detect_contradiction_candidates', "
    "'search_findings', 'full_document_processing', 'answer_with_citations', 'export_bundle', "
    "'llm_smoke', 'manual_entry', 'rag_query'"
)

_PREVIOUS_ANALYSIS_RUN_TYPES = (
    "'import_document', 'inspect_document', 'parse_document', 'ocr_document', 'extract_pages', "
    "'chunk_document', 'embed_chunks', 'index_chunks', 'validate_document_processing', "
    "'retired_analysis_module', 'detect_contradiction_candidates', "
    "'search_findings', 'full_document_processing', 'answer_with_citations', 'export_bundle', "
    "'llm_smoke', 'manual_entry'"
)


def upgrade() -> None:
    op.drop_constraint("ck_analysis_runs_run_type", "analysis_runs", type_="check")
    op.create_check_constraint(
        "ck_analysis_runs_run_type",
        "analysis_runs",
        f"run_type in ({_ANALYSIS_RUN_TYPES})",
    )

    op.create_table(
        "rag_answers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("analysis_run_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("answer_mode", sa.Text(), nullable=False),
        sa.Column("source_scope_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("used_sources_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("retrieval_metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.CheckConstraint("length(trim(question)) > 0", name="ck_rag_answers_question_nonblank"),
        sa.CheckConstraint("length(trim(answer_text)) > 0", name="ck_rag_answers_answer_text_nonblank"),
        sa.CheckConstraint(
            "answer_mode in ('short', 'detailed', 'source_focused', 'strict_source')",
            name="ck_rag_answers_answer_mode",
        ),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_run_id", name="uq_rag_answers_analysis_run"),
    )
    op.create_index("ix_rag_answers_case_created", "rag_answers", ["case_id", "created_at"])
    op.create_index("ix_rag_answers_analysis_run", "rag_answers", ["analysis_run_id"])


def downgrade() -> None:
    op.drop_index("ix_rag_answers_analysis_run", table_name="rag_answers")
    op.drop_index("ix_rag_answers_case_created", table_name="rag_answers")
    op.drop_table("rag_answers")

    op.drop_constraint("ck_analysis_runs_run_type", "analysis_runs", type_="check")
    op.create_check_constraint(
        "ck_analysis_runs_run_type",
        "analysis_runs",
        f"run_type in ({_PREVIOUS_ANALYSIS_RUN_TYPES})",
    )
