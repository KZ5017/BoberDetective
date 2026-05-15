"""detached source reattach target

Revision ID: 0015_reattach_target
Revises: 0014_detached_source_items
Create Date: 2026-05-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0015_reattach_target"
down_revision: str | None = "0014_detached_source_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("detached_source_items", sa.Column("reattached_to_object_type", sa.Text(), nullable=True))
    op.add_column("detached_source_items", sa.Column("reattached_to_object_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("detached_source_items", sa.Column("reattached_to_object_title_snapshot", sa.Text(), nullable=True))
    op.create_index(
        "ix_detached_source_items_reattach_target",
        "detached_source_items",
        ["reattached_to_object_type", "reattached_to_object_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_detached_source_items_reattach_target", table_name="detached_source_items")
    op.drop_column("detached_source_items", "reattached_to_object_title_snapshot")
    op.drop_column("detached_source_items", "reattached_to_object_id")
    op.drop_column("detached_source_items", "reattached_to_object_type")
