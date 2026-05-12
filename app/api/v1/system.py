from fastapi import APIRouter

from app.core.config import get_settings
from app.services.llm import get_llm_provider
from app.services.storage import StoragePaths

router = APIRouter()


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    storage = StoragePaths(settings.data_root)
    return {
        "status": "ok",
        "environment": settings.environment,
        "api_prefix": settings.api_prefix,
        "data_root": str(settings.data_root),
        "data_root_exists": settings.data_root.exists(),
        "data_root_writable": storage.is_data_root_writable(),
        "database_url_configured": bool(settings.database_url),
        "llm_provider": settings.llm_provider,
        "llm_base_url_configured": bool(settings.llm_base_url),
    }


@router.get("/llm/smoke")
def llm_smoke() -> dict:
    result = get_llm_provider().smoke_check()
    return {
        "provider": result.provider,
        "base_url": result.base_url,
        "reachable": result.reachable,
        "model_ids": result.model_ids,
        "configured_chat_model": result.configured_chat_model,
        "configured_chat_model_available": result.configured_chat_model_available,
        "configured_embedding_model": result.configured_embedding_model,
        "configured_embedding_model_available": result.configured_embedding_model_available,
        "error_message": result.error_message,
    }
