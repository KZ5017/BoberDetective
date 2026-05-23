from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ClaimModel(Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint(
            "claim_type in ('witness_statement', 'document_fact', 'expert_opinion', "
            "'administrative_fact', 'inference_candidate', 'unknown')",
            name="ck_claims_claim_type",
        ),
        CheckConstraint(
            "source_validation_status in ('pending_source_validation', 'source_valid', 'source_invalid')",
            name="ck_claims_source_validation_status",
        ),
        CheckConstraint(
            "review_status in ('new', 'needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_claims_review_status",
        ),
        CheckConstraint("confidence is null or (confidence >= 0 and confidence <= 1)", name="ck_claims_confidence_range"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    claim_type: Mapped[str] = mapped_column(Text, nullable=False)
    claim_title: Mapped[str] = mapped_column(Text, nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    speaker_entity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    subject_entity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    related_event_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    claim_time_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_time_normalized: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(nullable=True)
    created_by_analysis_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=False)
    source_validation_status: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    analysis_run = relationship("AnalysisRunModel")
    case = relationship("CaseModel")


class ClaimSourceModel(Base):
    __tablename__ = "claim_sources"
    __table_args__ = (
        CheckConstraint("support_type in ('direct', 'indirect', 'contextual')", name="ck_claim_sources_support_type"),
        CheckConstraint("relevance_rank is null or relevance_rank >= 0", name="ck_claim_sources_relevance_rank_non_negative"),
        UniqueConstraint("claim_id", "source_reference_id", name="uq_claim_sources_claim_source_reference"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    claim_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False)
    source_reference_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("source_references.id"), nullable=False)
    relevance_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    support_type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    claim = relationship("ClaimModel")
    source_reference = relationship("SourceReferenceModel")
