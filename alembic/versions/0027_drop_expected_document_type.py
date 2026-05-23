"""drop expected document type from missing item candidates

Revision ID: 0027_drop_expected_document_type
Revises: 0026_claim_titles
Create Date: 2026-05-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0027_drop_expected_document_type"
down_revision: str | None = "0026_claim_titles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("missing_item_candidates", "expected_document_type")


def downgrade() -> None:
    op.add_column("missing_item_candidates", sa.Column("expected_document_type", sa.Text(), nullable=True))
