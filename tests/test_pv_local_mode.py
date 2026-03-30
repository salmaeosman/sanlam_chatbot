from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings


def build_local_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        _env_file=None,
        gemini_api_key="",
        user_mgmt_api_url="",
        frontend_origins_raw="http://localhost:5173",
        chatbot_db_path=tmp_path / "data" / "chatbot.sqlite3",
        pv_db_path=tmp_path / "data" / "pv_records.sqlite3",
        pv_upload_dir=tmp_path / "data" / "pv_uploads",
    )
    return TestClient(create_app(settings))


def test_local_pv_flow_is_standalone(tmp_path: Path) -> None:
    with build_local_client(tmp_path) as client:
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        upload_response = client.post(
            "/pv-extractions/ingest",
            headers={"Authorization": "Bearer test-token"},
            files={"file": ("pv-test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )

        assert upload_response.status_code == 200
        payload = upload_response.json()
        assert payload["document_name"] == "pv-test.pdf"
        assert payload["source_document_download_url"].endswith("/source-document")

        list_response = client.get(
            "/pv-extractions",
            headers={"Authorization": "Bearer test-token"},
        )
        assert list_response.status_code == 200
        records = list_response.json()
        assert len(records) == 1
        assert records[0]["id"] == payload["id"]

        stats_response = client.get(
            "/api/v1/pv-extractions/stats",
            headers={"Authorization": "Bearer test-token"},
        )
        assert stats_response.status_code == 200
        assert stats_response.json()["total"] == 1

        patch_response = client.patch(
            f"/pv-extractions/{payload['id']}",
            headers={"Authorization": "Bearer test-token"},
            json={"statut": "termine", "ville": "Casablanca"},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["ville"] == "Casablanca"

        delete_response = client.delete(
            f"/pv-extractions/{payload['id']}",
            headers={"Authorization": "Bearer test-token"},
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["deleted"] is True
