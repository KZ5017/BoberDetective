"""events

Revision ID: 0007_events
Revises: 0006_human_reviews
Create Date: 2026-05-12 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_events"
down_revision: str | None = "0006_human_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event_title", sa.Text(), nullable=False),
        sa.Column("event_description", sa.Text(), nullable=True),
        sa.Column("event_time_raw", sa.Text(), nullable=True),
        sa.Column("event_time_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_time_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_precision", sa.Text(), nullable=True),
        sa.Column("location_text", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_by_analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_validation_status", sa.Text(), nullable=False),
        sa.Column("review_status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type in ('call', 'meeting', 'statement', 'transfer', 'search', 'seizure', "
            "'document_created', 'document_received', 'other')",
            name="ck_events_event_type",
        ),
        sa.CheckConstraint(
            "time_precision is null or time_precision in ('exact', 'minute', 'hour', 'day', 'month', 'unknown')",
            name="ck_events_time_precision",
        ),
        sa.CheckConstraint(
            "source_validation_status in ('pending_source_validation', 'source_valid', 'source_invalid')",
            name="ck_events_source_validation_status",
        ),
        sa.CheckConstraint(
            "review_status in ('new', 'needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_events_review_status",
        ),
        sa.CheckConstraint("confidence is null or (confidence >= 0 and confidence <= 1)", name="ck_events_confidence_range"),
        sa.CheckConstraint("event_time_end is null or event_time_start is null or event_time_end >= event_time_start", name="ck_events_time_order"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], name="fk_events_case_id_cases"),
        sa.ForeignKeyConstraint(["created_by_analysis_run_id"], ["analysis_runs.id"], name="fk_events_created_by_analysis_run_id_analysis_runs"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_case_time_start", "events", ["case_id", "event_time_start"])
    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_review_status", "events", ["review_status"])
    op.create_index("ix_events_source_validation_status", "events", ["source_validation_status"])

    op.create_table(
        "event_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relevance_rank", sa.Integer(), nullable=True),
        sa.Column("support_type", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("support_type in ('direct', 'indirect', 'contextual')", name="ck_event_sources_support_type"),
        sa.CheckConstraint("relevance_rank is null or relevance_rank >= 0", name="ck_event_sources_relevance_rank_non_negative"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_event_sources_event_id_events"),
        sa.ForeignKeyConstraint(["source_reference_id"], ["source_references.id"], name="fk_event_sources_source_reference_id_source_references"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "source_reference_id", name="uq_event_sources_event_source_reference"),
    )
    op.create_index("ix_event_sources_event_id", "event_sources", ["event_id"])
    op.create_index("ix_event_sources_source_reference_id", "event_sources", ["source_reference_id"])


def downgrade() -> None:
    op.drop_index("ix_event_sources_source_reference_id", table_name="event_sources")
    op.drop_index("ix_event_sources_event_id", table_name="event_sources")
    op.drop_table("event_sources")
    op.drop_index("ix_events_source_validation_status", table_name="events")
    op.drop_index("ix_events_review_status", table_name="events")
    op.drop_index("ix_events_event_type", table_name="events")
    op.drop_index("ix_events_case_time_start", table_name="events")
    op.drop_table("events")
