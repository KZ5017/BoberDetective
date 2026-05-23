"""retire legacy analysis run type names

Revision ID: 0029_retire_legacy_run_types
Revises: 0028_structured_event_time
Create Date: 2026-05-23
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0029_retire_legacy_run_types"
down_revision: str | None = "0028_structured_event_time"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LEGACY_RAW_RUN_TYPES = (
    "extract_entities",
    "extract_events",
    "extract_claims",
    "detect_missing_items",
    "summarize_case",
)


def upgrade() -> None:
    op.drop_constraint("ck_analysis_runs_run_type", "analysis_runs", type_="check")
    legacy_values = ", ".join(f"'{value}'" for value in LEGACY_RAW_RUN_TYPES)
    op.execute(
        f"""
        update analysis_runs
        set input_parameters = coalesce(input_parameters, '{{}}'::jsonb)
            || jsonb_build_object('retired_original_run_type', run_type),
            run_type = 'retired_analysis_module'
        where run_type in ({legacy_values})
        """
    )
    op.execute(
        """
        update analysis_runs
        set input_parameters = coalesce(input_parameters, '{}'::jsonb)
            || jsonb_build_object('previous_run_type', run_type),
            run_type = 'detect_contradiction_candidates'
        where run_type = 'detect_contradictions'
        """
    )
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


def downgrade() -> None:
    op.drop_constraint("ck_analysis_runs_run_type", "analysis_runs", type_="check")
    op.execute(
        """
        update analysis_runs
        set run_type = input_parameters->>'retired_original_run_type'
        where run_type = 'retired_analysis_module'
            and input_parameters ? 'retired_original_run_type'
        """
    )
    op.execute(
        """
        update analysis_runs
        set run_type = 'detect_contradictions'
        where run_type = 'detect_contradiction_candidates'
            and input_parameters->>'previous_run_type' = 'detect_contradictions'
        """
    )
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
