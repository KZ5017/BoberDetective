"""add claim titles

Revision ID: 0026_claim_titles
Revises: 0025_remove_summary_items
Create Date: 2026-05-22
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0026_claim_titles"
down_revision: str | None = "0025_remove_summary_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("claims", sa.Column("claim_title", sa.Text(), nullable=True))
    op.execute("update claims set claim_title = left(regexp_replace(trim(claim_text), '\\s+', ' ', 'g'), 160)")
    op.alter_column("claims", "claim_title", nullable=False)


def downgrade() -> None:
    op.drop_column("claims", "claim_title")
