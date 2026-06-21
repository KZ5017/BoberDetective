from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentProcessingItemModel(Base):
    __tablename__ = "document_processing_items"
    __table_args__ = (
        CheckConstraint("profile_key in ('person_search_seeds')", name="ck_document_processing_items_profile_key"),
        CheckConstraint("item_kind in ('person')", name="ck_document_processing_items_item_kind"),
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


class FullDocumentAnswerModel(Base):
    __tablename__ = "full_document_answers"
    __table_args__ = (
        CheckConstraint("profile_key in ('free_document_question')", name="ck_full_document_answers_profile_key"),
        CheckConstraint("length(trim(question_text)) > 0", name="ck_full_document_answers_question_not_blank"),
        CheckConstraint("length(trim(answer_text)) > 0", name="ck_full_document_answers_answer_not_blank"),
        CheckConstraint("answer_status in ('active', 'deleted')", name="ck_full_document_answers_status"),
        CheckConstraint("page_start >= 1", name="ck_full_document_answers_page_start_positive"),
        CheckConstraint("page_end >= page_start", name="ck_full_document_answers_page_range_order"),
        CheckConstraint("source_page_count >= 1", name="ck_full_document_answers_source_page_count_positive"),
        CheckConstraint("source_character_count >= 0", name="ck_full_document_answers_source_char_count_non_negative"),
        UniqueConstraint("analysis_run_id", name="uq_full_document_answers_analysis_run"),
        Index("ix_full_document_answers_case_document", "case_id", "document_id"),
        Index("ix_full_document_answers_run", "analysis_run_id"),
        Index("ix_full_document_answers_status", "case_id", "answer_status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    analysis_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=False)
    profile_key: Mapped[str] = mapped_column(Text, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    source_page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_template_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_template_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    case = relationship("CaseModel")
    document = relationship("DocumentModel")
    analysis_run = relationship("AnalysisRunModel")
