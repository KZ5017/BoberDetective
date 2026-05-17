"""Drop legacy free-text document_type.

Revision ID: 0019_drop_legacy_document_type
Revises: 0018_document_taxonomy
Create Date: 2026-05-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0019_drop_legacy_document_type"
down_revision: str | None = "0018_document_taxonomy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_documents_document_type", table_name="documents")
    op.drop_column("documents", "document_type")


def downgrade() -> None:
    op.add_column("documents", sa.Column("document_type", sa.Text(), nullable=True))
    op.create_index("ix_documents_document_type", "documents", ["document_type"])
