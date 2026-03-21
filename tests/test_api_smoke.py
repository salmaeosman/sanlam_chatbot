from app.config import get_settings
from fastapi.testclient import TestClient

from app.api import create_app


def test_health_endpoint_returns_ok(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    get_settings.cache_clear()
