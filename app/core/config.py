from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


def _getenv(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _getenv_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    environment: str
    data_root: Path
    api_prefix: str
    database_url: str
    llm_provider: str
    llm_base_url: str
    llm_api_key: str
    llm_chat_model: str
    llm_embedding_model: str
    llm_timeout_seconds: float
    llm_context_length: int
    llm_eval_batch_size: int
    llm_flash_attention: bool
    llm_offload_kv_cache_to_gpu: bool
    llm_auto_load_chat_model: bool
    max_upload_bytes: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_root = Path(_getenv("BOBERDETECTIVE_DATA_ROOT", "/home/bober/boberdetective-data")).expanduser()
    return Settings(
        environment=_getenv("BOBERDETECTIVE_ENV", "development"),
        data_root=data_root,
        api_prefix=_getenv("BOBERDETECTIVE_API_PREFIX", "/api/v1"),
        database_url=_getenv(
            "BOBERDETECTIVE_DATABASE_URL",
            "postgresql+psycopg://boberdetective:boberdetective_dev_password@127.0.0.1:5432/boberdetective",
        ),
        llm_provider=_getenv("BOBERDETECTIVE_LLM_PROVIDER", "lm_studio"),
        llm_base_url=_getenv("BOBERDETECTIVE_LLM_BASE_URL", "http://127.0.0.1:1234/v1"),
        llm_api_key=_getenv("BOBERDETECTIVE_LLM_API_KEY", "lm-studio"),
        llm_chat_model=_getenv("BOBERDETECTIVE_LLM_CHAT_MODEL", "qwen/qwen3.5-9b"),
        llm_embedding_model=_getenv("BOBERDETECTIVE_LLM_EMBEDDING_MODEL", "text-embedding-nomic-embed-text-v1.5"),
        llm_timeout_seconds=float(_getenv("BOBERDETECTIVE_LLM_TIMEOUT_SECONDS", "120")),
        llm_context_length=int(_getenv("BOBERDETECTIVE_LLM_CONTEXT_LENGTH", "4096")),
        llm_eval_batch_size=int(_getenv("BOBERDETECTIVE_LLM_EVAL_BATCH_SIZE", "4096")),
        llm_flash_attention=_getenv_bool("BOBERDETECTIVE_LLM_FLASH_ATTENTION", True),
        llm_offload_kv_cache_to_gpu=_getenv_bool("BOBERDETECTIVE_LLM_OFFLOAD_KV_CACHE_TO_GPU", True),
        llm_auto_load_chat_model=_getenv_bool("BOBERDETECTIVE_LLM_AUTO_LOAD_CHAT_MODEL", True),
        max_upload_bytes=int(_getenv("BOBERDETECTIVE_MAX_UPLOAD_BYTES", "5242880")),
    )
