from __future__ import annotations

import io
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        json_payload=None,
        headers: dict[str, str] | None = None,
        text: str | None = None,
        content: bytes | None = None,
    ) -> None:
        self.status_code = status_code
        self._json_payload = json_payload
        self.headers = headers or {}
        if text is None:
            if json_payload is None:
                text = ""
            else:
                text = json.dumps(json_payload)
        self.text = text
        self.content = content if content is not None else text.encode("utf-8")

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        if self._json_payload is None:
            raise ValueError("No JSON payload")
        return self._json_payload


def build_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        _env_file=None,
        GEMINI_API_KEY="test-key",
        USER_MGMT_API_URL="http://user-mgmt.test",
        FRONTEND_ORIGINS="http://localhost:5173",
        CHATBOT_DB_PATH=tmp_path / "data" / "chatbot.sqlite3",
    )
    return TestClient(create_app(settings))


def test_pv_upload_rejects_unsupported_file(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        services = client.app.state.services

        async def fake_get_current_user(*, token: str):
            assert token == "test-token"
            return {"id": 1, "username": "osman", "roles": ["MANAGER"]}

        services.user_mgmt.get_current_user = fake_get_current_user

        response = client.post(
            "/pv-extractions/ingest",
            headers={"Authorization": "Bearer test-token"},
            files={"file": ("note.txt", io.BytesIO(b"hello world"), "text/plain")},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Format non supporte. Utilisez PDF, JPG, PNG ou WEBP."


def test_pv_endpoints_use_python_flow_and_proxy_user_mgmt(tmp_path: Path) -> None:
    persisted_record = {
        "id": "pv-123",
        "documentName": "pv-test.pdf",
        "documentUrl": None,
        "numeroPolice": None,
        "numeroPv": "25/2026",
        "dateSurvenance": "2026-03-31",
        "heureSurvenance": "14:35",
        "ouverturePayload": {
            "numeroPermisConducteur": "P1234567",
            "categoriePermisConducteur": "B",
        },
        "ville": "Casablanca",
        "villeAr": "الدار البيضاء",
        "adresse": "Boulevard Hassan II",
        "adresseAr": "شارع الحسن الثاني",
        "victimes": [
            {
                "nom_fr": "Doe",
                "prenom_fr": "Jane",
                "cin": "AB123456",
                "etat_apres_accident": "Blessee",
                "qualite_victime": "Pieton",
                "date_naissance": "1960-09-12",
                "telephone": "0630664609",
                "itt": "30",
            }
        ],
        "nombreVictimes": 1,
        "vehicules": [
            {
                "type_fr": "Voiture",
                "marque": "Dacia",
                "plaque": "123-A-45",
                "compagnie_assurance": "Saham Assurance",
                "numero_police": "POL123",
            },
            {
                "type_fr": "Camion",
                "marque": "Isuzu",
                "plaque": "456-B-78",
                "compagnie_assurance": "AXA Assurance",
                "numero_police": "POL456",
            },
        ],
        "texteBrut": "Resume FR",
        "texteBrutAr": "ملخص",
        "statut": "termine",
        "createdAt": "2026-03-31T10:00:00Z",
        "updatedAt": "2026-03-31T10:00:00Z",
        "sourceDocumentDownloadUrl": "/pv-extractions/pv-123/source-document",
    }
    upstream_calls: list[dict[str, object]] = []

    with build_client(tmp_path) as client:
        services = client.app.state.services

        async def fake_get_current_user(*, token: str):
            assert token == "test-token"
            return {"id": 1, "username": "osman", "roles": ["MANAGER"]}

        async def fake_extract_pv_data(*, mime_type: str, file_bytes: bytes):
            assert mime_type == "application/pdf"
            assert file_bytes.startswith(b"%PDF-")
            return {
                "numero_pv": "25/2026",
                "date_survenance": "2026-03-31",
                "heure_survenance": "14:35",
                "numero_permis_conducteur": "Numero du permis: P1234567",
                "classe_permis_conducteur": "Classe du permis: b",
                "ville_fr": "Casablanca",
                "ville_ar": "الدار البيضاء",
                "adresse_fr": "Boulevard Hassan II",
                "adresse_ar": "شارع الحسن الثاني",
                "victimes": [
                    {
                        "nom_fr": "Doe",
                        "prenom_fr": "Jane",
                        "cin": "CIN N° AB 123456",
                        "etat_apres_accident": "Blessee",
                        "qualite_victime": "Pieton",
                        "date_naissance": "12/09/1960",
                        "telephone": "Tel: 06 30 664 609",
                        "itt": "ITT 30 jours",
                    },
                    {
                        "nom_fr": "Doe",
                        "prenom_fr": "Jane",
                        "cin": "AB123456",
                        "telephone": "06 30 66 46 09",
                    }
                ],
                "nombre_victimes": 2,
                "vehicules": [
                    {
                        "type_fr": "Voiture",
                        "marque": "Dacia",
                        "plaque": "123-A-45",
                        "compagnie_assurance": "Compagnie d'assurance: SAHAM assurances",
                        "numero_police": "Numero de police: POL123",
                    },
                    {
                        "type_fr": "Camion",
                        "marque": "Isuzu",
                        "plaque": "456-B-78",
                        "compagnie_assurance": "Compagnie adverse: AXA Assurance",
                        "numero_police": "Numero de police: POL456",
                    },
                ],
                "texte_brut_fr": "Resume FR",
                "texte_brut_ar": "ملخص",
            }

        async def fake_request(method: str, url: str, **kwargs):
            upstream_calls.append({"method": method, "url": url, **kwargs})

            if method == "POST" and url == "/pv-extractions/agent-ingest":
                files = kwargs["files"]
                assert files["file"][0] == "pv-test.pdf"
                assert files["file"][2] == "application/pdf"
                extracted_json = files["extractedData"][1]
                assert '"numero_pv": "25/2026"' in extracted_json
                assert '"heure_survenance": "14:35"' in extracted_json
                assert '"numero_permis_conducteur": "P1234567"' in extracted_json
                assert '"classe_permis_conducteur": "B"' in extracted_json
                assert '"cin": "AB123456"' in extracted_json
                assert '"date_naissance": "1960-09-12"' in extracted_json
                assert '"telephone": "0630664609"' in extracted_json
                assert '"itt": "30"' in extracted_json
                assert extracted_json.count('"cin": "AB123456"') == 1
                assert '"nombre_victimes": 1' in extracted_json
                assert '"compagnie_assurance": "Saham Assurance"' in extracted_json
                assert '"compagnie_assurance": "AXA Assurance"' in extracted_json
                assert '"numero_police": "POL123"' in extracted_json
                assert '"numero_police": "POL456"' in extracted_json
                return _FakeResponse(
                    status_code=201,
                    json_payload=persisted_record,
                    headers={"content-type": "application/json"},
                )

            if method == "GET" and url == "/pv-extractions":
                assert kwargs["params"] == {"search": "pv"}
                return _FakeResponse(
                    status_code=200,
                    json_payload=[persisted_record],
                    headers={"content-type": "application/json"},
                )

            if method == "GET" and url == "/pv-extractions/stats":
                return _FakeResponse(
                    status_code=200,
                    json_payload={
                        "total": 1,
                        "enCoursCount": 0,
                        "termineCount": 1,
                        "erreurCount": 0,
                        "withVictimsCount": 1,
                        "byStatus": [{"status": "termine", "total": 1}],
                    },
                    headers={"content-type": "application/json"},
                )

            if method == "GET" and url == "/pv-extractions/pv-123/source-document":
                return _FakeResponse(
                    status_code=200,
                    headers={
                        "content-type": "application/pdf",
                        "content-disposition": 'attachment; filename="pv-test.pdf"',
                    },
                    text="",
                    content=b"%PDF-1.4\n...",
                )

            raise AssertionError(f"Unexpected upstream call: {method} {url}")

        services.user_mgmt.get_current_user = fake_get_current_user
        services.gemini.extract_pv_data = fake_extract_pv_data
        services.user_mgmt.client.request = fake_request

        upload_response = client.post(
            "/pv-extractions/ingest",
            headers={"Authorization": "Bearer test-token"},
            files={"file": ("pv-test.pdf", io.BytesIO(b"%PDF-1.4\nsample"), "application/pdf")},
        )

        assert upload_response.status_code == 201
        upload_payload = upload_response.json()
        assert upload_payload["documentName"] == "pv-test.pdf"
        assert upload_payload["numeroPv"] == "25/2026"
        assert upload_payload["heureSurvenance"] == "14:35"
        assert upload_payload["ouverturePayload"]["numeroPermisConducteur"] == "P1234567"
        assert upload_payload["ouverturePayload"]["categoriePermisConducteur"] == "B"
        assert upload_payload["victimes"][0]["cin"] == "AB123456"
        assert upload_payload["victimes"][0]["date_naissance"] == "1960-09-12"
        assert upload_payload["victimes"][0]["telephone"] == "0630664609"
        assert upload_payload["victimes"][0]["itt"] == "30"
        assert upload_payload["extractedBy"] == "back-python"
        assert upload_payload["requestedBy"] == "osman"

        list_response = client.get(
            "/pv-extractions",
            headers={"Authorization": "Bearer test-token"},
            params={"search": "pv"},
        )
        assert list_response.status_code == 200
        assert list_response.json()[0]["id"] == "pv-123"

        stats_response = client.get(
            "/pv-extractions/stats",
            headers={"Authorization": "Bearer test-token"},
        )
        assert stats_response.status_code == 200
        assert stats_response.json()["termineCount"] == 1

        download_response = client.get(
            "/pv-extractions/pv-123/source-document",
            headers={"Authorization": "Bearer test-token"},
        )
        assert download_response.status_code == 200
        assert download_response.headers["content-type"] == "application/pdf"
        assert download_response.headers["content-disposition"] == 'attachment; filename="pv-test.pdf"'
        assert download_response.content.startswith(b"%PDF-1.4")

        assert [call["url"] for call in upstream_calls] == [
            "/pv-extractions/agent-ingest",
            "/pv-extractions",
            "/pv-extractions/stats",
            "/pv-extractions/pv-123/source-document",
        ]
