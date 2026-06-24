from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

import app.api.v1.assistant as assistant_api
from app.schemas.assistant import AssistantChatCreateRequest, AssistantChatListItem, AssistantMessageSendRequest
from app.services.assistant import AssistantLLMError, AssistantNotFoundError, _llm_reasoning_mode, _title_from_message


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
