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
class LLMSmokeResult:
    provider: str
    base_url: str
    reachable: bool
    model_ids: list[str]
    configured_chat_model: str
    configured_chat_model_available: bool | None
    configured_embedding_model: str
    configured_embedding_model_available: bool | None
    error_message: str | None = None


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


class OpenAICompatibleLocalProvider:
    provider_name = "openai_compatible_local"

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = client

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
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise LLMProviderError(str(exc)) from exc
        finally:
            if close_client:
                client.close()

    def smoke_check(self) -> LLMSmokeResult:
        try:
            models = self.list_models()
            model_ids = [model.id for model in models]
            return LLMSmokeResult(
                provider=self._settings.llm_provider,
                base_url=self._settings.llm_base_url,
                reachable=True,
                model_ids=model_ids,
                configured_chat_model=self._settings.llm_chat_model,
                configured_chat_model_available=_model_available(self._settings.llm_chat_model, model_ids),
                configured_embedding_model=self._settings.llm_embedding_model,
                configured_embedding_model_available=_model_available(self._settings.llm_embedding_model, model_ids),
            )
        except LLMProviderError as exc:
            return LLMSmokeResult(
                provider=self._settings.llm_provider,
                base_url=self._settings.llm_base_url,
                reachable=False,
                model_ids=[],
                configured_chat_model=self._settings.llm_chat_model,
                configured_chat_model_available=None,
                configured_embedding_model=self._settings.llm_embedding_model,
                configured_embedding_model_available=None,
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
            return LLMSmokeResult(
                provider=self.provider_name,
                base_url=self._native_base_url,
                reachable=True,
                model_ids=model_ids,
                configured_chat_model=self._settings.llm_chat_model,
                configured_chat_model_available=_model_available(self._settings.llm_chat_model, model_ids),
                configured_embedding_model=self._settings.llm_embedding_model,
                configured_embedding_model_available=_model_available(self._settings.llm_embedding_model, model_ids),
            )
        except LLMProviderError as exc:
            return LLMSmokeResult(
                provider=self.provider_name,
                base_url=self._native_base_url,
                reachable=False,
                model_ids=[],
                configured_chat_model=self._settings.llm_chat_model,
                configured_chat_model_available=None,
                configured_embedding_model=self._settings.llm_embedding_model,
                configured_embedding_model_available=None,
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
            system_prompt, user_messages = _split_system_prompt(messages)
            payload = {
                "model": model,
                "input": [{"type": "text", "content": _messages_to_native_input(user_messages)}],
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "store": False,
            }
            if _supports_native_reasoning_toggle(model):
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
            return LLMChatCompletion(model=model, content="\n".join(content_parts))
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


def _messages_to_native_input(messages: list[LLMChatMessage]) -> str:
    return "\n\n".join(f"{message.role.upper()}:\n{message.content}" for message in messages)


def _split_system_prompt(messages: list[LLMChatMessage]) -> tuple[str, list[LLMChatMessage]]:
    system_messages = [message.content for message in messages if message.role == "system"]
    user_messages = [message for message in messages if message.role != "system"]
    return "\n\n".join(system_messages), user_messages


def _supports_native_reasoning_toggle(model: str) -> bool:
    return "qwen" in model.casefold()
