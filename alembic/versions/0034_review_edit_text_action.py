"""add review edit text action

Revision ID: 0034_review_edit_text
Revises: 0033_review_delete_action
Create Date: 2026-05-23
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0034_review_edit_text"
down_revision: str | None = "0033_review_delete_action"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_human_reviews_action_type", "human_reviews", type_="check")
    op.create_check_constraint(
        "ck_human_reviews_action_type",
        "human_reviews",
        "action_type in ('mark_needs_review', 'verify', 'reject', 'correct', 'comment', 'attach_source', 'detach_source', 'delete_object', 'edit_text')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_human_reviews_action_type", "human_reviews", type_="check")
    op.create_check_constraint(
        "ck_human_reviews_action_type",
        "human_reviews",
        "action_type in ('mark_needs_review', 'verify', 'reject', 'correct', 'comment', 'attach_source', 'detach_source', 'delete_object')",
    )
