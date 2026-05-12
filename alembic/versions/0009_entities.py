"""entities

Revision ID: 0009_entities
Revises: 0008_exports
Create Date: 2026-05-12 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_entities"
down_revision: str | None = "0008_exports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_by_analysis_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "entity_type in ('person', 'organization', 'location', 'phone', 'email', 'license_plate', "
            "'case_reference', 'money_amount', 'document_reference', 'other')",
            name="ck_entities_entity_type",
        ),
        sa.CheckConstraint("confidence is null or (confidence >= 0 and confidence <= 1)", name="ck_entities_confidence_range"),
        sa.CheckConstraint(
            "review_status in ('new', 'needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_entities_review_status",
        ),
        sa.CheckConstraint(
            "created_by_analysis_run_id is not null or created_by_user_id is not null",
            name="ck_entities_creator_required",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], name="fk_entities_case_id_cases"),
        sa.ForeignKeyConstraint(["created_by_analysis_run_id"], ["analysis_runs.id"], name="fk_entities_created_by_analysis_run_id_analysis_runs"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_entities_created_by_user_id_users"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entities_case_type", "entities", ["case_id", "entity_type"])
    op.create_index("ix_entities_canonical_name", "entities", ["canonical_name"])
    op.create_index("ix_entities_normalized_value", "entities", ["normalized_value"])
    op.create_index("ix_entities_review_status", "entities", ["review_status"])

    op.create_table(
        "entity_mentions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("surface_text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_by_analysis_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("page_number is null or page_number >= 1", name="ck_entity_mentions_page_number_positive"),
        sa.CheckConstraint("confidence is null or (confidence >= 0 and confidence <= 1)", name="ck_entity_mentions_confidence_range"),
        sa.CheckConstraint("char_end is null or char_start is null or char_end >= char_start", name="ck_entity_mentions_char_end_after_start"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], name="fk_entity_mentions_case_id_cases"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], name="fk_entity_mentions_entity_id_entities"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_entity_mentions_document_id_documents"),
        sa.ForeignKeyConstraint(["page_id"], ["document_pages.id"], name="fk_entity_mentions_page_id_document_pages"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], name="fk_entity_mentions_chunk_id_document_chunks"),
        sa.ForeignKeyConstraint(["source_reference_id"], ["source_references.id"], name="fk_entity_mentions_source_reference_id_source_references"),
        sa.ForeignKeyConstraint(["created_by_analysis_run_id"], ["analysis_runs.id"], name="fk_entity_mentions_created_by_analysis_run_id_analysis_runs"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entity_mentions_entity_id", "entity_mentions", ["entity_id"])
    op.create_index("ix_entity_mentions_document_page", "entity_mentions", ["document_id", "page_number"])
    op.create_index("ix_entity_mentions_chunk_id", "entity_mentions", ["chunk_id"])


def downgrade() -> None:
    op.drop_index("ix_entity_mentions_chunk_id", table_name="entity_mentions")
    op.drop_index("ix_entity_mentions_document_page", table_name="entity_mentions")
    op.drop_index("ix_entity_mentions_entity_id", table_name="entity_mentions")
    op.drop_table("entity_mentions")
    op.drop_index("ix_entities_review_status", table_name="entities")
    op.drop_index("ix_entities_normalized_value", table_name="entities")
    op.drop_index("ix_entities_canonical_name", table_name="entities")
    op.drop_index("ix_entities_case_type", table_name="entities")
    op.drop_table("entities")
