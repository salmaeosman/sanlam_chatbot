from __future__ import annotations

import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.gemini_service import GeminiChatService, GeminiServiceError
from app.prompts import (
    build_session_title,
    build_suggestions,
    build_system_prompt,
    build_welcome_message,
)
from app.schemas import (
    ChatMessageResponse,
    ChatSessionResponse,
    CreateSessionRequest,
    HealthResponse,
    SendMessageRequest,
)
from app.session_store import ChatSessionStore
from app.user_mgmt_client import AuthenticationError, UserMgmtClient


UPLOAD_MULTIPART_OVERHEAD_BYTES = 1024 * 1024
SAFE_UPLOAD_EXTENSION_BY_MIME = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@dataclass(slots=True)
class ServiceContainer:
    settings: Settings
    store: ChatSessionStore
    user_mgmt: UserMgmtClient
    gemini: GeminiChatService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    services = ServiceContainer(
        settings=settings,
        store=ChatSessionStore(settings.chatbot_db_path),
        user_mgmt=UserMgmtClient(settings),
        gemini=GeminiChatService(settings),
    )
    app.state.services = services
    try:
        yield
    finally:
        await services.user_mgmt.aclose()
        await services.gemini.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        if settings.security_headers_enabled:
            response.headers.setdefault("Cache-Control", "no-store")
            response.headers.setdefault("Pragma", "no-cache")
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault(
                "Permissions-Policy",
                "camera=(), microphone=(), geolocation=()",
            )
        return response

    @app.get("/health", response_model=HealthResponse)
    async def health(services: ServiceContainer = Depends(get_services)) -> HealthResponse:
        gemini_status = await services.gemini.get_status()
        return HealthResponse(
            status="ok",
            llmProvider=gemini_status["provider"],
            llmModel=gemini_status["model"],
            llmConfigured=services.gemini.is_configured,
            llmReachable=gemini_status["reachable"],
            llmModelAvailable=gemini_status["modelAvailable"],
            userMgmtConfigured=bool(settings.user_mgmt_api_url.strip()),
        )

    @app.post("/api/v1/chat/sessions", response_model=ChatSessionResponse)
    async def create_session(
        payload: CreateSessionRequest,
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> ChatSessionResponse:
        context = await fetch_context(services, token, payload.page_id, payload.current_path)
        user = context["user"]

        session = services.store.create_session(
            user_id=user["id"],
            username=user["username"],
            user_label=format_user_label(user),
            roles=user.get("roles", []),
            title=build_session_title(user),
            page_id=payload.page_id,
            current_path=payload.current_path,
        )
        services.store.add_message(
            session.session_id,
            "assistant",
            build_welcome_message(user, payload.page_id, payload.current_path),
        )
        return build_session_response(services, session.session_id, context)

    @app.get("/api/v1/chat/sessions/{session_id}", response_model=ChatSessionResponse)
    async def get_session(
        session_id: str,
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> ChatSessionResponse:
        session = services.store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        context = await fetch_context(services, token, session.page_id, session.current_path)
        enforce_session_owner(session.user_id, context["user"]["id"])
        return build_session_response(services, session_id, context)

    @app.post("/api/v1/chat/sessions/{session_id}/messages", response_model=ChatSessionResponse)
    async def send_message(
        session_id: str,
        payload: SendMessageRequest,
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> ChatSessionResponse:
        session = services.store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        context = await fetch_context(services, token, payload.page_id, payload.current_path)
        enforce_session_owner(session.user_id, context["user"]["id"])

        services.store.update_session_context(
            session_id,
            user_label=format_user_label(context["user"]),
            roles=context["user"].get("roles", []),
            page_id=payload.page_id,
            current_path=payload.current_path,
        )
        services.store.add_message(session_id, "user", payload.message.strip())
        conversation_messages = build_model_messages(services.store.list_messages(session_id))

        try:
            answer = await services.gemini.generate_reply(
                system_prompt=build_system_prompt(context),
                conversation_messages=conversation_messages,
            )
        except GeminiServiceError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(error),
            ) from error

        services.store.add_message(session_id, "assistant", answer)
        services.store.set_last_response_id(session_id, None)
        return build_session_response(services, session_id, context)

    @app.post("/pv-extractions/ingest")
    async def ingest_pv_extraction(
        request: Request,
        file: UploadFile = File(...),
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> dict[str, Any]:
        validate_upload_content_length(request, services.settings)

        try:
            file_bytes = await file.read()
        finally:
            await file.close()

        file_name, mime_type = validate_pv_upload(
            file_name=file.filename,
            declared_mime_type=file.content_type,
            file_bytes=file_bytes,
            settings=services.settings,
        )

        try:
            return await services.user_mgmt.ingest_pv_extraction(
                token=token,
                file_name=file_name,
                mime_type=mime_type,
                file_bytes=file_bytes,
            )
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(error),
            ) from error
        except httpx.HTTPError as error:
            raise map_upstream_http_error(
                error,
                fallback="Impossible d'extraire le PV pour le moment",
            ) from error

    @app.get("/pv-extractions")
    async def list_pv_extractions(
        request: Request,
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> Any:
        try:
            return await services.user_mgmt.list_pv_extractions(
                token=token,
                params=dict(request.query_params),
            )
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(error),
            ) from error
        except httpx.HTTPError as error:
            raise map_upstream_http_error(
                error,
                fallback="Impossible de recuperer les extractions PV",
            ) from error

    @app.get("/pv-extractions/stats")
    async def get_pv_extraction_stats(
        request: Request,
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> dict[str, Any]:
        try:
            return await services.user_mgmt.get_pv_extraction_stats(
                token=token,
                params=dict(request.query_params),
            )
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(error),
            ) from error
        except httpx.HTTPError as error:
            raise map_upstream_http_error(
                error,
                fallback="Impossible de recuperer les statistiques PV",
            ) from error

    @app.get("/pv-extractions/{record_id}")
    async def get_pv_extraction(
        record_id: str,
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> dict[str, Any]:
        try:
            return await services.user_mgmt.get_pv_extraction(
                token=token,
                record_id=record_id,
            )
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(error),
            ) from error
        except httpx.HTTPError as error:
            raise map_upstream_http_error(
                error,
                fallback="Impossible de recuperer ce proces-verbal",
            ) from error

    @app.patch("/pv-extractions/{record_id}")
    async def update_pv_extraction(
        record_id: str,
        payload: dict[str, Any],
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> dict[str, Any]:
        try:
            return await services.user_mgmt.update_pv_extraction(
                token=token,
                record_id=record_id,
                payload=payload,
            )
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(error),
            ) from error
        except httpx.HTTPError as error:
            raise map_upstream_http_error(
                error,
                fallback="Impossible de mettre a jour ce proces-verbal",
            ) from error

    @app.delete("/pv-extractions/{record_id}")
    async def delete_pv_extraction(
        record_id: str,
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> dict[str, Any]:
        try:
            return await services.user_mgmt.delete_pv_extraction(
                token=token,
                record_id=record_id,
            )
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(error),
            ) from error
        except httpx.HTTPError as error:
            raise map_upstream_http_error(
                error,
                fallback="Impossible de supprimer ce proces-verbal",
            ) from error

    @app.get("/pv-extractions/{record_id}/source-document")
    async def download_pv_source_document(
        record_id: str,
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> Response:
        try:
            upstream_response = await services.user_mgmt.download_pv_source_document(
                token=token,
                record_id=record_id,
            )
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(error),
            ) from error
        except httpx.HTTPError as error:
            raise map_upstream_http_error(
                error,
                fallback="Impossible de telecharger le document source",
            ) from error

        forwarded_headers: dict[str, str] = {}
        disposition = upstream_response.headers.get("content-disposition")
        if disposition:
            forwarded_headers["Content-Disposition"] = disposition
        forwarded_headers["Cache-Control"] = "private, no-store, max-age=0"
        forwarded_headers["Pragma"] = "no-cache"
        forwarded_headers["X-Content-Type-Options"] = "nosniff"

        return Response(
            content=upstream_response.content,
            media_type=upstream_response.headers.get("content-type") or "application/octet-stream",
            headers=forwarded_headers,
        )

    return app


def get_services(request: Request) -> ServiceContainer:
    return request.app.state.services


async def get_bearer_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> str:
    if authorization:
        scheme, _, raw_token = authorization.partition(" ")
        token = raw_token.strip()
        if scheme.lower() == "bearer" and token:
            return token

    cookie_token = extract_token_from_cookie_header(
        cookie_header=request.headers.get("cookie"),
        cookie_name=get_settings().auth_cookie_name,
    )
    if cookie_token:
        return cookie_token

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")


async def fetch_context(
    services: ServiceContainer,
    token: str,
    page_id: str | None,
    current_path: str | None,
) -> dict:
    try:
        return await services.user_mgmt.get_live_context(
            token=token,
            page_id=page_id,
            current_path=current_path,
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


def enforce_session_owner(session_user_id: int, authenticated_user_id: int) -> None:
    if session_user_id != authenticated_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden session")


def map_upstream_http_error(error: httpx.HTTPError, *, fallback: str) -> HTTPException:
    if isinstance(error, httpx.HTTPStatusError):
        upstream_status = error.response.status_code
        if 400 <= upstream_status < 500:
            return HTTPException(
                status_code=upstream_status,
                detail=extract_upstream_error_detail(error, fallback=fallback),
            )
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=fallback,
        )

    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=fallback,
    )


def extract_upstream_error_detail(error: httpx.HTTPError, *, fallback: str) -> str:
    response = getattr(error, "response", None)
    if response is None:
        return fallback

    try:
        payload = response.json()
    except ValueError:
        return normalize_client_error_detail(response.text, fallback=fallback)

    if not isinstance(payload, dict):
        return fallback

    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return normalize_client_error_detail(message, fallback=fallback)
    if isinstance(message, list):
        joined = ", ".join(item for item in message if isinstance(item, str))
        if joined.strip():
            return normalize_client_error_detail(joined, fallback=fallback)
    if isinstance(payload.get("detail"), str) and payload["detail"].strip():
        return normalize_client_error_detail(payload["detail"], fallback=fallback)
    if isinstance(payload.get("error"), str) and payload["error"].strip():
        return normalize_client_error_detail(payload["error"], fallback=fallback)
    return fallback


def normalize_client_error_detail(detail: str, *, fallback: str) -> str:
    cleaned = " ".join(detail.split()).strip()
    if not cleaned:
        return fallback
    return cleaned[:300]


def extract_token_from_cookie_header(cookie_header: str | None, cookie_name: str) -> str | None:
    if not cookie_header or not cookie_name:
        return None

    for raw_pair in cookie_header.split(";"):
        name, separator, value = raw_pair.strip().partition("=")
        if separator and name == cookie_name and value.strip():
            return value.strip()

    return None


def validate_upload_content_length(request: Request, settings: Settings) -> None:
    raw_content_length = request.headers.get("content-length")
    if not raw_content_length:
        return

    try:
        content_length = int(raw_content_length)
    except ValueError:
        return

    max_request_size = settings.pv_upload_max_bytes + UPLOAD_MULTIPART_OVERHEAD_BYTES
    if content_length > max_request_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Le fichier depasse la limite autorisee de {settings.pv_upload_max_bytes // (1024 * 1024)} Mo",
        )


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

    extension = SAFE_UPLOAD_EXTENSION_BY_MIME.get(sniffed_mime_type, "")
    base_name = safe_name.rsplit(".", 1)[0] if "." in safe_name else safe_name
    base_name = (base_name or "pv-document")[:120]
    return f"{base_name}{extension}" if extension else base_name


def build_session_response(
    services: ServiceContainer,
    session_id: str,
    context: dict,
) -> ChatSessionResponse:
    session = services.store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    messages = [
        ChatMessageResponse(
            id=message.id,
            role=message.role,  # type: ignore[arg-type]
            content=message.content,
            createdAt=message.created_at,
        )
        for message in services.store.list_messages(session_id)
    ]

    return ChatSessionResponse(
        sessionId=session.session_id,
        title=session.title,
        pageId=session.page_id,
        currentPath=session.current_path,
        suggestions=build_suggestions(
            context["user"].get("roles", []),
            session.page_id,
            session.current_path,
        ),
        messages=messages,
    )


def format_user_label(user: dict) -> str:
    first = user.get("first_name") or ""
    last = user.get("last_name") or ""
    full_name = f"{first} {last}".strip()
    return full_name or user.get("username") or "Utilisateur"


def build_model_messages(messages: list) -> list[dict[str, str]]:
    normalized_messages = [
        {
            "role": "model" if message.role == "assistant" else "user",
            "content": message.content,
        }
        for message in messages
        if message.role in {"assistant", "user"} and message.content.strip()
    ]

    first_user_index = next(
        (index for index, message in enumerate(normalized_messages) if message["role"] == "user"),
        None,
    )

    if first_user_index is None:
        return []

    return normalized_messages[first_user_index:]
