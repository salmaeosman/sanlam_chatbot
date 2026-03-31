from app.config import get_settings
from fastapi.testclient import TestClient

from app.api import create_app


def test_health_endpoint_returns_ok(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        response = client.get("/health")

        assert response.status_code == 200
        payload = response.json()

        assert payload["status"] == "ok"
        assert payload["llmConfigured"] is False
        assert "llmBaseUrl" not in payload
        assert "userMgmtApiUrl" not in payload
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["cache-control"] == "no-store"

    get_settings.cache_clear()
