from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResearchFindingModel(Base):
    __tablename__ = "research_findings"
    __table_args__ = (
        CheckConstraint(
            "suggested_type in ('claim', 'event', 'entity', 'document_reference', 'other')",
            name="ck_research_findings_suggested_type",
        ),
        CheckConstraint(
            "source_validation_status in ('pending_source_validation', 'source_valid', 'source_invalid')",
            name="ck_research_findings_source_validation_status",
        ),
        CheckConstraint(
            "conversion_status in ('not_converted', 'converted', 'ignored')",
            name="ck_research_findings_conversion_status",
        ),
        CheckConstraint(
            "target_object_type is null or target_object_type in ('claim', 'event', 'entity', 'missing_item_candidate', 'summary_item', 'other')",
            name="ck_research_findings_target_object_type",
        ),
        CheckConstraint(
            "(conversion_status = 'converted' and target_object_type is not null and target_object_id is not null) "
            "or (conversion_status <> 'converted' and target_object_type is null and target_object_id is null)",
            name="ck_research_findings_conversion_target_consistency",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    analysis_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=False)
    source_reference_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("source_references.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    finding_text: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_type: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_type_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance_reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_validation_status: Mapped[str] = mapped_column(Text, nullable=False)
    conversion_status: Mapped[str] = mapped_column(Text, nullable=False)
    target_object_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_object_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    analysis_run = relationship("AnalysisRunModel")
    case = relationship("CaseModel")
    source_reference = relationship("SourceReferenceModel")
