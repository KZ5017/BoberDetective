from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SummaryItemModel(Base):
    __tablename__ = "summary_items"
    __table_args__ = (
        CheckConstraint(
            "summary_type in ('case_overview', 'document_summary', 'timeline_summary', 'entity_summary', 'caution_note', 'other')",
            name="ck_summary_items_summary_type",
        ),
        CheckConstraint(
            "source_validation_status in ('pending_source_validation', 'source_valid', 'source_invalid')",
            name="ck_summary_items_source_validation_status",
        ),
        CheckConstraint(
            "review_status in ('new', 'needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_summary_items_review_status",
        ),
        CheckConstraint("confidence is null or (confidence >= 0 and confidence <= 1)", name="ck_summary_items_confidence_range"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    summary_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_by_analysis_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=False)
    source_validation_status: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    analysis_run = relationship("AnalysisRunModel")
    case = relationship("CaseModel")


class SummaryItemSourceModel(Base):
    __tablename__ = "summary_item_sources"
    __table_args__ = (
        CheckConstraint("support_type in ('direct', 'indirect', 'contextual')", name="ck_summary_item_sources_support_type"),
        CheckConstraint(
            "relevance_rank is null or relevance_rank >= 0",
            name="ck_summary_item_sources_relevance_rank_non_negative",
        ),
        UniqueConstraint("summary_item_id", "source_reference_id", name="uq_summary_item_sources_item_source_reference"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    summary_item_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("summary_items.id"), nullable=False)
    source_reference_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("source_references.id"), nullable=False)
    relevance_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    support_type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    summary_item = relationship("SummaryItemModel")
    source_reference = relationship("SourceReferenceModel")
