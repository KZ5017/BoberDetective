from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


def _getenv(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


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
        max_upload_bytes=int(_getenv("BOBERDETECTIVE_MAX_UPLOAD_BYTES", "5242880")),
    )
