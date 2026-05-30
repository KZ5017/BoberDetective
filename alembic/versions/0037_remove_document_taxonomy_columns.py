"""remove retired document taxonomy columns

Revision ID: 0037_remove_doc_taxonomy
Revises: 0036_search_entries
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0037_remove_doc_taxonomy"
down_revision: str | None = "0036_search_entries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_document_search_entries_taxonomy_current", table_name="document_search_entries")
    op.drop_column("document_search_entries", "document_type_code")
    op.drop_column("document_search_entries", "document_group_code")

    op.drop_index("ix_documents_case_document_taxonomy", table_name="documents")
    op.drop_index("ix_documents_case_document_type_code", table_name="documents")
    op.drop_index("ix_documents_case_document_group_code", table_name="documents")
    op.drop_constraint("ck_documents_document_type_code_non_empty", "documents", type_="check")
    op.drop_constraint("ck_documents_document_group_code_non_empty", "documents", type_="check")
    op.drop_column("documents", "document_type_code")
    op.drop_column("documents", "document_group_code")


def downgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("document_group_code", sa.Text(), nullable=False, server_default="uncategorized"),
    )
    op.add_column(
        "documents",
        sa.Column("document_type_code", sa.Text(), nullable=False, server_default="uncategorized"),
    )
    op.create_check_constraint(
        "ck_documents_document_group_code_non_empty",
        "documents",
        "length(trim(document_group_code)) > 0",
    )
    op.create_check_constraint(
        "ck_documents_document_type_code_non_empty",
        "documents",
        "length(trim(document_type_code)) > 0",
    )
    op.create_index("ix_documents_case_document_group_code", "documents", ["case_id", "document_group_code"])
    op.create_index("ix_documents_case_document_type_code", "documents", ["case_id", "document_type_code"])
    op.create_index(
        "ix_documents_case_document_taxonomy",
        "documents",
        ["case_id", "document_group_code", "document_type_code"],
    )

    op.add_column(
        "document_search_entries",
        sa.Column("document_group_code", sa.Text(), nullable=False, server_default="uncategorized"),
    )
    op.add_column(
        "document_search_entries",
        sa.Column("document_type_code", sa.Text(), nullable=False, server_default="uncategorized"),
    )
    op.create_index(
        "ix_document_search_entries_taxonomy_current",
        "document_search_entries",
        ["case_id", "document_group_code", "document_type_code", "is_current"],
    )
