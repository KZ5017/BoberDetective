from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SourceReferenceModel(Base):
    __tablename__ = "source_references"
    __table_args__ = (
        CheckConstraint("page_number is null or page_number >= 1", name="ck_source_references_page_number_positive"),
        CheckConstraint(
            "confidence is null or (confidence >= 0 and confidence <= 1)",
            name="ck_source_references_confidence_range",
        ),
        CheckConstraint(
            "quote_char_end is null or quote_char_start is null or quote_char_end >= quote_char_start",
            name="ck_source_references_quote_char_end_after_start",
        ),
        CheckConstraint(
            "source_kind in ('page_quote', 'chunk_quote', 'document_metadata', 'manual_note')",
            name="ck_source_references_source_kind",
        ),
        CheckConstraint(
            "source_kind = 'document_metadata' or page_id is not null or chunk_id is not null",
            name="ck_source_references_source_location_required",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    page_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_pages.id"), nullable=True)
    chunk_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_chunks.id"), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote_text: Mapped[str] = mapped_column(Text, nullable=False)
    quote_char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote_char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    citation_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    case = relationship("CaseModel")
    document = relationship("DocumentModel")
    page = relationship("DocumentPageModel")
    chunk = relationship("DocumentChunkModel")
    created_by = relationship("UserModel")
