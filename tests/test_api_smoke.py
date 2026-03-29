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


def test_pv_upload_rejects_unsupported_file(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        response = client.post(
            "/pv-extractions/ingest",
            headers={"Authorization": "Bearer test-token"},
            files={"file": ("note.txt", b"hello world", "text/plain")},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Format de fichier non supporte. Utilisez PDF, JPG, PNG ou WEBP."

    get_settings.cache_clear()
