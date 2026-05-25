from pathlib import Path

import httpx

from app.core.config import Settings
from app.services.llm import LMStudioNativeProvider, LLMChatMessage, OpenAICompatibleLocalProvider


def _settings(*, auto_load: bool = True, auto_load_embedding: bool = True) -> Settings:
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
        llm_chat_context_length=30720,
        llm_embedding_context_length=12288,
        llm_eval_batch_size=6144,
        llm_flash_attention=True,
        llm_offload_kv_cache_to_gpu=True,
        llm_auto_load_chat_model=auto_load,
        llm_auto_load_embedding_model=auto_load_embedding,
        embedding_batch_size=8,
        pdf_parser="docling_then_pypdf",
        tesseract_cmd="tesseract",
        tesseract_languages="hun+eng",
        max_upload_bytes=1024,
        qdrant_url="http://qdrant.local",
        qdrant_chunk_collection="chunks",
    )


def test_openai_compatible_provider_lists_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "chat-model"}, {"id": "embedding-model"}]})

    client = httpx.Client(base_url="http://llm.local/v1", transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleLocalProvider(_settings(auto_load_embedding=False), client)

    assert [model.id for model in provider.list_models()] == ["chat-model", "embedding-model"]


def test_llm_smoke_reports_configured_model_availability() -> None:
    client = httpx.Client(
        base_url="http://llm.local/v1",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": [{"id": "chat-model"}]})),
    )
    provider = OpenAICompatibleLocalProvider(_settings(auto_load_embedding=False), client)

    result = provider.smoke_check()

    assert result.reachable is True
    assert result.configured_chat_model_available is True
    assert result.configured_embedding_model_available is False


def test_llm_smoke_reports_unreachable_provider() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    client = httpx.Client(base_url="http://llm.local/v1", transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleLocalProvider(_settings(auto_load_embedding=False), client)

    result = provider.smoke_check()

    assert result.reachable is False
    assert result.model_ids == []
    assert result.error_message is not None


def test_openai_compatible_provider_creates_embeddings() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings"
        payload = __import__("json").loads(request.content)
        assert payload["model"] == "embedding-model"
        assert payload["input"] == ["elso", "masodik"]
        return httpx.Response(
            200,
            json={
                "model": "embedding-model",
                "data": [
                    {"index": 1, "embedding": [0.3, 0.4]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ],
            },
        )

    client = httpx.Client(base_url="http://llm.local/v1", transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleLocalProvider(_settings(auto_load_embedding=False), client)

    result = provider.embeddings("embedding-model", ["elso", "masodik"])

    assert result.model == "embedding-model"
    assert result.embeddings == [[0.1, 0.2], [0.3, 0.4]]


def test_openai_compatible_provider_auto_loads_embedding_model() -> None:
    paths: list[str] = []
    captured_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(f"{request.method} {request.url.path}")
        payload = __import__("json").loads(request.content) if request.content else {}
        if payload:
            captured_payloads.append(payload)
        if request.url.path == "/api/v1/models":
            return httpx.Response(200, json={"models": [{"key": "embedding-model", "loaded_instances": []}]})
        if request.url.path == "/api/v1/models/load":
            return httpx.Response(200, json={"type": "embedding", "instance_id": "embedding-model:1", "status": "loaded"})
        if request.url.path == "/v1/embeddings":
            return httpx.Response(200, json={"model": payload["model"], "data": [{"index": 0, "embedding": [0.1, 0.2]}]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="http://llm.local/v1", transport=transport)
    native_client = httpx.Client(base_url="http://llm.local", transport=transport)
    provider = OpenAICompatibleLocalProvider(_settings(), client, native_client)

    result = provider.embeddings("embedding-model", ["teszt"])

    assert paths == ["GET /api/v1/models", "POST /api/v1/models/load", "POST /v1/embeddings"]
    assert captured_payloads[0]["model"] == "embedding-model"
    assert captured_payloads[0]["context_length"] == 12288
    assert "eval_batch_size" not in captured_payloads[0]
    assert "offload_kv_cache_to_gpu" not in captured_payloads[0]
    assert "flash_attention" not in captured_payloads[0]
    assert captured_payloads[1]["model"] == "embedding-model:1"
    assert result.model == "embedding-model:1"


def test_lm_studio_native_provider_uses_reasoning_off() -> None:
    captured_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(request.read() and __import__("json").loads(request.content))
        return httpx.Response(200, json={"output": [{"type": "message", "content": "{\"ok\": true}"}]})

    client = httpx.Client(base_url="http://llm.local", transport=httpx.MockTransport(handler))
    provider = LMStudioNativeProvider(_settings(auto_load=False), client)

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
    provider = LMStudioNativeProvider(_settings(auto_load=False), client)

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
                    "context_length": 30720,
                    "eval_batch_size": 6144,
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
        "context_length": 30720,
        "eval_batch_size": 6144,
        "flash_attention": True,
        "offload_kv_cache_to_gpu": True,
        "echo_load_config": True,
    }
    assert result.type == "llm"
    assert result.instance_id == "chat-model"
    assert result.status == "loaded"
    assert result.load_config == {
        "context_length": 30720,
        "eval_batch_size": 6144,
        "flash_attention": True,
        "offload_kv_cache_to_gpu": True,
    }


def test_lm_studio_native_provider_uses_loaded_instance_when_available() -> None:
    paths: list[str] = []
    captured_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(f"{request.method} {request.url.path}")
        if request.method == "GET" and request.url.path == "/api/v1/models":
            return httpx.Response(
                200,
                json={"models": [{"key": "chat-model", "loaded_instances": [{"id": "chat-model:3"}]}]},
            )
        captured_payload.update(__import__("json").loads(request.content))
        return httpx.Response(200, json={"output": [{"type": "message", "content": "{\"ok\": true}"}]})

    client = httpx.Client(base_url="http://llm.local", transport=httpx.MockTransport(handler))
    provider = LMStudioNativeProvider(_settings(), client)

    result = provider.chat_completion("chat-model", [LLMChatMessage(role="user", content="hello")])

    assert paths == ["GET /api/v1/models", "POST /api/v1/chat"]
    assert captured_payload["model"] == "chat-model:3"
    assert result.model == "chat-model:3"


def test_lm_studio_native_provider_auto_loads_missing_configured_chat_model() -> None:
    paths: list[str] = []
    captured_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(f"{request.method} {request.url.path}")
        if request.method == "GET" and request.url.path == "/api/v1/models":
            return httpx.Response(200, json={"models": [{"key": "chat-model", "loaded_instances": []}]})
        payload = __import__("json").loads(request.content)
        captured_payloads.append(payload)
        if request.url.path == "/api/v1/models/load":
            return httpx.Response(
                200,
                json={"type": "llm", "instance_id": "chat-model:4", "load_time_seconds": 2.0, "status": "loaded"},
            )
        return httpx.Response(200, json={"output": [{"type": "message", "content": "{\"ok\": true}"}]})

    client = httpx.Client(base_url="http://llm.local", transport=httpx.MockTransport(handler))
    provider = LMStudioNativeProvider(_settings(), client)

    result = provider.chat_completion("chat-model", [LLMChatMessage(role="user", content="hello")])

    assert paths == ["GET /api/v1/models", "POST /api/v1/models/load", "POST /api/v1/chat"]
    assert captured_payloads[0]["model"] == "chat-model"
    assert captured_payloads[1]["model"] == "chat-model:4"
    assert result.model == "chat-model:4"
