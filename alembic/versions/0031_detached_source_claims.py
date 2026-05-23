"""allow detached claim sources

Revision ID: 0031_detached_source_claims
Revises: 0030_llm_support_status
Create Date: 2026-05-23
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0031_detached_source_claims"
down_revision: str | None = "0030_llm_support_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_detached_source_items_object_type", "detached_source_items", type_="check")
    op.create_check_constraint(
        "ck_detached_source_items_object_type",
        "detached_source_items",
        "detached_from_object_type in ('claim', 'entity', 'event', 'missing_item_candidate')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_detached_source_items_object_type", "detached_source_items", type_="check")
    op.create_check_constraint(
        "ck_detached_source_items_object_type",
        "detached_source_items",
        "detached_from_object_type in ('entity', 'event', 'missing_item_candidate')",
    )
