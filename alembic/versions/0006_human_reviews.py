"""add human reviews

Revision ID: 0006_human_reviews
Revises: 0005_claims
Create Date: 2026-05-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006_human_reviews"
down_revision: str | None = "0005_claims"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "human_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("previous_review_status", sa.Text(), nullable=True),
        sa.Column("new_review_status", sa.Text(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("correction_patch_json", postgresql.JSONB(), nullable=True),
        sa.Column("performed_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "object_type in ('entity', 'event', 'claim', 'contradiction_candidate', "
            "'missing_item_candidate', 'source_reference', 'export')",
            name="ck_human_reviews_object_type",
        ),
        sa.CheckConstraint(
            "action_type in ('mark_needs_review', 'verify', 'reject', 'correct', 'comment', 'attach_source', 'detach_source')",
            name="ck_human_reviews_action_type",
        ),
        sa.CheckConstraint(
            "previous_review_status is null or previous_review_status in ('new', 'needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_human_reviews_previous_review_status",
        ),
        sa.CheckConstraint(
            "new_review_status is null or new_review_status in ('new', 'needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_human_reviews_new_review_status",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["performed_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_human_reviews_object", "human_reviews", ["object_type", "object_id", sa.text("performed_at DESC")])
    op.create_index("ix_human_reviews_performed_by_user_id", "human_reviews", ["performed_by_user_id"])
    op.create_index("ix_human_reviews_action_type", "human_reviews", ["action_type"])


def downgrade() -> None:
    op.drop_index("ix_human_reviews_action_type", table_name="human_reviews")
    op.drop_index("ix_human_reviews_performed_by_user_id", table_name="human_reviews")
    op.drop_index("ix_human_reviews_object", table_name="human_reviews")
    op.drop_table("human_reviews")
