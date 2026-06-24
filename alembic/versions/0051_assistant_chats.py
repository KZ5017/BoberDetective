"""add assistant chat history

Revision ID: 0051_assistant_chats
Revises: 0050_full_document_answers
Create Date: 2026-06-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0051_assistant_chats"
down_revision: str | None = "0050_full_document_answers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_Q = chr(39)


def upgrade() -> None:
    op.create_table(
        "assistant_chats",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("chat_status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column("reasoning_mode", sa.Text(), nullable=False, server_default="normal"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("" + _Q + "{}" + _Q + "::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_assistant_chats_title_nonblank"),
        sa.CheckConstraint("chat_status in (" + _Q + "active" + _Q + ", " + _Q + "deleted" + _Q + ")", name="ck_assistant_chats_status"),
        sa.CheckConstraint("reasoning_mode in (" + _Q + "normal" + _Q + ", " + _Q + "model_default" + _Q + ")", name="ck_assistant_chats_reasoning_mode"),
        sa.CheckConstraint("temperature >= 0 and temperature <= 2", name="ck_assistant_chats_temperature_range"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_chats_status_updated", "assistant_chats", ["chat_status", "updated_at"])

    op.create_table(
        "assistant_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column("reasoning_mode", sa.Text(), nullable=True),
        sa.Column("runtime_metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("" + _Q + "{}" + _Q + "::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role in (" + _Q + "user" + _Q + ", " + _Q + "assistant" + _Q + ")", name="ck_assistant_messages_role"),
        sa.CheckConstraint("length(trim(content)) > 0", name="ck_assistant_messages_content_nonblank"),
        sa.CheckConstraint("sequence_index >= 1", name="ck_assistant_messages_sequence_positive"),
        sa.ForeignKeyConstraint(["chat_id"], ["assistant_chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_messages_chat_sequence", "assistant_messages", ["chat_id", "sequence_index"], unique=True)
    op.create_index("ix_assistant_messages_chat_created", "assistant_messages", ["chat_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_assistant_messages_chat_created", table_name="assistant_messages")
    op.drop_index("ix_assistant_messages_chat_sequence", table_name="assistant_messages")
    op.drop_table("assistant_messages")
    op.drop_index("ix_assistant_chats_status_updated", table_name="assistant_chats")
    op.drop_table("assistant_chats")
