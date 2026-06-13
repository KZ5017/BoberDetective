from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EventModel(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "event_type in ('call', 'meeting', 'statement', 'transfer', 'search', 'seizure', "
            "'document_created', 'document_received', 'other')",
            name="ck_events_event_type",
        ),
        CheckConstraint(
            "time_precision is null or time_precision in ('minute', 'hour', 'day', 'month', 'year', 'unknown')",
            name="ck_events_time_precision",
        ),
        CheckConstraint(
            "source_validation_status in ('pending_source_validation', 'source_valid', 'source_invalid')",
            name="ck_events_source_validation_status",
        ),
        CheckConstraint(
            "review_status in ('needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_events_review_status",
        ),
        CheckConstraint("confidence is null or (confidence >= 0 and confidence <= 1)", name="ck_events_confidence_range"),
        CheckConstraint("event_time_end is null or event_time_start is null or event_time_end >= event_time_start", name="ck_events_time_order"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_title: Mapped[str] = mapped_column(Text, nullable=False)
    event_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_time_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_time_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_precision: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_by_analysis_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=False)
    source_validation_status: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    analysis_run = relationship("AnalysisRunModel")
    case = relationship("CaseModel")


class EventSourceModel(Base):
    __tablename__ = "event_sources"
    __table_args__ = (
        CheckConstraint("support_type in ('direct', 'indirect', 'contextual')", name="ck_event_sources_support_type"),
        CheckConstraint("relevance_rank is null or relevance_rank >= 0", name="ck_event_sources_relevance_rank_non_negative"),
        UniqueConstraint("event_id", "source_reference_id", name="uq_event_sources_event_source_reference"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    source_reference_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("source_references.id"), nullable=False)
    relevance_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    support_type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    event = relationship("EventModel")
    source_reference = relationship("SourceReferenceModel")
