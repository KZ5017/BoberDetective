"""add text review document status

Revision ID: 0017_text_review_status
Revises: 0016_manual_entry
Create Date: 2026-05-16
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0017_text_review_status"
down_revision: str | None = "0016_manual_entry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_DOCUMENT_STATUS_CONSTRAINT = (
    "processing_status in ('pending', 'processing', 'processed', 'failed', 'review_required', 'text_review_required')"
)
OLD_DOCUMENT_STATUS_CONSTRAINT = (
    "processing_status in ('pending', 'processing', 'processed', 'failed', 'review_required')"
)


def upgrade() -> None:
    op.drop_constraint("ck_documents_processing_status", "documents", type_="check")
    op.create_check_constraint("ck_documents_processing_status", "documents", NEW_DOCUMENT_STATUS_CONSTRAINT)


def downgrade() -> None:
    op.execute("update documents set processing_status = 'review_required' where processing_status = 'text_review_required'")
    op.drop_constraint("ck_documents_processing_status", "documents", type_="check")
    op.create_check_constraint("ck_documents_processing_status", "documents", OLD_DOCUMENT_STATUS_CONSTRAINT)
