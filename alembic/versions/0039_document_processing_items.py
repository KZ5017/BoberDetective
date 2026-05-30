"""add document processing items

Revision ID: 0039_doc_proc_items
Revises: 0038_nullable_text_fields
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0039_doc_proc_items"
down_revision: str | None = "0038_nullable_text_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_analysis_runs_run_type", "analysis_runs", type_="check")
    op.create_check_constraint(
        "ck_analysis_runs_run_type",
        "analysis_runs",
        "run_type in ("
        "'import_document', 'inspect_document', 'parse_document', 'ocr_document', 'extract_pages', "
        "'chunk_document', 'embed_chunks', 'index_chunks', 'validate_document_processing', "
        "'retired_analysis_module', 'detect_contradiction_candidates', "
        "'search_findings', 'full_document_processing', 'answer_with_citations', 'export_bundle', "
        "'llm_smoke', 'manual_entry'"
        ")",
    )

    op.drop_constraint("ck_analysis_run_outputs_output_type", "analysis_run_outputs", type_="check")
    op.create_check_constraint(
        "ck_analysis_run_outputs_output_type",
        "analysis_run_outputs",
        "output_type in ('document', 'page', 'chunk', 'entity', 'mention', 'event', 'claim', "
        "'contradiction_candidate', 'missing_item_candidate', 'export', 'source_reference', "
        "'research_finding', 'document_processing_item')",
    )

    op.create_table(
        "document_processing_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_key", sa.Text(), nullable=False),
        sa.Column("item_kind", sa.Text(), nullable=False),
        sa.Column("display_label", sa.Text(), nullable=False),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("mentioned_forms_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("source_supported_details_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("relationships_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("recommended_search_focus", sa.Text(), nullable=True),
        sa.Column("alternative_search_focuses_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("source_evidence_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("work_status", sa.Text(), server_default="active", nullable=False),
        sa.Column("target_object_type", sa.Text(), nullable=True),
        sa.Column("target_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("profile_key in ('person_search_seeds', 'entity_search_seeds')", name="ck_document_processing_items_profile_key"),
        sa.CheckConstraint(
            "item_kind in ('person', 'organization', 'location', 'document_reference', 'case_reference', 'attachment', 'other')",
            name="ck_document_processing_items_item_kind",
        ),
        sa.CheckConstraint("length(trim(display_label)) > 0", name="ck_document_processing_items_display_label_not_blank"),
        sa.CheckConstraint("jsonb_typeof(mentioned_forms_json) = 'array'", name="ck_document_processing_items_mentioned_forms_array"),
        sa.CheckConstraint(
            "jsonb_typeof(source_supported_details_json) = 'array'",
            name="ck_document_processing_items_supported_details_array",
        ),
        sa.CheckConstraint("jsonb_typeof(relationships_json) = 'array'", name="ck_document_processing_items_relationships_array"),
        sa.CheckConstraint(
            "jsonb_typeof(alternative_search_focuses_json) = 'array'",
            name="ck_document_processing_items_alt_focuses_array",
        ),
        sa.CheckConstraint("jsonb_typeof(source_evidence_json) = 'array'", name="ck_document_processing_items_source_evidence_array"),
        sa.CheckConstraint(
            "work_status in ('active', 'set_aside', 'converted', 'deleted')",
            name="ck_document_processing_items_work_status",
        ),
        sa.CheckConstraint(
            "target_object_type is null or target_object_type in ('claim', 'entity', 'event', 'missing_item_candidate', 'research_finding')",
            name="ck_document_processing_items_target_type",
        ),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_processing_items_case_document", "document_processing_items", ["case_id", "document_id"])
    op.create_index("ix_document_processing_items_document_status", "document_processing_items", ["document_id", "work_status"])
    op.create_index("ix_document_processing_items_profile", "document_processing_items", ["profile_key"])
    op.create_index("ix_document_processing_items_run", "document_processing_items", ["analysis_run_id"])


def downgrade() -> None:
    op.drop_index("ix_document_processing_items_run", table_name="document_processing_items")
    op.drop_index("ix_document_processing_items_profile", table_name="document_processing_items")
    op.drop_index("ix_document_processing_items_document_status", table_name="document_processing_items")
    op.drop_index("ix_document_processing_items_case_document", table_name="document_processing_items")
    op.drop_table("document_processing_items")

    op.drop_constraint("ck_analysis_run_outputs_output_type", "analysis_run_outputs", type_="check")
    op.create_check_constraint(
        "ck_analysis_run_outputs_output_type",
        "analysis_run_outputs",
        "output_type in ('document', 'page', 'chunk', 'entity', 'mention', 'event', 'claim', "
        "'contradiction_candidate', 'missing_item_candidate', 'export', 'source_reference', 'research_finding')",
    )

    op.drop_constraint("ck_analysis_runs_run_type", "analysis_runs", type_="check")
    op.create_check_constraint(
        "ck_analysis_runs_run_type",
        "analysis_runs",
        "run_type in ("
        "'import_document', 'inspect_document', 'parse_document', 'ocr_document', 'extract_pages', "
        "'chunk_document', 'embed_chunks', 'index_chunks', 'validate_document_processing', "
        "'retired_analysis_module', 'detect_contradiction_candidates', "
        "'search_findings', 'answer_with_citations', 'export_bundle', 'llm_smoke', 'manual_entry'"
        ")",
    )
