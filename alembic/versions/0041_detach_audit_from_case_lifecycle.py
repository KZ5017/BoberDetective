"""detach audit events from case lifecycle foreign keys

Revision ID: 0041_detach_audit_lifecycle
Revises: 0040_drop_db_text_cols
Create Date: 2026-05-29
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0041_detach_audit_lifecycle"
down_revision: str | None = "0040_drop_db_text_cols"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("audit_events_case_id_fkey", "audit_events", type_="foreignkey")
    op.drop_constraint("fk_audit_events_analysis_run_id_analysis_runs", "audit_events", type_="foreignkey")


def downgrade() -> None:
    op.create_foreign_key(
        "fk_audit_events_analysis_run_id_analysis_runs",
        "audit_events",
        "analysis_runs",
        ["analysis_run_id"],
        ["id"],
    )
    op.create_foreign_key(
        "audit_events_case_id_fkey",
        "audit_events",
        "cases",
        ["case_id"],
        ["id"],
    )
