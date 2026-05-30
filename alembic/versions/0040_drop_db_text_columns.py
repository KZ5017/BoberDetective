"""drop legacy database text storage columns

Revision ID: 0040_drop_db_text_cols
Revises: 0039_doc_proc_items
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0040_drop_db_text_cols"
down_revision: str | None = "0039_doc_proc_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_document_chunks_chunk_text_fts", table_name="document_chunks", postgresql_using="gin")
    op.drop_index("ix_document_pages_extracted_text_fts", table_name="document_pages", postgresql_using="gin")
    op.drop_column("document_chunks", "chunk_text")
    op.drop_column("document_pages", "extracted_text")


def downgrade() -> None:
    op.add_column("document_pages", sa.Column("extracted_text", sa.Text(), nullable=True))
    op.add_column("document_chunks", sa.Column("chunk_text", sa.Text(), nullable=True))
    op.create_index(
        "ix_document_pages_extracted_text_fts",
        "document_pages",
        [sa.text("to_tsvector('simple', coalesce(extracted_text, ''))")],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_document_chunks_chunk_text_fts",
        "document_chunks",
        [sa.text("to_tsvector('simple', coalesce(chunk_text, ''))")],
        postgresql_using="gin",
    )
