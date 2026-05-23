from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExportModel(Base):
    __tablename__ = "exports"
    __table_args__ = (
        CheckConstraint("export_type in ('json', 'markdown', 'html', 'pdf', 'docx')", name="ck_exports_export_type"),
        CheckConstraint(
            "export_scope in ('review_report', 'case_summary', 'claims', 'timeline', 'contradictions', 'missing_items', 'custom_bundle')",
            name="ck_exports_export_scope",
        ),
        CheckConstraint("sha256_hash is null or sha256_hash ~ '^[0-9a-f]{64}$'", name="ck_exports_sha256_hash_hex"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    export_type: Mapped[str] = mapped_column(Text, nullable=False)
    export_scope: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_by_analysis_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=True)
    exported_by_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    review_filter: Mapped[str | None] = mapped_column(Text, nullable=True)
    export_parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    case = relationship("CaseModel")
    exported_by = relationship("UserModel")
    generated_by_analysis_run = relationship("AnalysisRunModel")


class ExportItemModel(Base):
    __tablename__ = "export_items"
    __table_args__ = (
        CheckConstraint(
            "object_type in ('entity', 'event', 'claim', 'contradiction_candidate', 'missing_item_candidate')",
            name="ck_export_items_object_type",
        ),
        CheckConstraint("display_order is null or display_order >= 0", name="ck_export_items_display_order_non_negative"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    export_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("exports.id"), nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_reference_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("source_references.id"), nullable=True)
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    export = relationship("ExportModel")
    source_reference = relationship("SourceReferenceModel")
