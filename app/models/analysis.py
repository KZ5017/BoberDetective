from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnalysisRunModel(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint(
            "run_type in ("
            "'import_document', 'inspect_document', 'parse_document', 'ocr_document', 'extract_pages', "
            "'chunk_document', 'embed_chunks', 'index_chunks', 'validate_document_processing', "
            "'retired_analysis_module', 'detect_contradiction_candidates', "
            "'search_findings', 'full_document_processing', 'answer_with_citations', 'export_bundle', "
            "'llm_smoke', 'manual_entry'"
            ")",
            name="ck_analysis_runs_run_type",
        ),
        CheckConstraint("status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')", name="ck_analysis_runs_status"),
        CheckConstraint(
            "validation_status is null or validation_status in ('not_applicable', 'passed', 'failed', 'warning')",
            name="ck_analysis_runs_validation_status",
        ),
        CheckConstraint("finished_at is null or finished_at >= started_at", name="ck_analysis_runs_finished_after_started"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    run_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    started_by_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_template_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_template_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_schema_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_schema_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieval_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    case = relationship("CaseModel")
    started_by = relationship("UserModel")


class AnalysisRunInputModel(Base):
    __tablename__ = "analysis_run_inputs"
    __table_args__ = (
        CheckConstraint(
            "input_type in ('document', 'page', 'chunk', 'entity', 'claim', 'event', 'query_text', 'filter')",
            name="ck_analysis_run_inputs_input_type",
        ),
        CheckConstraint("sequence_no >= 0", name="ck_analysis_run_inputs_sequence_non_negative"),
        CheckConstraint(
            "document_id is not null or page_id is not null or chunk_id is not null or payload_json is not null or "
            "(related_object_type is not null and related_object_id is not null)",
            name="ck_analysis_run_inputs_has_carrier",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=False)
    input_type: Mapped[str] = mapped_column(Text, nullable=False)
    document_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    page_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_pages.id"), nullable=True)
    chunk_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_chunks.id"), nullable=True)
    related_object_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_object_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    analysis_run = relationship("AnalysisRunModel")
    document = relationship("DocumentModel")
    page = relationship("DocumentPageModel")
    chunk = relationship("DocumentChunkModel")


class AnalysisRunOutputModel(Base):
    __tablename__ = "analysis_run_outputs"
    __table_args__ = (
        CheckConstraint(
            "output_type in ('document', 'page', 'chunk', 'entity', 'mention', 'event', 'claim', 'contradiction_candidate', "
            "'missing_item_candidate', 'export', 'source_reference', 'research_finding', 'document_processing_item')",
            name="ck_analysis_run_outputs_output_type",
        ),
        CheckConstraint("output_position is null or output_position >= 0", name="ck_analysis_run_outputs_position_non_negative"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=False)
    output_type: Mapped[str] = mapped_column(Text, nullable=False)
    output_object_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    output_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    analysis_run = relationship("AnalysisRunModel")
