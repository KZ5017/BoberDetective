"""make legacy document text columns nullable

Revision ID: 0038_nullable_text_fields
Revises: 0037_remove_doc_taxonomy
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0038_nullable_text_fields"
down_revision: str | None = "0037_remove_doc_taxonomy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("document_pages", "extracted_text", existing_type=sa.Text(), nullable=True)
    op.alter_column("document_chunks", "chunk_text", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE document_pages SET extracted_text = '' WHERE extracted_text IS NULL")
    op.execute("UPDATE document_chunks SET chunk_text = '' WHERE chunk_text IS NULL")
    op.alter_column("document_chunks", "chunk_text", existing_type=sa.Text(), nullable=False)
    op.alter_column("document_pages", "extracted_text", existing_type=sa.Text(), nullable=False)
