"""manual entry run type

Revision ID: 0016_manual_entry
Revises: 0015_reattach_target
Create Date: 2026-05-15
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0016_manual_entry"
down_revision: str | None = "0015_reattach_target"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RUN_TYPE_CONSTRAINT = (
    "run_type in ("
    "'import_document', 'inspect_document', 'parse_document', 'ocr_document', 'extract_pages', "
    "'chunk_document', 'embed_chunks', 'index_chunks', 'validate_document_processing', "
    "'extract_entities', 'extract_events', "
    "'extract_claims', 'detect_contradictions', 'detect_missing_items', 'summarize_case', "
    "'answer_with_citations', 'export_bundle', 'llm_smoke', 'manual_entry'"
    ")"
)

OLD_RUN_TYPE_CONSTRAINT = (
    "run_type in ("
    "'import_document', 'inspect_document', 'parse_document', 'ocr_document', 'extract_pages', "
    "'chunk_document', 'embed_chunks', 'index_chunks', 'validate_document_processing', "
    "'extract_entities', 'extract_events', "
    "'extract_claims', 'detect_contradictions', 'detect_missing_items', 'summarize_case', "
    "'answer_with_citations', 'export_bundle', 'llm_smoke'"
    ")"
)


def upgrade() -> None:
    op.drop_constraint("ck_analysis_runs_run_type", "analysis_runs", type_="check")
    op.create_check_constraint("ck_analysis_runs_run_type", "analysis_runs", RUN_TYPE_CONSTRAINT)


def downgrade() -> None:
    op.drop_constraint("ck_analysis_runs_run_type", "analysis_runs", type_="check")
    op.create_check_constraint("ck_analysis_runs_run_type", "analysis_runs", OLD_RUN_TYPE_CONSTRAINT)
