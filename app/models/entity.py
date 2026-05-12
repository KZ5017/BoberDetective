from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EntityModel(Base):
    __tablename__ = "entities"
    __table_args__ = (
        CheckConstraint(
            "entity_type in ('person', 'organization', 'location', 'phone', 'email', 'license_plate', "
            "'case_reference', 'money_amount', 'document_reference', 'other')",
            name="ck_entities_entity_type",
        ),
        CheckConstraint("confidence is null or (confidence >= 0 and confidence <= 1)", name="ck_entities_confidence_range"),
        CheckConstraint(
            "review_status in ('new', 'needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_entities_review_status",
        ),
        CheckConstraint(
            "created_by_analysis_run_id is not null or created_by_user_id is not null",
            name="ck_entities_creator_required",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_by_analysis_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    review_status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    analysis_run = relationship("AnalysisRunModel")
    case = relationship("CaseModel")
    created_by = relationship("UserModel")


class EntityMentionModel(Base):
    __tablename__ = "entity_mentions"
    __table_args__ = (
        CheckConstraint("page_number is null or page_number >= 1", name="ck_entity_mentions_page_number_positive"),
        CheckConstraint("confidence is null or (confidence >= 0 and confidence <= 1)", name="ck_entity_mentions_confidence_range"),
        CheckConstraint("char_end is null or char_start is null or char_end >= char_start", name="ck_entity_mentions_char_end_after_start"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    page_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_pages.id"), nullable=True)
    chunk_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_chunks.id"), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    surface_text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_reference_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("source_references.id"), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_by_analysis_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    analysis_run = relationship("AnalysisRunModel")
    case = relationship("CaseModel")
    entity = relationship("EntityModel")
    source_reference = relationship("SourceReferenceModel")
