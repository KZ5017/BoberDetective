from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DetachedSourceItemModel(Base):
    __tablename__ = "detached_source_items"
    __table_args__ = (
        CheckConstraint(
            "detached_from_object_type in ('entity', 'event', 'missing_item_candidate')",
            name="ck_detached_source_items_object_type",
        ),
        CheckConstraint(
            "handling_status in ('needs_review', 'reattached', 'discarded')",
            name="ck_detached_source_items_handling_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    source_reference_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("source_references.id"), nullable=False)
    detached_from_object_type: Mapped[str] = mapped_column(Text, nullable=False)
    detached_from_object_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    detached_from_source_link_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    detached_from_source_link_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_title_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    object_body_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_subtype_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_review_status_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_validation_status_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    handling_status: Mapped[str] = mapped_column(Text, nullable=False, default="needs_review")
    reattached_to_object_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    reattached_to_object_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reattached_to_object_title_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    detach_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    detached_by_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    detached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    case = relationship("CaseModel")
    source_reference = relationship("SourceReferenceModel")
    detached_by = relationship("UserModel")
