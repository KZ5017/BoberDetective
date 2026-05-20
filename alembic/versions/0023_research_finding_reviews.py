"""allow research finding human reviews

Revision ID: 0023_research_finding_reviews
Revises: 0022_search_findings_run_type
Create Date: 2026-05-20
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0023_research_finding_reviews"
down_revision: str | None = "0022_search_findings_run_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_human_reviews_object_type", "human_reviews", type_="check")
    op.create_check_constraint(
        "ck_human_reviews_object_type",
        "human_reviews",
        "object_type in ('entity', 'event', 'claim', 'contradiction_candidate', "
        "'missing_item_candidate', 'source_reference', 'export', 'summary_item', 'research_finding')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_human_reviews_object_type", "human_reviews", type_="check")
    op.create_check_constraint(
        "ck_human_reviews_object_type",
        "human_reviews",
        "object_type in ('entity', 'event', 'claim', 'contradiction_candidate', "
        "'missing_item_candidate', 'source_reference', 'export', 'summary_item')",
    )
