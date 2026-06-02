"""add document collections

Revision ID: 0043_document_collections
Revises: 0042_doc_proc_person_only
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0043_document_collections"
down_revision: str | None = "0042_doc_proc_person_only"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_collections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_document_collections_name_nonblank"),
        sa.CheckConstraint("length(name) <= 120", name="ck_document_collections_name_length"),
        sa.CheckConstraint("description is null or length(description) <= 1000", name="ck_document_collections_description_length"),
        sa.CheckConstraint("color is null or color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_document_collections_color_hex"),
        sa.CheckConstraint("sort_order >= 0", name="ck_document_collections_sort_order_non_negative"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "create unique index uq_document_collections_case_name_lower "
        "on document_collections (case_id, lower(name))"
    )
    op.create_index(
        "ix_document_collections_case_sort",
        "document_collections",
        ["case_id", "sort_order", "name"],
    )

    op.create_table(
        "document_collection_memberships",
        sa.Column("collection_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("added_by_user_id", sa.UUID(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["added_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["collection_id"], ["document_collections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("collection_id", "document_id"),
    )
    op.create_index(
        "ix_document_collection_memberships_document",
        "document_collection_memberships",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_collection_memberships_document", table_name="document_collection_memberships")
    op.drop_table("document_collection_memberships")
    op.drop_index("ix_document_collections_case_sort", table_name="document_collections")
    op.drop_index("uq_document_collections_case_name_lower", table_name="document_collections")
    op.drop_table("document_collections")
