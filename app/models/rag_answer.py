from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RagAnswerModel(Base):
    __tablename__ = "rag_answers"
    __table_args__ = (
        CheckConstraint("length(trim(question)) > 0", name="ck_rag_answers_question_nonblank"),
        CheckConstraint("length(trim(answer_text)) > 0", name="ck_rag_answers_answer_text_nonblank"),
        CheckConstraint(
            "answer_mode in ('short', 'detailed')",
            name="ck_rag_answers_answer_mode",
        ),
        UniqueConstraint("analysis_run_id", name="uq_rag_answers_analysis_run"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    analysis_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_mode: Mapped[str] = mapped_column(Text, nullable=False)
    source_scope_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    used_sources_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    retrieval_metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    created_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    analysis_run = relationship("AnalysisRunModel")
    case = relationship("CaseModel")
    created_by = relationship("UserModel")
