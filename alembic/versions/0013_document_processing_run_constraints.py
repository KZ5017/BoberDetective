"""document processing run constraints

Revision ID: 0013_processing_runs
Revises: 0012_missing_item_candidates
Create Date: 2026-05-13
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0013_processing_runs"
down_revision: str | None = "0012_missing_item_candidates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RUN_TYPE_CONSTRAINT = (
    "run_type in ("
    "'import_document', 'inspect_document', 'parse_document', 'ocr_document', 'extract_pages', "
    "'chunk_document', 'embed_chunks', 'index_chunks', 'validate_document_processing', "
    "'extract_entities', 'extract_events', "
    "'extract_claims', 'detect_contradictions', 'detect_missing_items', 'summarize_case', "
    "'answer_with_citations', 'export_bundle', 'llm_smoke'"
    ")"
)

OLD_RUN_TYPE_CONSTRAINT = (
    "run_type in ("
    "'parse_document', 'ocr_document', 'chunk_document', 'extract_entities', 'extract_events', "
    "'extract_claims', 'detect_contradictions', 'detect_missing_items', 'summarize_case', "
    "'answer_with_citations', 'export_bundle', 'llm_smoke'"
    ")"
)

OUTPUT_TYPE_CONSTRAINT = (
    "output_type in ('document', 'page', 'chunk', 'entity', 'mention', 'event', 'claim', 'contradiction_candidate', "
    "'missing_item_candidate', 'export', 'summary_item', 'source_reference')"
)

OLD_OUTPUT_TYPE_CONSTRAINT = (
    "output_type in ('entity', 'mention', 'event', 'claim', 'contradiction_candidate', "
    "'missing_item_candidate', 'export', 'summary_item', 'source_reference')"
)


def upgrade() -> None:
    op.drop_constraint("ck_analysis_runs_run_type", "analysis_runs", type_="check")
    op.create_check_constraint("ck_analysis_runs_run_type", "analysis_runs", RUN_TYPE_CONSTRAINT)

    op.drop_constraint("ck_analysis_run_outputs_output_type", "analysis_run_outputs", type_="check")
    op.create_check_constraint("ck_analysis_run_outputs_output_type", "analysis_run_outputs", OUTPUT_TYPE_CONSTRAINT)


def downgrade() -> None:
    op.drop_constraint("ck_analysis_run_outputs_output_type", "analysis_run_outputs", type_="check")
    op.create_check_constraint("ck_analysis_run_outputs_output_type", "analysis_run_outputs", OLD_OUTPUT_TYPE_CONSTRAINT)

    op.drop_constraint("ck_analysis_runs_run_type", "analysis_runs", type_="check")
    op.create_check_constraint("ck_analysis_runs_run_type", "analysis_runs", OLD_RUN_TYPE_CONSTRAINT)
