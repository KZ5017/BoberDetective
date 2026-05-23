"""use structured event time and drop free-text event location

Revision ID: 0028_structured_event_time
Revises: 0027_drop_expected_document_type
Create Date: 2026-05-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0028_structured_event_time"
down_revision: str | None = "0027_drop_expected_document_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_events_time_precision", "events", type_="check")
    op.create_check_constraint(
        "ck_events_time_precision",
        "events",
        "time_precision is null or time_precision in ('minute', 'hour', 'day', 'month', 'year', 'unknown')",
    )
    op.drop_column("events", "event_time_raw")
    op.drop_column("events", "location_text")


def downgrade() -> None:
    op.add_column("events", sa.Column("event_time_raw", sa.Text(), nullable=True))
    op.add_column("events", sa.Column("location_text", sa.Text(), nullable=True))
    op.drop_constraint("ck_events_time_precision", "events", type_="check")
    op.create_check_constraint(
        "ck_events_time_precision",
        "events",
        "time_precision is null or time_precision in ('exact', 'minute', 'hour', 'day', 'month', 'unknown')",
    )
