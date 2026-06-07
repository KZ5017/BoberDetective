"""limit rag answer modes

Revision ID: 0045_limit_rag_answer_modes
Revises: 0044_rag_answers
Create Date: 2026-06-07
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0045_limit_rag_answer_modes"
down_revision: str | None = "0044_rag_answers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_rag_answers_answer_mode", "rag_answers", type_="check")
    op.create_check_constraint(
        "ck_rag_answers_answer_mode",
        "rag_answers",
        "answer_mode in ('short', 'detailed')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_rag_answers_answer_mode", "rag_answers", type_="check")
    op.create_check_constraint(
        "ck_rag_answers_answer_mode",
        "rag_answers",
        "answer_mode in ('short', 'detailed', 'source_focused', 'strict_source')",
    )
