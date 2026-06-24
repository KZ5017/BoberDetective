from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


_Q = chr(39)


class AssistantChatModel(Base):
    __tablename__ = "assistant_chats"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_assistant_chats_title_nonblank"),
        CheckConstraint(
            "chat_status in (" + _Q + "active" + _Q + ", " + _Q + "deleted" + _Q + ")",
            name="ck_assistant_chats_status",
        ),
        CheckConstraint(
            "reasoning_mode in (" + _Q + "normal" + _Q + ", " + _Q + "model_default" + _Q + ")",
            name="ck_assistant_chats_reasoning_mode",
        ),
        CheckConstraint("temperature >= 0 and temperature <= 2", name="ck_assistant_chats_temperature_range"),
        Index("ix_assistant_chats_status_updated", "chat_status", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="Új beszélgetés")
    chat_status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning_mode: Mapped[str] = mapped_column(Text, nullable=False, default="normal")
    temperature: Mapped[float] = mapped_column(nullable=False, default=0.7)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    messages = relationship(
        "AssistantMessageModel",
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="AssistantMessageModel.sequence_index",
    )
    created_by = relationship("UserModel")


class AssistantMessageModel(Base):
    __tablename__ = "assistant_messages"
    __table_args__ = (
        CheckConstraint(
            "role in (" + _Q + "user" + _Q + ", " + _Q + "assistant" + _Q + ")",
            name="ck_assistant_messages_role",
        ),
        CheckConstraint("length(trim(content)) > 0", name="ck_assistant_messages_content_nonblank"),
        CheckConstraint("sequence_index >= 1", name="ck_assistant_messages_sequence_positive"),
        Index("ix_assistant_messages_chat_sequence", "chat_id", "sequence_index", unique=True),
        Index("ix_assistant_messages_chat_created", "chat_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    chat_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("assistant_chats.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning_mode: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    chat = relationship("AssistantChatModel", back_populates="messages")
