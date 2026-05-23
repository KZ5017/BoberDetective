"""delete discarded detached sources

Revision ID: 0032_delete_detached_sources
Revises: 0031_detached_source_claims
Create Date: 2026-05-23
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0032_delete_detached_sources"
down_revision: str | None = "0031_detached_source_claims"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("delete from detached_source_items where handling_status = 'discarded'")
    op.drop_constraint("ck_detached_source_items_handling_status", "detached_source_items", type_="check")
    op.create_check_constraint(
        "ck_detached_source_items_handling_status",
        "detached_source_items",
        "handling_status in ('needs_review', 'reattached')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_detached_source_items_handling_status", "detached_source_items", type_="check")
    op.create_check_constraint(
        "ck_detached_source_items_handling_status",
        "detached_source_items",
        "handling_status in ('needs_review', 'reattached', 'discarded')",
    )
