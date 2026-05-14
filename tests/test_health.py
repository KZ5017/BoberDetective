from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/system/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_default_upload_limit_allows_medium_scanned_pdfs() -> None:
    get_settings.cache_clear()

    assert get_settings().max_upload_bytes == 50 * 1024 * 1024
