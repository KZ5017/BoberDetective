"""detached source items

Revision ID: 0014_detached_source_items
Revises: 0013_processing_runs
Create Date: 2026-05-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0014_detached_source_items"
down_revision: str | None = "0013_processing_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "detached_source_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("detached_from_object_type", sa.Text(), nullable=False),
        sa.Column("detached_from_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("detached_from_source_link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("detached_from_source_link_type", sa.Text(), nullable=False),
        sa.Column("object_title_snapshot", sa.Text(), nullable=False),
        sa.Column("object_body_snapshot", sa.Text(), nullable=True),
        sa.Column("object_subtype_snapshot", sa.Text(), nullable=True),
        sa.Column("object_review_status_snapshot", sa.Text(), nullable=True),
        sa.Column("source_validation_status_snapshot", sa.Text(), nullable=True),
        sa.Column("source_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("handling_status", sa.Text(), nullable=False),
        sa.Column("detach_comment", sa.Text(), nullable=True),
        sa.Column("detached_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("detached_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "detached_from_object_type in ('entity', 'event', 'missing_item_candidate')",
            name="ck_detached_source_items_object_type",
        ),
        sa.CheckConstraint(
            "handling_status in ('needs_review', 'reattached', 'discarded')",
            name="ck_detached_source_items_handling_status",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["detached_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_reference_id"], ["source_references.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_detached_source_items_case_status", "detached_source_items", ["case_id", "handling_status"])
    op.create_index("ix_detached_source_items_source_reference_id", "detached_source_items", ["source_reference_id"])
    op.create_index(
        "ix_detached_source_items_origin",
        "detached_source_items",
        ["detached_from_object_type", "detached_from_object_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_detached_source_items_origin", table_name="detached_source_items")
    op.drop_index("ix_detached_source_items_source_reference_id", table_name="detached_source_items")
    op.drop_index("ix_detached_source_items_case_status", table_name="detached_source_items")
    op.drop_table("detached_source_items")
