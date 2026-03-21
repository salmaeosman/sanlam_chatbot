from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


class GeminiServiceError(RuntimeError):
    pass


class GeminiChatService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(
            base_url=settings.gemini_base_url.rstrip("/"),
            timeout=settings.gemini_timeout_seconds,
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.gemini_api_key.strip())

    async def get_status(self) -> dict[str, Any]:
        status = {
            "provider": "gemini",
            "model": self.settings.gemini_model,
            "baseUrl": self.settings.gemini_base_url,
            "reachable": False,
            "modelAvailable": False,
        }

        if not self.is_configured:
            return status

        try:
            response = await self.client.get(
                "/v1beta/models",
                headers=self._headers(),
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return status

        data = response.json()
        models = data.get("models", [])
        available_names = {
            (row.get("name") or "").split("/", 1)[-1]
            for row in models
            if row.get("name")
        }

        status["reachable"] = True
        status["modelAvailable"] = self.settings.gemini_model in available_names
        return status

    async def generate_reply(
        self,
        *,
        system_prompt: str,
        conversation_messages: list[dict[str, str]],
    ) -> str:
        if not self.is_configured:
            raise GeminiServiceError("GEMINI_API_KEY is missing.")

        payload = {
            "system_instruction": {
                "parts": [
                    {
                        "text": system_prompt,
                    },
                ],
            },
            "contents": [
                {
                    "role": message["role"],
                    "parts": [
                        {
                            "text": message["content"],
                        },
                    ],
                }
                for message in conversation_messages
            ],
            "generationConfig": {
                "maxOutputTokens": self.settings.gemini_max_output_tokens,
            },
        }

        try:
            response = await self.client.post(
                f"/v1beta/models/{self.settings.gemini_model}:generateContent",
                headers=self._headers(),
                json=payload,
            )
        except httpx.ConnectError as error:
            raise GeminiServiceError(
                f"Gemini n'est pas joignable sur {self.settings.gemini_base_url}.",
            ) from error
        except httpx.HTTPError as error:
            raise GeminiServiceError(f"Requete Gemini echouee: {error}") from error

        if response.is_error:
            raise GeminiServiceError(self._extract_error(response))

        data = response.json()
        text = self._extract_text(data)
        if not text:
            raise GeminiServiceError("Gemini n'a pas renvoye de contenu exploitable.")

        return text

    def _headers(self) -> dict[str, str]:
        return {
            "x-goog-api-key": self.settings.gemini_api_key,
            "Content-Type": "application/json",
        }

    def _extract_error(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text.strip() or f"Gemini HTTP {response.status_code}"

        error_payload = payload.get("error") or {}
        message = error_payload.get("message") or response.text.strip()
        if response.status_code == 429:
            return f"Gemini rate limit reached: {message}"
        if response.status_code in {401, 403}:
            return f"Gemini authentication failed: {message}"
        if response.status_code == 404:
            return (
                f"Le modele Gemini '{self.settings.gemini_model}' est introuvable "
                f"ou indisponible pour votre cle API: {message}"
            )
        return f"Gemini request failed: {message}"

    def _extract_text(self, payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates") or []
        chunks: list[str] = []
        for candidate in candidates:
            content = candidate.get("content") or {}
            for part in content.get("parts") or []:
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())

        return "\n".join(chunks).strip()
