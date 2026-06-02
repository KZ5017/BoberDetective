from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentCollectionModel(Base):
    __tablename__ = "document_collections"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_document_collections_name_nonblank"),
        CheckConstraint("length(name) <= 120", name="ck_document_collections_name_length"),
        CheckConstraint("description is null or length(description) <= 1000", name="ck_document_collections_description_length"),
        CheckConstraint("color is null or color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_document_collections_color_hex"),
        CheckConstraint("sort_order >= 0", name="ck_document_collections_sort_order_non_negative"),
        Index("ix_document_collections_case_sort", "case_id", "sort_order", "name"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    case = relationship("CaseModel")
    created_by = relationship("UserModel")
    memberships = relationship(
        "DocumentCollectionMembershipModel",
        back_populates="collection",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DocumentCollectionMembershipModel(Base):
    __tablename__ = "document_collection_memberships"
    __table_args__ = (
        Index("ix_document_collection_memberships_document", "document_id"),
    )

    collection_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_collections.id", ondelete="CASCADE"),
        primary_key=True,
    )
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    added_by_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    collection = relationship("DocumentCollectionModel", back_populates="memberships")
    document = relationship("DocumentModel")
    added_by = relationship("UserModel")
