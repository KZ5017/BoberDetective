"""add knowledge index metadata

Revision ID: 0047_knowledge_index_metadata
Revises: 0046_knowledge_documents
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0047_knowledge_index_metadata"
down_revision: str | None = "0046_knowledge_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("knowledge_documents", sa.Column("embedding_provider", sa.Text(), nullable=True))
    op.add_column("knowledge_documents", sa.Column("embedding_model", sa.Text(), nullable=True))
    op.add_column("knowledge_documents", sa.Column("vector_collection", sa.Text(), nullable=True))
    op.add_column("knowledge_documents", sa.Column("indexed_chunk_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("knowledge_documents", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_knowledge_documents_indexed_chunk_count_non_negative",
        "knowledge_documents",
        "indexed_chunk_count >= 0",
    )
    op.create_index(
        "ix_knowledge_documents_embedding_status",
        "knowledge_documents",
        ["embedding_model", "vector_collection", "processing_status"],
    )
    op.alter_column("knowledge_documents", "indexed_chunk_count", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_knowledge_documents_embedding_status", table_name="knowledge_documents")
    op.drop_constraint("ck_knowledge_documents_indexed_chunk_count_non_negative", "knowledge_documents", type_="check")
    op.drop_column("knowledge_documents", "indexed_at")
    op.drop_column("knowledge_documents", "indexed_chunk_count")
    op.drop_column("knowledge_documents", "vector_collection")
    op.drop_column("knowledge_documents", "embedding_model")
    op.drop_column("knowledge_documents", "embedding_provider")
