"""add structured document taxonomy fields

Revision ID: 0018_document_taxonomy
Revises: 0017_text_review_status
Create Date: 2026-05-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0018_document_taxonomy"
down_revision: str | None = "0017_text_review_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index("ix_documents_case_document_taxonomy", table_name="documents")
    op.drop_index("ix_documents_case_document_type_code", table_name="documents")
    op.drop_index("ix_documents_case_document_group_code", table_name="documents")
    op.drop_constraint("ck_documents_document_type_code_non_empty", "documents", type_="check")
    op.drop_constraint("ck_documents_document_group_code_non_empty", "documents", type_="check")
    op.drop_column("documents", "document_type_code")
    op.drop_column("documents", "document_group_code")
