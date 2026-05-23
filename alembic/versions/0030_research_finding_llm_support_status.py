"""add research finding llm support status

Revision ID: 0030_llm_support_status
Revises: 0029_retire_legacy_run_types
Create Date: 2026-05-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0030_llm_support_status"
down_revision: str | None = "0029_retire_legacy_run_types"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("research_findings", sa.Column("llm_support_status", sa.Text(), nullable=False, server_default="confirmed"))
    op.create_check_constraint(
        "ck_research_findings_llm_support_status",
        "research_findings",
        "llm_support_status in ('confirmed', 'unconfirmed')",
    )
    op.alter_column("research_findings", "llm_support_status", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_research_findings_llm_support_status", "research_findings", type_="check")
    op.drop_column("research_findings", "llm_support_status")
