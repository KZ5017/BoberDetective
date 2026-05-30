from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentProcessingItemModel(Base):
    __tablename__ = "document_processing_items"
    __table_args__ = (
        CheckConstraint("profile_key in ('person_search_seeds', 'entity_search_seeds')", name="ck_document_processing_items_profile_key"),
        CheckConstraint(
            "item_kind in ('person', 'organization', 'location', 'document_reference', 'case_reference', 'attachment', 'other')",
            name="ck_document_processing_items_item_kind",
        ),
        CheckConstraint("length(trim(display_label)) > 0", name="ck_document_processing_items_display_label_not_blank"),
        CheckConstraint("jsonb_typeof(mentioned_forms_json) = 'array'", name="ck_document_processing_items_mentioned_forms_array"),
        CheckConstraint(
            "jsonb_typeof(source_supported_details_json) = 'array'",
            name="ck_document_processing_items_supported_details_array",
        ),
        CheckConstraint("jsonb_typeof(relationships_json) = 'array'", name="ck_document_processing_items_relationships_array"),
        CheckConstraint(
            "jsonb_typeof(alternative_search_focuses_json) = 'array'",
            name="ck_document_processing_items_alt_focuses_array",
        ),
        CheckConstraint("jsonb_typeof(source_evidence_json) = 'array'", name="ck_document_processing_items_source_evidence_array"),
        CheckConstraint(
            "work_status in ('active', 'set_aside', 'converted', 'deleted')",
            name="ck_document_processing_items_work_status",
        ),
        CheckConstraint(
            "target_object_type is null or target_object_type in ('claim', 'entity', 'event', 'missing_item_candidate', 'research_finding')",
            name="ck_document_processing_items_target_type",
        ),
        Index("ix_document_processing_items_case_document", "case_id", "document_id"),
        Index("ix_document_processing_items_document_status", "document_id", "work_status"),
        Index("ix_document_processing_items_profile", "profile_key"),
        Index("ix_document_processing_items_run", "analysis_run_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    analysis_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=False)
    profile_key: Mapped[str] = mapped_column(Text, nullable=False)
    item_kind: Mapped[str] = mapped_column(Text, nullable=False)
    display_label: Mapped[str] = mapped_column(Text, nullable=False)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mentioned_forms_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_supported_details_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    relationships_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    recommended_search_focus: Mapped[str | None] = mapped_column(Text, nullable=True)
    alternative_search_focuses_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_evidence_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    work_status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    target_object_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_object_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    case = relationship("CaseModel")
    document = relationship("DocumentModel")
    analysis_run = relationship("AnalysisRunModel")
