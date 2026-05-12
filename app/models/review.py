from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class HumanReviewModel(Base):
    __tablename__ = "human_reviews"
    __table_args__ = (
        CheckConstraint(
            "object_type in ('entity', 'event', 'claim', 'contradiction_candidate', "
            "'missing_item_candidate', 'source_reference', 'export', 'summary_item')",
            name="ck_human_reviews_object_type",
        ),
        CheckConstraint(
            "action_type in ('mark_needs_review', 'verify', 'reject', 'correct', 'comment', 'attach_source', 'detach_source')",
            name="ck_human_reviews_action_type",
        ),
        CheckConstraint(
            "previous_review_status is null or previous_review_status in ('new', 'needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_human_reviews_previous_review_status",
        ),
        CheckConstraint(
            "new_review_status is null or new_review_status in ('new', 'needs_review', 'verified', 'rejected', 'corrected')",
            name="ck_human_reviews_new_review_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    previous_review_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_review_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_patch_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    performed_by_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    case = relationship("CaseModel")
    performed_by = relationship("UserModel")
