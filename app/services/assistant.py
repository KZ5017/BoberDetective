from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.assistant import AssistantChatModel, AssistantMessageModel
from app.schemas.assistant import (
    AssistantChatCreateRequest,
    AssistantChatDetail,
    AssistantChatListItem,
    AssistantChatUpdateRequest,
    AssistantMessageRead,
    AssistantMessageRegenerateRequest,
    AssistantMessageSendRequest,
    AssistantMessageSendResponse,
)
from app.services.llm import LLMChatMessage, LLMProviderError, LMStudioNativeProvider


ASSISTANT_DEFAULT_TITLE = "Új beszélgetés"
ASSISTANT_CONTEXT_CHARACTER_BUDGET = 30000


class AssistantError(Exception):
    pass


class AssistantNotFoundError(AssistantError):
    pass


class AssistantValidationError(AssistantError):
    pass


class AssistantLLMError(AssistantError):
    pass


def list_assistant_chats(db: Session) -> list[AssistantChatListItem]:
    chats = (
        db.execute(
            select(AssistantChatModel)
            .where(AssistantChatModel.chat_status == "active")
            .order_by(AssistantChatModel.updated_at.desc())
        )
        .scalars()
        .all()
    )
    return [AssistantChatListItem.model_validate(chat) for chat in chats]


def create_assistant_chat(db: Session, payload: AssistantChatCreateRequest) -> AssistantChatDetail:
    settings = get_settings()
    chat = AssistantChatModel(
        title=ASSISTANT_DEFAULT_TITLE,
        model_name=settings.llm_chat_model,
        reasoning_mode=payload.reasoning_mode,
        temperature=payload.temperature,
        metadata_json={},
    )
    db.add(chat)
    db.commit()
    return get_assistant_chat(db, chat.id)


def get_assistant_chat(db: Session, chat_id: UUID) -> AssistantChatDetail:
    chat = _get_active_chat(db, chat_id)
    return _chat_detail(chat)


def update_assistant_chat(db: Session, chat_id: UUID, payload: AssistantChatUpdateRequest) -> AssistantChatDetail:
    chat = _get_active_chat(db, chat_id)
    chat.title = _normalize_title(payload.title) or ASSISTANT_DEFAULT_TITLE
    chat.updated_at = datetime.now(UTC)
    db.commit()
    return get_assistant_chat(db, chat.id)


def delete_assistant_chat(db: Session, chat_id: UUID) -> None:
    chat = _get_active_chat(db, chat_id)
    now = datetime.now(UTC)
    chat.chat_status = "deleted"
    chat.deleted_at = now
    chat.updated_at = now
    db.commit()


def send_assistant_message(db: Session, chat_id: UUID, payload: AssistantMessageSendRequest) -> AssistantMessageSendResponse:
    chat = _get_active_chat(db, chat_id)
    content = payload.content.strip()
    if not content:
        raise AssistantValidationError("Az üzenet nem lehet üres")

    sequence_index = _next_message_sequence(db, chat.id)
    user_message = AssistantMessageModel(
        chat_id=chat.id,
        role="user",
        content=content,
        sequence_index=sequence_index,
        runtime_metadata_json={},
    )
    now = datetime.now(UTC)
    if chat.title == ASSISTANT_DEFAULT_TITLE and sequence_index == 1:
        chat.title = _title_from_message(content)
    chat.updated_at = now
    db.add(user_message)
    db.commit()

    return _generate_assistant_response(
        db,
        chat,
        user_message,
        reasoning_mode=payload.reasoning_mode,
        temperature=payload.temperature,
    )


def regenerate_last_assistant_message(
    db: Session,
    chat_id: UUID,
    payload: AssistantMessageRegenerateRequest,
) -> AssistantMessageSendResponse:
    chat = _get_active_chat(db, chat_id)
    messages = sorted(chat.messages, key=lambda item: item.sequence_index)
    if len(messages) < 2:
        raise AssistantValidationError("Nincs újragenerálható asszisztens válasz.")
    last_message = messages[-1]
    previous_message = messages[-2]
    if last_message.role != "assistant" or previous_message.role != "user":
        raise AssistantValidationError("Csak az utolsó asszisztens válasz generálható újra.")

    db.delete(last_message)
    chat.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(previous_message)
    db.refresh(chat)

    return _generate_assistant_response(
        db,
        chat,
        previous_message,
        reasoning_mode=payload.reasoning_mode,
        temperature=payload.temperature,
    )


def _generate_assistant_response(
    db: Session,
    chat: AssistantChatModel,
    user_message: AssistantMessageModel,
    *,
    reasoning_mode: str | None,
    temperature: float | None,
) -> AssistantMessageSendResponse:
    effective_reasoning_mode = reasoning_mode or chat.reasoning_mode
    effective_temperature = temperature if temperature is not None else chat.temperature
    messages = _context_messages_for_llm(db, chat.id)
    settings = get_settings()
    try:
        completion = LMStudioNativeProvider(settings).chat_completion(
            settings.llm_chat_model,
            messages,
            temperature=effective_temperature,
            max_tokens=None,
            reasoning_mode=_llm_reasoning_mode(effective_reasoning_mode),
        )
    except LLMProviderError as exc:
        raise AssistantLLMError(str(exc)) from exc

    assistant_message = AssistantMessageModel(
        chat_id=chat.id,
        role="assistant",
        content=completion.content.strip(),
        sequence_index=_next_message_sequence(db, chat.id),
        model_name=completion.model,
        reasoning_mode=effective_reasoning_mode,
        runtime_metadata_json={"temperature": effective_temperature},
    )
    chat.model_name = completion.model
    chat.reasoning_mode = effective_reasoning_mode
    chat.temperature = effective_temperature
    chat.updated_at = datetime.now(UTC)
    db.add(assistant_message)
    db.commit()
    db.expire(chat, ["messages"])
    return AssistantMessageSendResponse(
        chat=get_assistant_chat(db, chat.id),
        user_message=AssistantMessageRead.model_validate(user_message),
        assistant_message=AssistantMessageRead.model_validate(assistant_message),
    )


def _get_active_chat(db: Session, chat_id: UUID) -> AssistantChatModel:
    chat = (
        db.execute(
            select(AssistantChatModel)
            .options(selectinload(AssistantChatModel.messages))
            .where(AssistantChatModel.id == chat_id, AssistantChatModel.chat_status == "active")
        )
        .scalars()
        .first()
    )
    if chat is None:
        raise AssistantNotFoundError("A beszélgetés nem található")
    return chat


def _next_message_sequence(db: Session, chat_id: UUID) -> int:
    current = db.execute(
        select(func.max(AssistantMessageModel.sequence_index)).where(AssistantMessageModel.chat_id == chat_id)
    ).scalar_one()
    return int(current or 0) + 1


def _context_messages_for_llm(db: Session, chat_id: UUID) -> list[LLMChatMessage]:
    messages = (
        db.execute(
            select(AssistantMessageModel)
            .where(AssistantMessageModel.chat_id == chat_id)
            .order_by(AssistantMessageModel.sequence_index.asc())
        )
        .scalars()
        .all()
    )
    selected: list[AssistantMessageModel] = []
    character_count = 0
    for message in reversed(messages):
        next_count = character_count + len(message.content)
        if selected and next_count > ASSISTANT_CONTEXT_CHARACTER_BUDGET:
            break
        selected.append(message)
        character_count = next_count
    selected.reverse()
    return [LLMChatMessage(role=message.role, content=message.content) for message in selected]


def _chat_detail(chat: AssistantChatModel) -> AssistantChatDetail:
    return AssistantChatDetail(
        id=chat.id,
        title=chat.title,
        chat_status=chat.chat_status,
        model_name=chat.model_name,
        reasoning_mode=chat.reasoning_mode,
        temperature=chat.temperature,
        metadata_json=chat.metadata_json or {},
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        deleted_at=chat.deleted_at,
        messages=[AssistantMessageRead.model_validate(message) for message in sorted(chat.messages, key=lambda item: item.sequence_index)],
    )


def _llm_reasoning_mode(reasoning_mode: str) -> str:
    if reasoning_mode == "model_default":
        return "model_default"
    return "off"


def _normalize_title(title: str | None) -> str | None:
    if title is None:
        return None
    normalized = " ".join(title.split())
    return normalized[:160] if normalized else None


def _title_from_message(content: str) -> str:
    normalized = " ".join(content.split())
    if not normalized:
        return ASSISTANT_DEFAULT_TITLE
    return normalized[:80]
