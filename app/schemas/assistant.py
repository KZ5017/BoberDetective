from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


AssistantReasoningMode = Literal["normal", "model_default"]
AssistantRole = Literal["user", "assistant"]


class AssistantChatCreateRequest(BaseModel):
    reasoning_mode: AssistantReasoningMode = "normal"
    temperature: float = Field(default=0.7, ge=0, le=2)


class AssistantChatUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class AssistantMessageSendRequest(BaseModel):
    content: str = Field(min_length=1, max_length=120000)
    reasoning_mode: AssistantReasoningMode | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)


class AssistantMessageRegenerateRequest(BaseModel):
    reasoning_mode: AssistantReasoningMode | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)


class AssistantMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chat_id: UUID
    role: str
    content: str
    sequence_index: int
    model_name: str | None
    reasoning_mode: str | None
    runtime_metadata_json: dict
    error_message: str | None
    created_at: datetime


class AssistantChatListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    chat_status: str
    model_name: str | None
    reasoning_mode: str
    temperature: float
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class AssistantChatDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    chat_status: str
    model_name: str | None
    reasoning_mode: str
    temperature: float
    metadata_json: dict
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    messages: list[AssistantMessageRead]


class AssistantChatList(BaseModel):
    data: list[AssistantChatListItem]


class AssistantMessageSendResponse(BaseModel):
    chat: AssistantChatDetail
    user_message: AssistantMessageRead
    assistant_message: AssistantMessageRead
