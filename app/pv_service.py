from __future__ import annotations

import base64
import binascii
import hashlib
import json
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException, UploadFile, status

from app.config import Settings
from app.pv_extraction import LocalPvExtractor, normalize_upstream_record
from app.pv_store import PvRecordStore
from app.user_mgmt_client import AuthenticationError, UserMgmtClient


SAFE_UPLOAD_EXTENSION_BY_MIME = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class PvService:
    def __init__(self, settings: Settings, user_mgmt: UserMgmtClient) -> None:
        self.settings = settings
        self.user_mgmt = user_mgmt
        self.store = PvRecordStore(settings.pv_db_path)
        self.extractor = LocalPvExtractor()
        self.settings.pv_upload_dir.mkdir(parents=True, exist_ok=True)

    async def list_records(self, *, base_url: str, token: str) -> list[dict[str, Any]]:
        owner_ref = await self._resolve_owner_ref(token)
        records = self.store.list_records(owner_ref)
        return [self._serialize_record(base_url=base_url, record=record) for record in records]

    async def get_stats(self, *, token: str) -> dict[str, int]:
        owner_ref = await self._resolve_owner_ref(token)
        return self.store.get_stats(owner_ref)

    async def get_record(self, *, base_url: str, token: str, record_id: str) -> dict[str, Any]:
        owner_ref = await self._resolve_owner_ref(token)
        record = self.store.get_record(owner_ref, record_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enregistrement introuvable.")
        return self._serialize_record(base_url=base_url, record=record)

    async def ingest_record(self, *, base_url: str, token: str, file: UploadFile) -> dict[str, Any]:
        try:
            file_bytes = await file.read()
        finally:
            await file.close()

        file_name, mime_type = validate_pv_upload(
            file_name=file.filename,
            declared_mime_type=file.content_type,
            file_bytes=file_bytes,
            settings=self.settings,
        )

        owner_ref = await self._resolve_owner_ref(token)
        upload_path = self._persist_upload(file_name=file_name, mime_type=mime_type, file_bytes=file_bytes)
        extracted_payload = await self._extract_payload(
            upload_path=upload_path,
            file_name=file_name,
            mime_type=mime_type,
            token=token,
        )

        timestamp = utc_now_iso()
        persisted = self.store.create_record(
            {
                "id": str(uuid4()),
                "owner_ref": owner_ref,
                "document_name": extracted_payload.get("document_name") or file_name,
                "document_url": None,
                "numero_police": extracted_payload.get("numero_police"),
                "date_survenance": extracted_payload.get("date_survenance"),
                "ville": extracted_payload.get("ville"),
                "ville_ar": extracted_payload.get("ville_ar"),
                "adresse": extracted_payload.get("adresse"),
                "adresse_ar": extracted_payload.get("adresse_ar"),
                "victimes": extracted_payload.get("victimes", []),
                "nombre_victimes": int(extracted_payload.get("nombre_victimes", 0) or 0),
                "vehicules": extracted_payload.get("vehicules", []),
                "texte_brut": extracted_payload.get("texte_brut"),
                "texte_brut_ar": extracted_payload.get("texte_brut_ar"),
                "statut": extracted_payload.get("statut") or "termine",
                "created_at": timestamp,
                "updated_at": timestamp,
                "source_document_path": str(upload_path),
            }
        )
        return self._serialize_record(base_url=base_url, record=persisted)

    async def update_record(
        self,
        *,
        base_url: str,
        token: str,
        record_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        owner_ref = await self._resolve_owner_ref(token)
        existing = self.store.get_record(owner_ref, record_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enregistrement introuvable.")

        changes = normalize_update_payload(payload, existing)
        changes["updated_at"] = utc_now_iso()
        updated = self.store.update_record(owner_ref, record_id, changes)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enregistrement introuvable.")
        return self._serialize_record(base_url=base_url, record=updated)

    async def delete_record(self, *, token: str, record_id: str) -> dict[str, Any]:
        owner_ref = await self._resolve_owner_ref(token)
        record = self.store.delete_record(owner_ref, record_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enregistrement introuvable.")

        source_path = Path(record["source_document_path"])
        if source_path.exists():
            source_path.unlink()

        return {"deleted": True, "id": record_id}

    async def get_source_document(self, *, token: str, record_id: str) -> tuple[Path, str]:
        owner_ref = await self._resolve_owner_ref(token)
        record = self.store.get_record(owner_ref, record_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable.")

        source_path = Path(record["source_document_path"])
        if not source_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fichier source introuvable.")
        return source_path, record["document_name"]

    async def _resolve_owner_ref(self, token: str) -> str:
        claims = decode_jwt_claims(token)
        user_context: dict[str, Any] | None = None

        if self.settings.user_mgmt_api_url.strip():
            try:
                user_context = await self.user_mgmt.get_current_user(token=token)
            except AuthenticationError as error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=str(error),
                ) from error
            except httpx.HTTPError:
                user_context = None

        return resolve_owner_ref(token=token, claims=claims, user_context=user_context)

    async def _extract_payload(
        self,
        *,
        upload_path: Path,
        file_name: str,
        mime_type: str,
        token: str,
    ) -> dict[str, Any]:
        if self.settings.pv_remote_ingest_url.strip():
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            try:
                with upload_path.open("rb") as stream:
                    files = {"file": (file_name, stream, mime_type)}
                    async with httpx.AsyncClient(timeout=self.settings.pv_remote_ingest_timeout_seconds) as client:
                        response = await client.post(
                            self.settings.pv_remote_ingest_url,
                            headers=headers,
                            files=files,
                        )
                if response.is_success:
                    payload = response.json()
                    if isinstance(payload, dict):
                        return normalize_upstream_record(payload, file_name)
            except (OSError, httpx.HTTPError, ValueError):
                pass

        return self.extractor.extract(upload_path, file_name)

    def _persist_upload(self, *, file_name: str, mime_type: str, file_bytes: bytes) -> Path:
        extension = SAFE_UPLOAD_EXTENSION_BY_MIME.get(mime_type) or Path(file_name).suffix or ".bin"
        target_path = self.settings.pv_upload_dir / f"{uuid4()}{extension}"
        target_path.write_bytes(file_bytes)
        return target_path

    def _serialize_record(self, *, base_url: str, record: dict[str, Any]) -> dict[str, Any]:
        normalized_base_url = base_url.rstrip("/")
        download_url = f"{normalized_base_url}/pv-extractions/{record['id']}/source-document"
        return {
            "id": record["id"],
            "document_name": record["document_name"],
            "document_url": record.get("document_url") or download_url,
            "numero_police": record.get("numero_police"),
            "date_survenance": record.get("date_survenance"),
            "ville": record.get("ville"),
            "ville_ar": record.get("ville_ar"),
            "adresse": record.get("adresse"),
            "adresse_ar": record.get("adresse_ar"),
            "victimes": record.get("victimes", []),
            "nombre_victimes": int(record.get("nombre_victimes", 0) or 0),
            "vehicules": record.get("vehicules", []),
            "texte_brut": record.get("texte_brut"),
            "texte_brut_ar": record.get("texte_brut_ar"),
            "statut": record.get("statut", "en_cours"),
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "source_document_download_url": download_url,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def decode_jwt_claims(token: str | None) -> dict[str, Any]:
    if not token:
        return {}

    parts = token.split(".")
    if len(parts) < 2:
        return {}

    payload = parts[1]
    payload += "=" * (-len(payload) % 4)

    try:
        decoded = base64.urlsafe_b64decode(payload.encode("utf-8"))
        parsed = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error):
        return {}

    return parsed if isinstance(parsed, dict) else {}


def resolve_owner_ref(token: str | None, claims: dict[str, Any], user_context: dict[str, Any] | None) -> str:
    for source in (user_context or {}, claims):
        for key in ("id", "sub", "user_id", "username", "preferred_username", "email"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, int):
                return str(value)

    if token:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    return "anonymous"


def validate_pv_upload(
    *,
    file_name: str | None,
    declared_mime_type: str | None,
    file_bytes: bytes,
    settings: Settings,
) -> tuple[str, str]:
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier envoye est vide",
        )

    if len(file_bytes) > settings.pv_upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Le fichier depasse la limite autorisee de {settings.pv_upload_max_bytes // (1024 * 1024)} Mo",
        )

    sniffed_mime_type = sniff_pv_mime_type(file_bytes)
    declared = normalize_mime_type(declared_mime_type)
    allowed_types = settings.pv_upload_allowed_types

    if sniffed_mime_type is None or sniffed_mime_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format de fichier non supporte. Utilisez PDF, JPG, PNG ou WEBP.",
        )

    if declared and declared != "application/octet-stream" and declared not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le type MIME du fichier n'est pas autorise",
        )

    if declared and declared != "application/octet-stream" and declared != sniffed_mime_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le type MIME du fichier ne correspond pas a son contenu",
        )

    return sanitize_upload_filename(file_name, sniffed_mime_type=sniffed_mime_type), sniffed_mime_type


def normalize_mime_type(value: str | None) -> str:
    if not value:
        return ""
    return value.split(";", 1)[0].strip().lower()


def sniff_pv_mime_type(file_bytes: bytes) -> str | None:
    if file_bytes.startswith(b"%PDF-"):
        return "application/pdf"
    if file_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(file_bytes) >= 12 and file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
        return "image/webp"
    return None


def sanitize_upload_filename(file_name: str | None, *, sniffed_mime_type: str) -> str:
    candidate = (file_name or "pv-document").replace("\\", "/").split("/")[-1].strip()
    if not candidate:
        candidate = "pv-document"

    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", candidate).strip("._")
    if not safe_name:
        safe_name = "pv-document"

    extension = SAFE_UPLOAD_EXTENSION_BY_MIME.get(sniffed_mime_type)
    base_name = safe_name.rsplit(".", 1)[0] if "." in safe_name else safe_name
    base_name = (base_name or "pv-document")[:120]
    if not extension:
        extension = mimetypes.guess_extension(sniffed_mime_type) or ""
    return f"{base_name}{extension}" if extension else base_name


def normalize_update_payload(payload: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    def string_value(key: str, alternate: str | None = None) -> str | None:
        value = payload.get(key)
        if value is None and alternate:
            value = payload.get(alternate)
        if value is None:
            return existing.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return str(value)

    victimes = payload.get("victimes", existing.get("victimes", []))
    if not isinstance(victimes, list):
        victimes = existing.get("victimes", [])

    vehicules = payload.get("vehicules", existing.get("vehicules", []))
    if not isinstance(vehicules, list):
        vehicules = existing.get("vehicules", [])

    nombre_victimes = payload.get("nombre_victimes", payload.get("nombreVictimes"))
    if not isinstance(nombre_victimes, int):
        nombre_victimes = len(victimes)

    return {
        "document_name": string_value("document_name", "documentName") or existing["document_name"],
        "document_url": string_value("document_url", "documentUrl"),
        "numero_police": string_value("numero_police", "numeroPolice"),
        "date_survenance": string_value("date_survenance", "dateSurvenance"),
        "ville": string_value("ville"),
        "ville_ar": string_value("ville_ar", "villeAr"),
        "adresse": string_value("adresse"),
        "adresse_ar": string_value("adresse_ar", "adresseAr"),
        "victimes": victimes,
        "nombre_victimes": nombre_victimes,
        "vehicules": vehicules,
        "texte_brut": string_value("texte_brut", "texteBrut"),
        "texte_brut_ar": string_value("texte_brut_ar", "texteBrutAr"),
        "statut": string_value("statut") or existing.get("statut", "en_cours"),
    }
