from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ContradictionCandidateModel(Base):
    __tablename__ = "contradiction_candidates"
    __table_args__ = (
        CheckConstraint(
            "contradiction_type in ('time_conflict', 'location_conflict', 'identity_conflict', "
            "'document_mismatch', 'amount_conflict', 'other')",
            name="ck_contradiction_candidates_type",
        ),
        CheckConstraint(
            "severity_hint is null or severity_hint in ('low', 'medium', 'high')",
            name="ck_contradiction_candidates_severity_hint",
        ),
        CheckConstraint(
            "source_validation_status in ('pending_source_validation', 'source_valid', 'source_invalid')",
            name="ck_contradiction_candidates_source_validation_status",
        ),
        CheckConstraint(
            "review_status in ('needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_contradiction_candidates_review_status",
        ),
        CheckConstraint(
            "confidence is null or (confidence >= 0 and confidence <= 1)",
            name="ck_contradiction_candidates_confidence_range",
        ),
        CheckConstraint(
            "(claim_id_a is not null and claim_id_b is not null) or (event_id_a is not null and event_id_b is not null)",
            name="ck_contradiction_candidates_has_pair",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    contradiction_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    claim_id_a: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("claims.id"), nullable=True)
    claim_id_b: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("claims.id"), nullable=True)
    event_id_a: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=True)
    event_id_b: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    severity_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_analysis_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=False)
    source_validation_status: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    analysis_run = relationship("AnalysisRunModel")
    case = relationship("CaseModel")
    claim_a = relationship("ClaimModel", foreign_keys=[claim_id_a])
    claim_b = relationship("ClaimModel", foreign_keys=[claim_id_b])
    event_a = relationship("EventModel", foreign_keys=[event_id_a])
    event_b = relationship("EventModel", foreign_keys=[event_id_b])


class ContradictionCandidateSourceModel(Base):
    __tablename__ = "contradiction_candidate_sources"
    __table_args__ = (
        CheckConstraint(
            "side_label is null or side_label in ('a', 'b', 'context')",
            name="ck_contradiction_candidate_sources_side_label",
        ),
        UniqueConstraint(
            "contradiction_candidate_id",
            "source_reference_id",
            "side_label",
            name="uq_contradiction_candidate_sources_candidate_source_side",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    contradiction_candidate_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contradiction_candidates.id"),
        nullable=False,
    )
    source_reference_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("source_references.id"), nullable=False)
    side_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    contradiction_candidate = relationship("ContradictionCandidateModel")
    source_reference = relationship("SourceReferenceModel")
