from pathlib import Path

import httpx

from app.core.config import Settings
from app.services.llm import LMStudioNativeProvider, LLMChatMessage, OpenAICompatibleLocalProvider


def _settings() -> Settings:
    return Settings(
        environment="test",
        data_root=Path("/tmp/boberdetective-test"),
        api_prefix="/api/v1",
        database_url="postgresql+psycopg://example",
        llm_provider="lm_studio",
        llm_base_url="http://llm.local/v1",
        llm_api_key="secret",
        llm_chat_model="chat-model",
        llm_embedding_model="embedding-model",
        llm_timeout_seconds=1,
        llm_context_length=4096,
        llm_eval_batch_size=4096,
        llm_flash_attention=True,
        llm_offload_kv_cache_to_gpu=True,
        max_upload_bytes=1024,
    )


def test_openai_compatible_provider_lists_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "chat-model"}, {"id": "embedding-model"}]})

    client = httpx.Client(base_url="http://llm.local/v1", transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleLocalProvider(_settings(), client)

    assert [model.id for model in provider.list_models()] == ["chat-model", "embedding-model"]


def test_llm_smoke_reports_configured_model_availability() -> None:
    client = httpx.Client(
        base_url="http://llm.local/v1",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": [{"id": "chat-model"}]})),
    )
    provider = OpenAICompatibleLocalProvider(_settings(), client)

    result = provider.smoke_check()

    assert result.reachable is True
    assert result.configured_chat_model_available is True
    assert result.configured_embedding_model_available is False


def test_llm_smoke_reports_unreachable_provider() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    client = httpx.Client(base_url="http://llm.local/v1", transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleLocalProvider(_settings(), client)

    result = provider.smoke_check()

    assert result.reachable is False
    assert result.model_ids == []
    assert result.error_message is not None


def test_lm_studio_native_provider_uses_reasoning_off() -> None:
    captured_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(request.read() and __import__("json").loads(request.content))
        return httpx.Response(200, json={"output": [{"type": "message", "content": "{\"ok\": true}"}]})

    client = httpx.Client(base_url="http://llm.local", transport=httpx.MockTransport(handler))
    provider = LMStudioNativeProvider(_settings(), client)

    result = provider.chat_completion("qwen/qwen3.5-9b", [LLMChatMessage(role="user", content="hello")])

    assert result.content == "{\"ok\": true}"
    assert captured_payload["reasoning"] == "off"
    assert captured_payload["input"][0]["type"] == "text"
    assert "content" in captured_payload["input"][0]
    assert captured_payload["max_output_tokens"] == 800
    assert captured_payload["store"] is False


def test_lm_studio_native_provider_omits_reasoning_for_non_reasoning_model() -> None:
    captured_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(__import__("json").loads(request.content))
        return httpx.Response(200, json={"output": [{"type": "message", "content": "{\"ok\": true}"}]})

    client = httpx.Client(base_url="http://llm.local", transport=httpx.MockTransport(handler))
    provider = LMStudioNativeProvider(_settings(), client)

    provider.chat_completion("meta-llama-3.1-8b-instruct", [LLMChatMessage(role="user", content="hello")])

    assert "reasoning" not in captured_payload


def test_lm_studio_native_provider_lists_loaded_models() -> None:
    client = httpx.Client(
        base_url="http://llm.local",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "models": [
                        {"key": "fallback-model", "loaded_instances": [{"id": "chat-model"}]},
                        {"key": "embedding-model"},
                    ]
                },
            )
        ),
    )
    provider = LMStudioNativeProvider(_settings(), client)

    assert [model.id for model in provider.list_models()] == ["chat-model", "embedding-model"]


def test_lm_studio_native_provider_loads_configured_chat_model_with_gpu_friendly_profile() -> None:
    captured_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/models/load"
        captured_payload.update(__import__("json").loads(request.content))
        return httpx.Response(
            200,
            json={
                "type": "llm",
                "instance_id": "chat-model",
                "load_time_seconds": 1.25,
                "status": "loaded",
                "load_config": {
                    "context_length": 4096,
                    "eval_batch_size": 4096,
                    "flash_attention": True,
                    "offload_kv_cache_to_gpu": True,
                },
            },
        )

    client = httpx.Client(base_url="http://llm.local", transport=httpx.MockTransport(handler))
    provider = LMStudioNativeProvider(_settings(), client)

    result = provider.load_configured_chat_model()

    assert captured_payload == {
        "model": "chat-model",
        "context_length": 4096,
        "eval_batch_size": 4096,
        "flash_attention": True,
        "offload_kv_cache_to_gpu": True,
        "echo_load_config": True,
    }
    assert result.type == "llm"
    assert result.instance_id == "chat-model"
    assert result.status == "loaded"
    assert result.load_config == {
        "context_length": 4096,
        "eval_batch_size": 4096,
        "flash_attention": True,
        "offload_kv_cache_to_gpu": True,
    }
