from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from app.config import Settings
from app.pv_schemas import (
    PV_EXTRACTION_RESPONSE_JSON_SCHEMA,
    normalize_extracted_pv_payload,
)


class GeminiServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


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

        data = await self._generate_content(
            system_prompt=system_prompt,
            conversation_messages=conversation_messages,
            max_output_tokens=self.settings.gemini_max_output_tokens,
        )
        text = self._extract_text(data)
        if not text:
            raise GeminiServiceError("Gemini n'a pas renvoye de contenu exploitable.")

        if self._response_was_truncated(data):
            retried_text = await self._retry_truncated_reply(
                system_prompt=system_prompt,
                conversation_messages=conversation_messages,
            )
            if retried_text:
                return retried_text

        return text

    async def extract_pv_data(
        self,
        *,
        mime_type: str,
        file_bytes: bytes,
    ) -> dict[str, Any]:
        if not self.is_configured:
            raise GeminiServiceError("GEMINI_API_KEY n est pas configure", status_code=500)

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64.b64encode(file_bytes).decode("ascii"),
                            },
                        },
                        {
                            "text": (
                                "Analyse ce proces-verbal d accident et extrais les informations "
                                "en francais ET en arabe. Sois tres precis et extrait toutes les "
                                "informations disponibles. Pour chaque victime, extrais aussi "
                                "le numero de CIN ou le numero de la carte d identite nationale "
                                "quand il apparait dans le document, ainsi que son etat apres "
                                "l accident, sa qualite exacte (pieton, passager, conducteur, etc.), "
                                "sa date de naissance, son numero de telephone et son ITT "
                                "quand ils sont visibles. L ITT doit etre exprimee en jours. "
                                "Extrais aussi le numero du PV, l heure de survenance, le numero "
                                "du permis du conducteur et la classe ou categorie de son permis "
                                "quand ils apparaissent dans le document. Pour chaque vehicule, "
                                "extrais aussi le nom de la compagnie d assurance quand il est "
                                "visible. Cette compagnie d assurance concerne la partie ou le "
                                "vehicule implique, pas la victime. S il y a plusieurs vehicules "
                                "avec plusieurs numeros de "
                                "police, renseigne le numero de police dans chaque objet vehicule, "
                                "pas seulement au niveau global. "
                                "Ne cree jamais deux objets pour la meme victime, meme si elle est "
                                "mentionnee plusieurs fois dans le document. Le champ "
                                "nombre_victimes doit correspondre au nombre de victimes distinctes "
                                "de la liste victimes."
                            ),
                        },
                    ],
                },
            ],
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "Tu es un agent specialise dans l extraction de donnees a partir "
                            "de proces-verbaux d accidents de circulation. Le document peut "
                            "etre en francais, en arabe ou bilingue. Extrais les informations "
                            "exactement telles qu elles apparaissent dans le document. Pour "
                            "chaque champ textuel, fournis la version francaise suffixe _fr et "
                            "la version arabe suffixe _ar. Si le texte n existe que dans une "
                            "langue, traduis-le proprement dans l autre quand le schema le demande. "
                            "Le numero_police doit correspondre au numero de police d assurance "
                            "et non au numero du proces-verbal. S il existe plusieurs vehicules "
                            "avec plusieurs polices, renseigne numero_police dans chaque vehicule. "
                            "Le champ numero_police global ne doit etre renseigne que si un seul "
                            "numero de police est clairement present ou si un seul numero peut etre "
                            "rattache avec certitude. Le champ numero_pv correspond "
                            "au numero du proces-verbal lui-meme, souvent introduit par numero PV, "
                            "N du PV ou عدد المحضر. Extrais heure_survenance au format HH:MM "
                            "ou HH:MM:SS. Extrais aussi numero_permis_conducteur et "
                            "classe_permis_conducteur quand le numero du permis et sa classe ou "
                            "categorie sont visibles pour le conducteur. Pour chaque vehicule, "
                            "renseigne compagnie_assurance avec le nom de la compagnie "
                            "d assurance quand elle apparait dans le PV. La compagnie "
                            "d assurance est rattachee a la partie ou au vehicule, jamais a la "
                            "victime. Si l assureur est "
                            "Saham Assurance ou Sanlam, ce vehicule correspond a la partie "
                            "assuree chez nous; une autre compagnie correspond a la partie "
                            "adverse. Pour chaque victime, "
                            "renseigne le champ cin avec le "
                            "numero de CIN ou le numero de la carte d identite nationale quand "
                            "il est visible pres des mentions CIN, N de la carte d identite "
                            "nationale ou بطاقة التعريف الوطنية. Renseigne aussi etat_apres_accident "
                            "en francais (par ex. Blessee, Decedee, Indemne) et qualite_victime "
                            "en francais (par ex. Pieton, Passager, Conducteur) selon le contenu "
                            "du PV. Renseigne date_naissance au format YYYY-MM-DD et telephone "
                            "avec le numero de telephone de la victime quand ils sont visibles "
                            "dans le document, y compris si la date apparait avec des libelles "
                            "comme date de naissance, nee le, date naissance, تاريخ الازدياد "
                            "ou تاريخ الميلاد. Renseigne aussi itt avec la duree en jours "
                            "uniquement, par exemple 30 pour 30 jours d ITT. Retourne une seule "
                            "entree par victime distincte et assure-toi que nombre_victimes "
                            "corresponde au nombre d objets victimes renvoyes. N invente jamais "
                            "une valeur absente."
                        ),
                    },
                ],
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": PV_EXTRACTION_RESPONSE_JSON_SCHEMA,
                "temperature": 0,
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
                f"Gemini n est pas joignable sur {self.settings.gemini_base_url}.",
                status_code=502,
            ) from error
        except httpx.HTTPError as error:
            raise GeminiServiceError(
                f"Requete Gemini echouee: {error}",
                status_code=502,
            ) from error

        if response.status_code == 429:
            raise GeminiServiceError(
                "Trop de requetes, veuillez reessayer plus tard.",
                status_code=429,
            )

        if response.status_code == 402:
            raise GeminiServiceError(
                "Credits Gemini insuffisants.",
                status_code=402,
            )

        if response.is_error:
            raise GeminiServiceError(
                f"Erreur Gemini lors de l extraction du PV ({response.status_code})",
                status_code=502,
            )

        data = response.json()
        text_payload = self._extract_text(data)
        if not text_payload:
            raise GeminiServiceError(
                "Aucune extraction structuree n a ete retournee par Gemini",
                status_code=502,
            )

        try:
            parsed = json.loads(text_payload)
        except json.JSONDecodeError as error:
            raise GeminiServiceError(
                "La reponse JSON de Gemini est invalide",
                status_code=502,
            ) from error

        if isinstance(parsed, dict):
            normalized_payload = normalize_extracted_pv_payload(parsed)
            if isinstance(normalized_payload, dict):
                return normalized_payload

        raise GeminiServiceError("La reponse de Gemini est invalide", status_code=502)

    async def _retry_truncated_reply(
        self,
        *,
        system_prompt: str,
        conversation_messages: list[dict[str, str]],
    ) -> str | None:
        retry_max_tokens = min(max(self.settings.gemini_max_output_tokens * 2, 1600), 4096)
        if retry_max_tokens <= self.settings.gemini_max_output_tokens:
            return None

        try:
            retried_payload = await self._generate_content(
                system_prompt=system_prompt,
                conversation_messages=conversation_messages,
                max_output_tokens=retry_max_tokens,
            )
        except GeminiServiceError:
            return None

        retried_text = self._extract_text(retried_payload)
        return retried_text or None

    async def _generate_content(
        self,
        *,
        system_prompt: str,
        conversation_messages: list[dict[str, str]],
        max_output_tokens: int,
    ) -> dict[str, Any]:
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
                "maxOutputTokens": max_output_tokens,
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

        return response.json()

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

    def _response_was_truncated(self, payload: dict[str, Any]) -> bool:
        candidates = payload.get("candidates") or []
        for candidate in candidates:
            if str(candidate.get("finishReason") or "").upper() == "MAX_TOKENS":
                return True
        return False
