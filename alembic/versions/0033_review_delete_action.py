"""add review delete action

Revision ID: 0033_review_delete_action
Revises: 0032_delete_detached_sources
Create Date: 2026-05-23
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0033_review_delete_action"
down_revision: str | None = "0032_delete_detached_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_human_reviews_action_type", "human_reviews", type_="check")
    op.create_check_constraint(
        "ck_human_reviews_action_type",
        "human_reviews",
        "action_type in ('mark_needs_review', 'verify', 'reject', 'correct', 'comment', 'attach_source', 'detach_source', 'delete_object')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_human_reviews_action_type", "human_reviews", type_="check")
    op.create_check_constraint(
        "ck_human_reviews_action_type",
        "human_reviews",
        "action_type in ('mark_needs_review', 'verify', 'reject', 'correct', 'comment', 'attach_source', 'detach_source')",
    )
