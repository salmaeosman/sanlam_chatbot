from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import Settings
from app.prompts import build_manager_summary


CLAIM_ROLES = {"AVOCAT", "MEDECIN", "GESTIONNAIRE_JUDICIAIRE"}


class AuthenticationError(Exception):
    pass


class UserMgmtClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(
            base_url=settings.user_mgmt_api_url.rstrip("/"),
            timeout=settings.user_mgmt_timeout_seconds,
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    async def get_live_context(
        self,
        *,
        token: str,
        page_id: str | None,
        current_path: str | None,
    ) -> dict[str, Any]:
        user = await self._get_required_json("/auth/me", token=token)
        roles = {role.upper() for role in user.get("roles", [])}
        normalized_path = (current_path or "").lower()
        context: dict[str, Any] = {
            "user": user,
            "page_id": page_id,
            "current_path": current_path,
        }

        tasks: list[asyncio.Future] = []
        task_keys: list[str] = []

        if roles & CLAIM_ROLES:
            tasks.extend(
                [
                    asyncio.ensure_future(self._get_optional_json("/reclamations/stats", token=token)),
                    asyncio.ensure_future(self._get_optional_json("/notifications", token=token)),
                    asyncio.ensure_future(self._get_optional_json("/reclamations", token=token)),
                ],
            )
            task_keys.extend(["reclamation_stats", "notifications", "reclamations"])

        if "MANAGER" in roles:
            tasks.extend(
                [
                    asyncio.ensure_future(self._get_optional_json("/users", token=token)),
                    asyncio.ensure_future(self._get_optional_json("/roles", token=token)),
                ],
            )
            task_keys.extend(["users", "roles"])

        if "/pv-ia" in normalized_path:
            tasks.extend(
                [
                    asyncio.ensure_future(self._get_optional_json("/pv-extractions/stats", token=token)),
                    asyncio.ensure_future(self._get_optional_json("/pv-extractions", token=token)),
                ],
            )
            task_keys.extend(["pv_extraction_stats", "pv_extractions"])

        if tasks:
            results = await asyncio.gather(*tasks)
            payloads = dict(zip(task_keys, results, strict=False))

            if payloads.get("reclamation_stats") is not None:
                raw_rows = payloads.get("reclamations") or []
                context["reclamations"] = {
                    "stats": payloads["reclamation_stats"],
                    "recent": [
                        {
                            "id": row.get("id"),
                            "status": row.get("status"),
                            "claimNumber": row.get("claimNumber"),
                            "policyNumber": row.get("policyNumber"),
                            "category": row.get("category"),
                            "lastActivityAt": row.get("lastActivityAt"),
                            "createdAt": row.get("createdAt"),
                        }
                        for row in raw_rows[: self.settings.recent_reclamations_limit]
                    ],
                }

            if payloads.get("notifications") is not None:
                raw_notifications = payloads["notifications"]
                context["notifications"] = {
                    "unreadCount": raw_notifications.get("unreadCount", 0),
                    "latest": [
                        {
                            "id": item.get("id"),
                            "type": item.get("type"),
                            "title": item.get("title"),
                            "createdAt": item.get("createdAt"),
                        }
                        for item in (raw_notifications.get("items") or [])[
                            : self.settings.recent_notifications_limit
                        ]
                    ],
                }

            if payloads.get("users") is not None and payloads.get("roles") is not None:
                context["manager"] = build_manager_summary(
                    users=payloads["users"],
                    roles=payloads["roles"],
                )

            if payloads.get("pv_extraction_stats") is not None:
                raw_rows = payloads.get("pv_extractions") or []
                if isinstance(raw_rows, dict):
                    raw_rows = raw_rows.get("items") or []

                context["pv_extractions"] = {
                    "stats": payloads["pv_extraction_stats"],
                    "recent": [
                        {
                            "id": row.get("id"),
                            "statut": row.get("statut"),
                            "documentName": row.get("documentName") or row.get("document_name"),
                            "numeroPolice": row.get("numeroPolice") or row.get("numero_police"),
                            "ville": row.get("ville"),
                            "nombreVictimes": row.get("nombreVictimes")
                            or row.get("nombre_victimes")
                            or 0,
                            "updatedAt": row.get("updatedAt") or row.get("updated_at"),
                        }
                        for row in raw_rows[: self.settings.recent_reclamations_limit]
                        if isinstance(row, dict)
                    ],
                }

        return context

    async def ingest_pv_extraction(
        self,
        *,
        token: str,
        file_name: str,
        mime_type: str,
        file_bytes: bytes,
    ) -> dict[str, Any]:
        response = await self.client.post(
            "/pv-extractions/ingest",
            headers=self._headers(token),
            files={
                "file": (
                    file_name,
                    file_bytes,
                    mime_type or "application/octet-stream",
                ),
            },
            timeout=self.settings.user_mgmt_pv_upload_timeout_seconds,
        )
        return self._require_json_response(response)

    async def list_pv_extractions(
        self,
        *,
        token: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        response = await self.client.get(
            "/pv-extractions",
            headers=self._headers(token),
            params=params,
        )
        return self._require_json_response(response)

    async def get_pv_extraction_stats(
        self,
        *,
        token: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = await self.client.get(
            "/pv-extractions/stats",
            headers=self._headers(token),
            params=params,
        )
        return self._require_json_response(response)

    async def get_pv_extraction(
        self,
        *,
        token: str,
        record_id: str,
    ) -> dict[str, Any]:
        response = await self.client.get(
            f"/pv-extractions/{record_id}",
            headers=self._headers(token),
        )
        return self._require_json_response(response)

    async def update_pv_extraction(
        self,
        *,
        token: str,
        record_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self.client.patch(
            f"/pv-extractions/{record_id}",
            headers=self._headers(token),
            json=payload,
        )
        return self._require_json_response(response)

    async def delete_pv_extraction(
        self,
        *,
        token: str,
        record_id: str,
    ) -> dict[str, Any]:
        response = await self.client.delete(
            f"/pv-extractions/{record_id}",
            headers=self._headers(token),
        )
        return self._require_json_response(response)

    async def download_pv_source_document(
        self,
        *,
        token: str,
        record_id: str,
    ) -> httpx.Response:
        response = await self.client.get(
            f"/pv-extractions/{record_id}/source-document",
            headers=self._headers(token),
        )
        self._raise_for_status(response)
        return response

    async def _get_required_json(self, path: str, *, token: str) -> Any:
        response = await self.client.get(path, headers=self._headers(token))
        self._raise_for_status(response)
        return response.json()

    async def _get_optional_json(self, path: str, *, token: str) -> Any | None:
        response = await self.client.get(path, headers=self._headers(token))
        if response.status_code in {401, 403, 404}:
            return None
        response.raise_for_status()
        return response.json()

    def _require_json_response(self, response: httpx.Response) -> Any:
        self._raise_for_status(response)
        return response.json()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 401:
            raise AuthenticationError("Invalid or expired token")
        response.raise_for_status()

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}
