"""add search findings analysis run type

Revision ID: 0022_search_findings_run_type
Revises: 0021_research_findings
Create Date: 2026-05-20
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0022_search_findings_run_type"
down_revision: str | None = "0021_research_findings"
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
        "'extract_entities', 'extract_events', "
        "'extract_claims', 'detect_contradictions', 'detect_missing_items', 'summarize_case', "
        "'search_findings', 'answer_with_citations', 'export_bundle', 'llm_smoke', 'manual_entry'"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_analysis_runs_run_type", "analysis_runs", type_="check")
    op.create_check_constraint(
        "ck_analysis_runs_run_type",
        "analysis_runs",
        "run_type in ("
        "'import_document', 'inspect_document', 'parse_document', 'ocr_document', 'extract_pages', "
        "'chunk_document', 'embed_chunks', 'index_chunks', 'validate_document_processing', "
        "'extract_entities', 'extract_events', "
        "'extract_claims', 'detect_contradictions', 'detect_missing_items', 'summarize_case', "
        "'answer_with_citations', 'export_bundle', 'llm_smoke', 'manual_entry'"
        ")",
    )
