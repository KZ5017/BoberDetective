"""limit document processing to person profile

Revision ID: 0042_doc_proc_person_only
Revises: 0041_detach_audit_lifecycle
Create Date: 2026-05-31
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0042_doc_proc_person_only"
down_revision: str | None = "0041_detach_audit_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("delete from document_processing_items where profile_key <> 'person_search_seeds' or item_kind <> 'person'")
    op.drop_constraint("ck_document_processing_items_profile_key", "document_processing_items", type_="check")
    op.drop_constraint("ck_document_processing_items_item_kind", "document_processing_items", type_="check")
    op.create_check_constraint(
        "ck_document_processing_items_profile_key",
        "document_processing_items",
        "profile_key in ('person_search_seeds')",
    )
    op.create_check_constraint(
        "ck_document_processing_items_item_kind",
        "document_processing_items",
        "item_kind in ('person')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_document_processing_items_item_kind", "document_processing_items", type_="check")
    op.drop_constraint("ck_document_processing_items_profile_key", "document_processing_items", type_="check")
    op.create_check_constraint(
        "ck_document_processing_items_profile_key",
        "document_processing_items",
        "profile_key in ('person_search_seeds', 'entity_search_seeds')",
    )
    op.create_check_constraint(
        "ck_document_processing_items_item_kind",
        "document_processing_items",
        "item_kind in ('person', 'organization', 'location', 'document_reference', 'case_reference', 'attachment', 'other')",
    )
