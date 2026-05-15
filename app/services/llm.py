from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings


class LLMProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMModel:
    id: str


@dataclass(frozen=True)
class LLMChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMChatCompletion:
    model: str
    content: str


@dataclass(frozen=True)
class LLMEmbeddingResult:
    model: str
    embeddings: list[list[float]]


@dataclass(frozen=True)
class LLMSmokeResult:
    provider: str
    base_url: str
    reachable: bool
    model_ids: list[str]
    configured_chat_model: str
    configured_chat_model_available: bool | None
    configured_chat_model_loaded: bool | None
    configured_embedding_model: str
    configured_embedding_model_available: bool | None
    configured_embedding_model_loaded: bool | None
    loaded_model_ids: list[str]
    error_message: str | None = None


@dataclass(frozen=True)
class LLMModelLoadResult:
    type: str
    instance_id: str
    load_time_seconds: float | None
    status: str
    load_config: dict | None


class LLMProvider(Protocol):
    provider_name: str

    def list_models(self) -> list[LLMModel]:
        raise NotImplementedError

    def smoke_check(self) -> LLMSmokeResult:
        raise NotImplementedError

    def chat_completion(
        self,
        model: str,
        messages: list[LLMChatMessage],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> LLMChatCompletion:
        raise NotImplementedError

    def embeddings(self, model: str, texts: list[str]) -> LLMEmbeddingResult:
        raise NotImplementedError


class OpenAICompatibleLocalProvider:
    provider_name = "openai_compatible_local"

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        native_client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client
        self._native_client = native_client
        self._loaded_embedding_model_instance_id: str | None = None

    def list_models(self) -> list[LLMModel]:
        client = self._client or self._build_client()
        close_client = self._client is None
        try:
            response = client.get("/models")
            response.raise_for_status()
            payload = response.json()
            models = payload.get("data")
            if not isinstance(models, list):
                raise LLMProviderError("LLM provider returned an invalid models payload")
            return [LLMModel(id=str(item["id"])) for item in models if isinstance(item, dict) and item.get("id")]
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(_http_status_error_message(exc)) from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise LLMProviderError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

    def smoke_check(self) -> LLMSmokeResult:
        try:
            models = self.list_models()
            model_ids = [model.id for model in models]
            loaded_model_ids = _safe_loaded_model_instance_ids(self._settings, self._native_client)
            return LLMSmokeResult(
                provider=self._settings.llm_provider,
                base_url=self._settings.llm_base_url,
                reachable=True,
                model_ids=model_ids,
                configured_chat_model=self._settings.llm_chat_model,
                configured_chat_model_available=_model_available(self._settings.llm_chat_model, model_ids),
                configured_chat_model_loaded=_model_loaded(self._settings.llm_chat_model, loaded_model_ids),
                configured_embedding_model=self._settings.llm_embedding_model,
                configured_embedding_model_available=_model_available(self._settings.llm_embedding_model, model_ids),
                configured_embedding_model_loaded=_model_loaded(self._settings.llm_embedding_model, loaded_model_ids),
                loaded_model_ids=loaded_model_ids,
            )
        except LLMProviderError as exc:
            return LLMSmokeResult(
                provider=self._settings.llm_provider,
                base_url=self._settings.llm_base_url,
                reachable=False,
                model_ids=[],
                configured_chat_model=self._settings.llm_chat_model,
                configured_chat_model_available=None,
                configured_chat_model_loaded=None,
                configured_embedding_model=self._settings.llm_embedding_model,
                configured_embedding_model_available=None,
                configured_embedding_model_loaded=None,
                loaded_model_ids=[],
                error_message=str(exc),
            )

    def chat_completion(
        self,
        model: str,
        messages: list[LLMChatMessage],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> LLMChatCompletion:
        client = self._client or self._build_client()
        close_client = self._client is None
        try:
            response = client.post(
                "/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": message.role, "content": message.content} for message in messages],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            payload = response.json()
            choices = payload.get("choices")
            if not isinstance(choices, list) or not choices:
                raise LLMProviderError("LLM provider returned no chat choices")
            message = choices[0].get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise LLMProviderError("LLM provider returned an invalid chat payload")
            return LLMChatCompletion(model=model, content=message["content"])
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(_http_status_error_message(exc)) from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise LLMProviderError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

    def embeddings(self, model: str, texts: list[str]) -> LLMEmbeddingResult:
        if not texts:
            return LLMEmbeddingResult(model=model, embeddings=[])
        client = self._client or self._build_client()
        close_client = self._client is None
        try:
            embedding_model = (
                LMStudioNativeProvider(self._settings, self._native_client).ensure_configured_embedding_model_loaded()
                if self._settings.llm_auto_load_embedding_model
                and self._settings.llm_provider == "lm_studio"
                and model == self._settings.llm_embedding_model
                else model
            )
            response = client.post(
                "/embeddings",
                json={
                    "model": embedding_model,
                    "input": texts,
                },
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data")
            if not isinstance(data, list):
                raise LLMProviderError("LLM provider returned an invalid embeddings payload")
            embeddings_by_index: dict[int, list[float]] = {}
            for item in data:
                if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
                    raise LLMProviderError("LLM provider returned an invalid embedding item")
                index = int(item.get("index", len(embeddings_by_index)))
                embedding = [_as_float(value) for value in item["embedding"]]
                embeddings_by_index[index] = embedding
            embeddings = [embeddings_by_index[index] for index in sorted(embeddings_by_index)]
            if len(embeddings) != len(texts):
                raise LLMProviderError("LLM provider returned a different number of embeddings")
            dimensions = {len(embedding) for embedding in embeddings}
            if len(dimensions) > 1 or 0 in dimensions:
                raise LLMProviderError("LLM provider returned invalid embedding dimensions")
            return LLMEmbeddingResult(model=str(payload.get("model", embedding_model)), embeddings=embeddings)
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(_http_status_error_message(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(_http_status_error_message(exc)) from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise LLMProviderError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

    def _build_client(self) -> httpx.Client:
        headers = {}
        if self._settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self._settings.llm_api_key}"
        return httpx.Client(
            base_url=self._settings.llm_base_url.rstrip("/"),
            timeout=self._settings.llm_timeout_seconds,
            headers=headers,
        )


class LMStudioNativeProvider:
    provider_name = "lm_studio_native"

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = client
        self._loaded_chat_model_instance_id: str | None = None
        self._loaded_embedding_model_instance_id: str | None = None

    def list_models(self) -> list[LLMModel]:
        client = self._client or self._build_client()
        close_client = self._client is None
        try:
            response = client.get("/api/v1/models")
            response.raise_for_status()
            payload = response.json()
            models = payload.get("models")
            if not isinstance(models, list):
                raise LLMProviderError("LM Studio native API returned an invalid models payload")
            model_ids: list[str] = []
            for item in models:
                if not isinstance(item, dict):
                    continue
                loaded_instances = item.get("loaded_instances")
                if isinstance(loaded_instances, list):
                    model_ids.extend(
                        str(instance["id"])
                        for instance in loaded_instances
                        if isinstance(instance, dict) and instance.get("id")
                    )
                elif item.get("key"):
                    model_ids.append(str(item["key"]))
            return [LLMModel(id=model_id) for model_id in model_ids]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise LLMProviderError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

    def smoke_check(self) -> LLMSmokeResult:
        try:
            models = self.list_models()
            model_ids = [model.id for model in models]
            loaded_model_ids = self.loaded_model_instance_ids()
            return LLMSmokeResult(
                provider=self.provider_name,
                base_url=self._native_base_url,
                reachable=True,
                model_ids=model_ids,
                configured_chat_model=self._settings.llm_chat_model,
                configured_chat_model_available=_model_available(self._settings.llm_chat_model, model_ids),
                configured_chat_model_loaded=_model_loaded(self._settings.llm_chat_model, loaded_model_ids),
                configured_embedding_model=self._settings.llm_embedding_model,
                configured_embedding_model_available=_model_available(self._settings.llm_embedding_model, model_ids),
                configured_embedding_model_loaded=_model_loaded(self._settings.llm_embedding_model, loaded_model_ids),
                loaded_model_ids=loaded_model_ids,
            )
        except LLMProviderError as exc:
            return LLMSmokeResult(
                provider=self.provider_name,
                base_url=self._native_base_url,
                reachable=False,
                model_ids=[],
                configured_chat_model=self._settings.llm_chat_model,
                configured_chat_model_available=None,
                configured_chat_model_loaded=None,
                configured_embedding_model=self._settings.llm_embedding_model,
                configured_embedding_model_available=None,
                configured_embedding_model_loaded=None,
                loaded_model_ids=[],
                error_message=str(exc),
            )

    def loaded_model_instance_ids(self) -> list[str]:
        client = self._client or self._build_client()
        close_client = self._client is None
        try:
            response = client.get("/api/v1/models")
            response.raise_for_status()
            payload = response.json()
            models = payload.get("models")
            if not isinstance(models, list):
                raise LLMProviderError("LM Studio native API returned an invalid models payload")
            instance_ids: list[str] = []
            for item in models:
                if not isinstance(item, dict):
                    continue
                loaded_instances = item.get("loaded_instances")
                if not isinstance(loaded_instances, list):
                    continue
                instance_ids.extend(
                    str(instance["id"])
                    for instance in loaded_instances
                    if isinstance(instance, dict) and instance.get("id")
                )
            return instance_ids
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise LLMProviderError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

    def ensure_configured_chat_model_loaded(self) -> str:
        instance_id = self._matching_loaded_instance_id(self._settings.llm_chat_model, self._loaded_chat_model_instance_id)
        if instance_id is not None:
            self._loaded_chat_model_instance_id = instance_id
            return instance_id
        result = self.load_configured_chat_model()
        if result.status != "loaded" or result.instance_id == "":
            raise LLMProviderError("LM Studio did not return a loaded chat model instance")
        self._loaded_chat_model_instance_id = result.instance_id
        return result.instance_id

    def ensure_configured_embedding_model_loaded(self) -> str:
        instance_id = self._matching_loaded_instance_id(self._settings.llm_embedding_model, self._loaded_embedding_model_instance_id)
        if instance_id is not None:
            self._loaded_embedding_model_instance_id = instance_id
            return instance_id
        result = self.load_configured_embedding_model()
        if result.status != "loaded" or result.instance_id == "":
            raise LLMProviderError("LM Studio did not return a loaded embedding model instance")
        self._loaded_embedding_model_instance_id = result.instance_id
        return result.instance_id

    def _matching_loaded_instance_id(self, configured_model: str, cached_instance_id: str | None) -> str | None:
        instance_ids = self.loaded_model_instance_ids()
        if cached_instance_id in instance_ids:
            return cached_instance_id
        for instance_id in instance_ids:
            if _is_instance_of_model(instance_id, configured_model):
                return instance_id
        return None

    def load_configured_chat_model(self) -> LLMModelLoadResult:
        client = self._client or self._build_client()
        close_client = self._client is None
        try:
            response = client.post(
                "/api/v1/models/load",
                json={
                    "model": self._settings.llm_chat_model,
                    "context_length": self._settings.llm_context_length,
                    "eval_batch_size": self._settings.llm_eval_batch_size,
                    "flash_attention": self._settings.llm_flash_attention,
                    "offload_kv_cache_to_gpu": self._settings.llm_offload_kv_cache_to_gpu,
                    "echo_load_config": True,
                },
            )
            response.raise_for_status()
            payload = response.json()
            return LLMModelLoadResult(
                type=str(payload.get("type", "")),
                instance_id=str(payload.get("instance_id", "")),
                load_time_seconds=_optional_float(payload.get("load_time_seconds")),
                status=str(payload.get("status", "")),
                load_config=payload.get("load_config") if isinstance(payload.get("load_config"), dict) else None,
            )
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(_http_status_error_message(exc)) from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise LLMProviderError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

    def load_configured_embedding_model(self) -> LLMModelLoadResult:
        client = self._client or self._build_client()
        close_client = self._client is None
        try:
            response = client.post(
                "/api/v1/models/load",
                json={
                    "model": self._settings.llm_embedding_model,
                    "context_length": self._settings.llm_context_length,
                    "echo_load_config": True,
                },
            )
            response.raise_for_status()
            payload = response.json()
            return LLMModelLoadResult(
                type=str(payload.get("type", "")),
                instance_id=str(payload.get("instance_id", "")),
                load_time_seconds=_optional_float(payload.get("load_time_seconds")),
                status=str(payload.get("status", "")),
                load_config=payload.get("load_config") if isinstance(payload.get("load_config"), dict) else None,
            )
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(_http_status_error_message(exc)) from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise LLMProviderError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

    def chat_completion(
        self,
        model: str,
        messages: list[LLMChatMessage],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> LLMChatCompletion:
        client = self._client or self._build_client()
        close_client = self._client is None
        try:
            chat_model = (
                self.ensure_configured_chat_model_loaded()
                if self._settings.llm_auto_load_chat_model and model == self._settings.llm_chat_model
                else model
            )
            system_prompt, user_messages = _split_system_prompt(messages)
            payload = {
                "model": chat_model,
                "input": [{"type": "text", "content": _messages_to_native_input(user_messages)}],
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "store": False,
            }
            if _supports_native_reasoning_toggle(chat_model):
                payload["reasoning"] = "off"
            response = client.post(
                "/api/v1/chat",
                json=payload,
            )
            response.raise_for_status()
            payload = response.json()
            output = payload.get("output")
            if not isinstance(output, list) or not output:
                raise LLMProviderError("LM Studio native API returned no output")
            content_parts = [
                str(item["content"])
                for item in output
                if isinstance(item, dict) and item.get("type") == "message" and isinstance(item.get("content"), str)
            ]
            if not content_parts:
                raise LLMProviderError("LM Studio native API returned no message content")
            return LLMChatCompletion(model=chat_model, content="\n".join(content_parts))
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise LLMProviderError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

    def _build_client(self) -> httpx.Client:
        headers = {}
        if self._settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self._settings.llm_api_key}"
        return httpx.Client(
            base_url=self._native_base_url,
            timeout=self._settings.llm_timeout_seconds,
            headers=headers,
        )

    @property
    def _native_base_url(self) -> str:
        return self._settings.llm_base_url.rstrip("/").removesuffix("/v1")


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if settings.llm_provider != "lm_studio":
        raise LLMProviderError(f"Unsupported LLM provider: {settings.llm_provider}")
    return OpenAICompatibleLocalProvider(settings)


def _model_available(configured_model: str, model_ids: list[str]) -> bool | None:
    if configured_model == "":
        return None
    return configured_model in model_ids


def _model_loaded(configured_model: str, loaded_model_ids: list[str]) -> bool | None:
    if configured_model == "":
        return None
    return any(_is_instance_of_model(instance_id, configured_model) for instance_id in loaded_model_ids)


def _safe_loaded_model_instance_ids(settings: Settings, client: httpx.Client | None = None) -> list[str]:
    if settings.llm_provider != "lm_studio":
        return []
    try:
        return LMStudioNativeProvider(settings, client).loaded_model_instance_ids()
    except LLMProviderError:
        return []


def _messages_to_native_input(messages: list[LLMChatMessage]) -> str:
    return "\n\n".join(f"{message.role.upper()}:\n{message.content}" for message in messages)


def _split_system_prompt(messages: list[LLMChatMessage]) -> tuple[str, list[LLMChatMessage]]:
    system_messages = [message.content for message in messages if message.role == "system"]
    user_messages = [message for message in messages if message.role != "system"]
    return "\n\n".join(system_messages), user_messages


def _supports_native_reasoning_toggle(model: str) -> bool:
    return "qwen" in model.casefold()


def _is_instance_of_model(instance_id: str, configured_model: str) -> bool:
    return instance_id == configured_model or instance_id.startswith(f"{configured_model}:")


def _optional_float(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _as_float(value) -> float:
    if isinstance(value, bool):
        raise ValueError("Boolean embedding value is invalid")
    return float(value)


def _http_status_error_message(exc: httpx.HTTPStatusError) -> str:
    detail = exc.response.text.strip()
    if detail:
        return f"{exc.response.status_code} {exc.response.reason_phrase}: {detail}"
    return str(exc)
