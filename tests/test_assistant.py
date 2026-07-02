from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

import app.api.v1.assistant as assistant_api
import app.services.assistant as assistant_service
from app.schemas.assistant import AssistantChatCreateRequest, AssistantChatListItem, AssistantMessageRegenerateRequest, AssistantMessageSendRequest
from app.services.assistant import (
    ASSISTANT_CONTEXT_LIMIT_ERROR_CODE,
    ASSISTANT_SYSTEM_PROMPT,
    AssistantContextLimitError,
    AssistantLLMError,
    AssistantNotFoundError,
    _context_messages_for_llm,
    _ensure_context_character_budget,
    _llm_reasoning_mode,
    _title_from_message,
)


def test_assistant_chat_create_request_defaults_to_normal_reasoning() -> None:
    payload = AssistantChatCreateRequest()

    assert payload.reasoning_mode == "normal"
    assert payload.temperature == 0.7


def test_assistant_title_from_message_is_compact() -> None:
    title = _title_from_message("  Ez   egy hosszabb   kérdés a modellhez.  ")

    assert title == "Ez egy hosszabb kérdés a modellhez."


def test_assistant_reasoning_mode_maps_to_provider_values() -> None:
    assert _llm_reasoning_mode("normal") == "off"
    assert _llm_reasoning_mode("model_default") == "model_default"


def test_assistant_api_list_wraps_service_response(monkeypatch) -> None:
    item = AssistantChatListItem(
        id=uuid4(),
        title="Beszélgetés",
        chat_status="active",
        model_name="qwen/qwen3.5-9b",
        reasoning_mode="normal",
        temperature=0.7,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )
    monkeypatch.setattr(assistant_api, "list_assistant_chats", lambda db: [item])

    response = assistant_api.get_assistant_chats(db=object())

    assert response.data == [item]


def test_assistant_api_maps_missing_chat(monkeypatch) -> None:
    def _missing(db, chat_id):
        raise AssistantNotFoundError("missing")

    monkeypatch.setattr(assistant_api, "get_assistant_chat", _missing)

    with pytest.raises(HTTPException) as exc:
        assistant_api.get_assistant_chat_detail(uuid4(), db=object())

    assert exc.value.status_code == 404


def test_assistant_api_maps_llm_error(monkeypatch) -> None:
    def _llm_error(db, chat_id, payload):
        raise AssistantLLMError("llm failed")

    monkeypatch.setattr(assistant_api, "send_assistant_message", _llm_error)

    with pytest.raises(HTTPException) as exc:
        assistant_api.post_assistant_message(uuid4(), AssistantMessageSendRequest(content="Szia"), db=object())

    assert exc.value.status_code == 502


def test_assistant_api_maps_regenerate_validation_error(monkeypatch) -> None:
    def _validation_error(db, chat_id, payload):
        raise assistant_api.AssistantValidationError("no assistant answer")

    monkeypatch.setattr(assistant_api, "regenerate_last_assistant_message", _validation_error)

    with pytest.raises(HTTPException) as exc:
        assistant_api.post_assistant_regenerate_last_message(uuid4(), AssistantMessageRegenerateRequest(), db=object())

    assert exc.value.status_code == 400


def test_assistant_context_messages_include_minimal_system_prompt(monkeypatch) -> None:
    messages = [
        SimpleNamespace(role="user", content="Első kérdés"),
        SimpleNamespace(role="assistant", content="Első válasz"),
        SimpleNamespace(role="user", content="Utolsó kérdés"),
    ]
    monkeypatch.setattr(assistant_service, "_stored_context_messages", lambda db, chat_id: messages)

    llm_messages = _context_messages_for_llm(object(), uuid4())

    assert [message.role for message in llm_messages] == ["system", "user", "assistant", "user"]
    assert llm_messages[0].content == ASSISTANT_SYSTEM_PROMPT
    assert llm_messages[-1].content == "Utolsó kérdés"


def test_assistant_context_budget_rejects_oversized_history(monkeypatch) -> None:
    monkeypatch.setattr(assistant_service, "ASSISTANT_CONTEXT_CHARACTER_BUDGET", 10)
    messages = [SimpleNamespace(content="12345"), SimpleNamespace(content="67890")]

    _ensure_context_character_budget(messages)
    with pytest.raises(AssistantContextLimitError):
        _ensure_context_character_budget(messages, additional_content="x")


def test_assistant_api_maps_context_limit_error(monkeypatch) -> None:
    def _context_limit(db, chat_id, payload):
        raise AssistantContextLimitError("context full")

    monkeypatch.setattr(assistant_api, "send_assistant_message", _context_limit)

    with pytest.raises(HTTPException) as exc:
        assistant_api.post_assistant_message(uuid4(), AssistantMessageSendRequest(content="Szia"), db=object())

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == ASSISTANT_CONTEXT_LIMIT_ERROR_CODE
    assert exc.value.detail["message"] == "context full"


def test_assistant_regenerate_reuses_previous_user_message(monkeypatch) -> None:
    chat_id = uuid4()
    user_message = SimpleNamespace(id=uuid4(), role="user", content="Eredeti kérdés", sequence_index=1)
    assistant_message = SimpleNamespace(id=uuid4(), role="assistant", content="Régi válasz", sequence_index=2)
    chat = SimpleNamespace(id=chat_id, messages=[user_message, assistant_message], updated_at=None)
    calls = []

    class FakeDb:
        def __init__(self) -> None:
            self.deleted = []
            self.commits = 0
            self.refreshed = []

        def delete(self, item) -> None:
            self.deleted.append(item)

        def commit(self) -> None:
            self.commits += 1

        def refresh(self, item) -> None:
            self.refreshed.append(item)

    db = FakeDb()

    def fake_generate(db_arg, chat_arg, user_arg, *, reasoning_mode, temperature):
        calls.append((db_arg, chat_arg, user_arg, reasoning_mode, temperature))
        return SimpleNamespace(chat=chat, user_message=user_arg, assistant_message=SimpleNamespace(role="assistant"))

    monkeypatch.setattr(assistant_service, "_get_active_chat", lambda db_arg, chat_id_arg: chat)
    monkeypatch.setattr(assistant_service, "_generate_assistant_response", fake_generate)
    monkeypatch.setattr(assistant_service, "_validate_assistant_context_budget", lambda *args, **kwargs: None)

    assistant_service.regenerate_last_assistant_message(
        db,
        chat_id,
        AssistantMessageRegenerateRequest(reasoning_mode="model_default", temperature=0.4),
    )

    assert db.deleted == [assistant_message]
    assert db.commits == 1
    assert calls[0][2] is user_message
    assert calls[0][3] == "model_default"
    assert calls[0][4] == 0.4
