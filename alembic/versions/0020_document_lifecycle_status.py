"""document lifecycle status

Revision ID: 0020_document_lifecycle_status
Revises: 0019_drop_legacy_document_type
Create Date: 2026-05-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0020_document_lifecycle_status"
down_revision: str | None = "0019_drop_legacy_document_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("lifecycle_status", sa.Text(), nullable=False, server_default="active"))
    op.add_column("documents", sa.Column("lifecycle_status_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "documents",
        sa.Column("lifecycle_status_changed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("documents", sa.Column("lifecycle_status_reason", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_documents_lifecycle_status",
        "documents",
        "lifecycle_status in ('active', 'excluded', 'archived')",
    )
    op.create_foreign_key(
        "fk_documents_lifecycle_status_changed_by_user_id_users",
        "documents",
        "users",
        ["lifecycle_status_changed_by_user_id"],
        ["id"],
    )
    op.alter_column("documents", "lifecycle_status", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_documents_lifecycle_status_changed_by_user_id_users", "documents", type_="foreignkey")
    op.drop_constraint("ck_documents_lifecycle_status", "documents", type_="check")
    op.drop_column("documents", "lifecycle_status_reason")
    op.drop_column("documents", "lifecycle_status_changed_by_user_id")
    op.drop_column("documents", "lifecycle_status_changed_at")
    op.drop_column("documents", "lifecycle_status")
