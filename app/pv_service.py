from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

import httpx
from fastapi import HTTPException, UploadFile, status

from app.config import Settings
from app.gemini_service import GeminiChatService, GeminiServiceError
from app.pv_schemas import (
    PV_ALLOWED_MIME_TYPES,
    PV_ALLOWED_ROLES,
    NormalizedPvUpload,
    normalize_extracted_pv_payload,
    normalize_mime_type,
    normalize_role_title,
    sanitize_displayed_file_name,
    sniff_mime_type,
)
from app.user_mgmt_client import AuthenticationError, UserMgmtClient


@dataclass(frozen=True, slots=True)
class PvBinaryPayload:
    body: bytes
    content_type: str
    content_disposition: str | None


class PvService:
    def __init__(
        self,
        settings: Settings,
        user_mgmt: UserMgmtClient,
        gemini: GeminiChatService,
    ) -> None:
        self.settings = settings
        self.user_mgmt = user_mgmt
        self.gemini = gemini

    async def ingest_record(self, *, token: str, file: UploadFile) -> dict[str, Any]:
        user = await self.ensure_authorized_user(token)
        normalized_file = await self.normalize_uploaded_file(file)

        extracted = await self.gemini.extract_pv_data(
            mime_type=normalized_file.mime_type,
            file_bytes=normalized_file.buffer,
        )
        normalized_extracted = normalize_extracted_pv_payload(extracted)
        persisted = await self.persist_extracted_record(
            token=token,
            file=normalized_file,
            extracted=normalized_extracted if isinstance(normalized_extracted, dict) else extracted,
        )

        if isinstance(persisted, dict):
            persisted["extractedBy"] = "back-python"
            persisted["requestedBy"] = user.get("username") if isinstance(user, dict) else None

        return persisted if isinstance(persisted, dict) else {"data": persisted}

    async def list_records(
        self,
        *,
        token: str,
        query_params: Mapping[str, str] | None = None,
    ) -> Any:
        return await self.proxy_json(
            method="GET",
            path="/pv-extractions",
            token=token,
            query_params=query_params,
        )

    async def get_stats(
        self,
        *,
        token: str,
        query_params: Mapping[str, str] | None = None,
    ) -> Any:
        return await self.proxy_json(
            method="GET",
            path="/pv-extractions/stats",
            token=token,
            query_params=query_params,
        )

    async def get_record(self, *, token: str, record_id: str) -> Any:
        return await self.proxy_json(
            method="GET",
            path=f"/pv-extractions/{record_id}",
            token=token,
        )

    async def update_record(self, *, token: str, record_id: str, payload: dict[str, Any]) -> Any:
        return await self.proxy_json(
            method="PATCH",
            path=f"/pv-extractions/{record_id}",
            token=token,
            json_body=payload,
        )

    async def delete_record(self, *, token: str, record_id: str) -> Any:
        return await self.proxy_json(
            method="DELETE",
            path=f"/pv-extractions/{record_id}",
            token=token,
        )

    async def download_source_document(self, *, token: str, record_id: str) -> PvBinaryPayload:
        response = await self._request_upstream(
            method="GET",
            path=f"/pv-extractions/{record_id}/source-document",
            token=token,
        )

        if not response.is_success:
            raise self._to_upstream_http_exception(response)

        return PvBinaryPayload(
            body=response.content,
            content_type=response.headers.get("content-type") or "application/octet-stream",
            content_disposition=response.headers.get("content-disposition"),
        )

    async def ensure_authorized_user(self, token: str) -> dict[str, Any]:
        try:
            user = await self.user_mgmt.get_current_user(token=token)
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(error),
            ) from error
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Les donnees de Bawaba de Sanlam sont temporairement indisponibles",
            ) from error

        roles = [
            normalize_role_title(role)
            for role in (user.get("roles") if isinstance(user, dict) else []) or []
        ]
        if not any(role in PV_ALLOWED_ROLES for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acces refuse a ce module",
            )

        return user if isinstance(user, dict) else {}

    async def normalize_uploaded_file(self, file: UploadFile) -> NormalizedPvUpload:
        try:
            buffer = await file.read()
        finally:
            await file.close()

        original_name = (file.filename or "").strip()
        if not buffer or not original_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le fichier source du PV est obligatoire",
            )

        if len(buffer) > self.settings.pv_upload_max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le fichier depasse la taille maximale autorisee de 15 Mo",
            )

        sniffed_mime_type = sniff_mime_type(buffer)
        normalized_mime_type = normalize_mime_type(file.content_type)

        if not sniffed_mime_type or sniffed_mime_type not in PV_ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format non supporte. Utilisez PDF, JPG, PNG ou WEBP.",
            )

        if (
            normalized_mime_type
            and normalized_mime_type != "application/octet-stream"
            and normalized_mime_type != sniffed_mime_type
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le type MIME du fichier ne correspond pas a son contenu",
            )

        raw_size = getattr(file, "size", None)
        size = int(raw_size) if isinstance(raw_size, int) and raw_size > 0 else len(buffer)

        return NormalizedPvUpload(
            original_name=sanitize_displayed_file_name(original_name),
            mime_type=sniffed_mime_type,
            size=size,
            buffer=buffer,
        )

    async def persist_extracted_record(
        self,
        *,
        token: str,
        file: NormalizedPvUpload,
        extracted: dict[str, Any],
    ) -> Any:
        response = await self._request_upstream(
            method="POST",
            path="/pv-extractions/agent-ingest",
            token=token,
            files={
                "file": (file.original_name, file.buffer, file.mime_type),
                "extractedData": (None, json.dumps(extracted, ensure_ascii=True), "application/json"),
            },
            timeout=self.settings.user_mgmt_pv_upload_timeout_seconds,
        )

        return self._read_upstream_payload(response)

    async def proxy_json(
        self,
        *,
        method: str,
        path: str,
        token: str,
        query_params: Mapping[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        response = await self._request_upstream(
            method=method,
            path=path,
            token=token,
            query_params=query_params,
            json_body=json_body,
        )
        return self._read_upstream_payload(response)

    async def _request_upstream(
        self,
        *,
        method: str,
        path: str,
        token: str,
        query_params: Mapping[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        files: Any | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        try:
            return await self.user_mgmt.client.request(
                method=method,
                url=path,
                headers=self._auth_headers(token),
                params=dict(query_params or {}),
                json=json_body,
                files=files,
                timeout=timeout,
            )
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(error),
            ) from error
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Les donnees de Bawaba de Sanlam sont temporairement indisponibles",
            ) from error

    def _read_upstream_payload(self, response: httpx.Response) -> Any:
        payload = self._parse_response_body(response)
        if not response.is_success:
            raise self._to_upstream_http_exception(response, payload=payload)
        return payload

    def _to_upstream_http_exception(
        self,
        response: httpx.Response,
        *,
        payload: Any | None = None,
    ) -> HTTPException:
        normalized_payload = payload if payload is not None else self._parse_response_body(response)
        return HTTPException(
            status_code=response.status_code,
            detail=self._normalize_upstream_message(normalized_payload, response.status_code),
        )

    def _parse_response_body(self, response: httpx.Response) -> Any:
        if not response.text:
            return {}

        try:
            return response.json()
        except ValueError:
            return {"message": response.text}

    def _normalize_upstream_message(self, payload: Any, status_code: int) -> str:
        if isinstance(payload, dict):
            candidate = payload.get("message", payload.get("detail"))
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
            if isinstance(candidate, list):
                joined = ", ".join(item for item in candidate if isinstance(item, str))
                if joined.strip():
                    return joined.strip()

        if isinstance(payload, str) and payload.strip():
            return payload.strip()

        return "Erreur du service amont" if status_code >= 500 else "Requete refusee par le service amont"

    @staticmethod
    def _auth_headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}
