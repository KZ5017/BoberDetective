"""make research findings a worklist layer

Revision ID: 0024_research_findings_worklist
Revises: 0023_research_finding_reviews
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0024_research_findings_worklist"
down_revision: str | None = "0023_research_finding_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("delete from human_reviews where object_type = 'research_finding'")
    op.drop_constraint("ck_human_reviews_object_type", "human_reviews", type_="check")
    op.create_check_constraint(
        "ck_human_reviews_object_type",
        "human_reviews",
        "object_type in ('entity', 'event', 'claim', 'contradiction_candidate', "
        "'missing_item_candidate', 'source_reference', 'export', 'summary_item')",
    )
    op.drop_constraint("ck_research_findings_review_status", "research_findings", type_="check")
    op.drop_column("research_findings", "review_status")


def downgrade() -> None:
    op.add_column("research_findings", sa.Column("review_status", sa.Text(), nullable=False, server_default="needs_review"))
    op.alter_column("research_findings", "review_status", server_default=None)
    op.create_check_constraint(
        "ck_research_findings_review_status",
        "research_findings",
        "review_status in ('new', 'needs_review', 'verified', 'rejected', 'corrected')",
    )
    op.drop_constraint("ck_human_reviews_object_type", "human_reviews", type_="check")
    op.create_check_constraint(
        "ck_human_reviews_object_type",
        "human_reviews",
        "object_type in ('entity', 'event', 'claim', 'contradiction_candidate', "
        "'missing_item_candidate', 'source_reference', 'export', 'summary_item', 'research_finding')",
    )
