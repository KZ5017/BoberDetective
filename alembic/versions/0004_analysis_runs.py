"""add analysis run provenance tables

Revision ID: 0004_analysis_runs
Revises: 0003_source_references
Create Date: 2026-05-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004_analysis_runs"
down_revision: str | None = "0003_source_references"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_type", sa.Text(), nullable=True),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("prompt_template_name", sa.Text(), nullable=True),
        sa.Column("prompt_template_version", sa.Text(), nullable=True),
        sa.Column("input_parameters", postgresql.JSONB(), nullable=True),
        sa.Column("raw_prompt_text", sa.Text(), nullable=True),
        sa.Column("output_schema_name", sa.Text(), nullable=True),
        sa.Column("output_schema_version", sa.Text(), nullable=True),
        sa.Column("retrieval_strategy", sa.Text(), nullable=True),
        sa.Column("validation_status", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "run_type in ("
            "'parse_document', 'ocr_document', 'chunk_document', 'extract_entities', 'extract_events', "
            "'extract_claims', 'detect_contradictions', 'detect_missing_items', 'summarize_case', "
            "'answer_with_citations', 'export_bundle', 'llm_smoke'"
            ")",
            name="ck_analysis_runs_run_type",
        ),
        sa.CheckConstraint("status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')", name="ck_analysis_runs_status"),
        sa.CheckConstraint(
            "validation_status is null or validation_status in ('not_applicable', 'passed', 'failed', 'warning')",
            name="ck_analysis_runs_validation_status",
        ),
        sa.CheckConstraint("finished_at is null or finished_at >= started_at", name="ck_analysis_runs_finished_after_started"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["started_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_analysis_runs_case_type_started", "analysis_runs", ["case_id", "run_type", sa.text("started_at DESC")])
    op.create_index("ix_analysis_runs_status", "analysis_runs", ["status"])
    op.create_index("ix_analysis_runs_provider_model", "analysis_runs", ["provider_type", "model_name", "model_version"])

    op.create_table(
        "analysis_run_inputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_type", sa.Text(), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("related_object_type", sa.Text(), nullable=True),
        sa.Column("related_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "input_type in ('document', 'page', 'chunk', 'entity', 'claim', 'event', 'query_text', 'filter')",
            name="ck_analysis_run_inputs_input_type",
        ),
        sa.CheckConstraint("sequence_no >= 0", name="ck_analysis_run_inputs_sequence_non_negative"),
        sa.CheckConstraint(
            "document_id is not null or page_id is not null or chunk_id is not null or payload_json is not null or "
            "(related_object_type is not null and related_object_id is not null)",
            name="ck_analysis_run_inputs_has_carrier",
        ),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["page_id"], ["document_pages.id"]),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"]),
    )
    op.create_index("ix_analysis_run_inputs_analysis_run_id", "analysis_run_inputs", ["analysis_run_id"])
    op.create_index("ix_analysis_run_inputs_document_id", "analysis_run_inputs", ["document_id"])
    op.create_index("ix_analysis_run_inputs_page_id", "analysis_run_inputs", ["page_id"])
    op.create_index("ix_analysis_run_inputs_chunk_id", "analysis_run_inputs", ["chunk_id"])
    op.create_index("ix_analysis_run_inputs_related_object", "analysis_run_inputs", ["related_object_type", "related_object_id"])

    op.create_table(
        "analysis_run_outputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("output_type", sa.Text(), nullable=False),
        sa.Column("output_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("output_position", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "output_type in ('entity', 'mention', 'event', 'claim', 'contradiction_candidate', "
            "'missing_item_candidate', 'export', 'summary_item', 'source_reference')",
            name="ck_analysis_run_outputs_output_type",
        ),
        sa.CheckConstraint("output_position is null or output_position >= 0", name="ck_analysis_run_outputs_position_non_negative"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"]),
    )
    op.create_index("ix_analysis_run_outputs_analysis_run_id", "analysis_run_outputs", ["analysis_run_id"])
    op.create_index("ix_analysis_run_outputs_output_object", "analysis_run_outputs", ["output_type", "output_object_id"])

    op.create_foreign_key(
        "fk_audit_events_analysis_run_id_analysis_runs",
        "audit_events",
        "analysis_runs",
        ["analysis_run_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_source_references_extraction_run_id_analysis_runs",
        "source_references",
        "analysis_runs",
        ["extraction_run_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_source_references_extraction_run_id_analysis_runs", "source_references", type_="foreignkey")
    op.drop_constraint("fk_audit_events_analysis_run_id_analysis_runs", "audit_events", type_="foreignkey")

    op.drop_index("ix_analysis_run_outputs_output_object", table_name="analysis_run_outputs")
    op.drop_index("ix_analysis_run_outputs_analysis_run_id", table_name="analysis_run_outputs")
    op.drop_table("analysis_run_outputs")

    op.drop_index("ix_analysis_run_inputs_related_object", table_name="analysis_run_inputs")
    op.drop_index("ix_analysis_run_inputs_chunk_id", table_name="analysis_run_inputs")
    op.drop_index("ix_analysis_run_inputs_page_id", table_name="analysis_run_inputs")
    op.drop_index("ix_analysis_run_inputs_document_id", table_name="analysis_run_inputs")
    op.drop_index("ix_analysis_run_inputs_analysis_run_id", table_name="analysis_run_inputs")
    op.drop_table("analysis_run_inputs")

    op.drop_index("ix_analysis_runs_provider_model", table_name="analysis_runs")
    op.drop_index("ix_analysis_runs_status", table_name="analysis_runs")
    op.drop_index("ix_analysis_runs_case_type_started", table_name="analysis_runs")
    op.drop_table("analysis_runs")
