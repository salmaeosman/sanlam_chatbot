from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.gemini_service import GeminiChatService, GeminiServiceError
from app.legal_reference_service import LegalReferenceService
from app.pv_service import PvService
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


@dataclass(slots=True)
class ServiceContainer:
    settings: Settings
    store: ChatSessionStore
    user_mgmt: UserMgmtClient
    gemini: GeminiChatService
    legal_reference: LegalReferenceService
    pv: PvService


def create_app(settings: Settings | None = None) -> FastAPI:
    effective_settings = settings or get_settings()
    effective_settings.chatbot_db_path.parent.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        user_mgmt = UserMgmtClient(effective_settings)
        gemini = GeminiChatService(effective_settings)
        services = ServiceContainer(
            settings=effective_settings,
            store=ChatSessionStore(effective_settings.chatbot_db_path),
            user_mgmt=user_mgmt,
            gemini=gemini,
            legal_reference=LegalReferenceService(effective_settings),
            pv=PvService(effective_settings, user_mgmt, gemini),
        )
        app.state.services = services
        try:
            yield
        finally:
            await services.user_mgmt.aclose()
            await services.gemini.aclose()

    app = FastAPI(title=effective_settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=effective_settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        if effective_settings.security_headers_enabled:
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
            userMgmtConfigured=bool(effective_settings.user_mgmt_api_url.strip()),
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
        user_message = payload.message.strip()
        services.store.add_message(session_id, "user", user_message)
        legal_reference_snippets = services.legal_reference.search(user_message)
        if legal_reference_snippets:
            context["legal_reference_snippets"] = legal_reference_snippets
        elif services.legal_reference.looks_like_reference_question(user_message):
            context["legal_reference_question"] = True
        conversation_messages = build_model_messages(services.store.list_messages(session_id))

        try:
            answer = await services.gemini.generate_reply(
                system_prompt=build_system_prompt(context, latest_user_message=user_message),
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

    @app.post("/pv-extractions/ingest", status_code=status.HTTP_201_CREATED)
    @app.post(
        "/api/v1/pv-extractions/ingest",
        include_in_schema=False,
        status_code=status.HTTP_201_CREATED,
    )
    async def ingest_pv_extraction(
        request: Request,
        file: UploadFile = File(...),
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> dict[str, Any]:
        validate_upload_content_length(request, services.settings)
        try:
            return await services.pv.ingest_record(token=token, file=file)
        except GeminiServiceError as error:
            raise HTTPException(
                status_code=getattr(error, "status_code", status.HTTP_503_SERVICE_UNAVAILABLE),
                detail=str(error),
            ) from error

    @app.get("/pv-extractions")
    @app.get("/api/v1/pv-extractions", include_in_schema=False)
    async def list_pv_extractions(
        request: Request,
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> Any:
        return await services.pv.list_records(
            token=token,
            query_params=request.query_params,
        )

    @app.get("/pv-extractions/stats")
    @app.get("/api/v1/pv-extractions/stats", include_in_schema=False)
    async def get_pv_extraction_stats(
        request: Request,
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> Any:
        return await services.pv.get_stats(
            token=token,
            query_params=request.query_params,
        )

    @app.get("/pv-extractions/{record_id}")
    @app.get("/api/v1/pv-extractions/{record_id}", include_in_schema=False)
    async def get_pv_extraction(
        record_id: str,
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> Any:
        return await services.pv.get_record(token=token, record_id=record_id)

    @app.patch("/pv-extractions/{record_id}")
    @app.patch("/api/v1/pv-extractions/{record_id}", include_in_schema=False)
    async def update_pv_extraction(
        record_id: str,
        payload: dict[str, Any],
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> Any:
        return await services.pv.update_record(
            token=token,
            record_id=record_id,
            payload=payload,
        )

    @app.delete("/pv-extractions/{record_id}")
    @app.delete("/api/v1/pv-extractions/{record_id}", include_in_schema=False)
    async def delete_pv_extraction(
        record_id: str,
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> Any:
        return await services.pv.delete_record(token=token, record_id=record_id)

    @app.get("/pv-extractions/{record_id}/source-document")
    @app.get("/api/v1/pv-extractions/{record_id}/source-document", include_in_schema=False)
    async def download_pv_source_document(
        record_id: str,
        token: str = Depends(get_bearer_token),
        services: ServiceContainer = Depends(get_services),
    ) -> Response:
        document = await services.pv.download_source_document(
            token=token,
            record_id=record_id,
        )
        response = Response(
            content=document.body,
            media_type=document.content_type,
        )
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if document.content_disposition:
            response.headers["Content-Disposition"] = document.content_disposition
        return response

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
        cookie_name=get_services(request).settings.auth_cookie_name,
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
            detail=(
                f"Le fichier depasse la limite autorisee de "
                f"{settings.pv_upload_max_bytes // (1024 * 1024)} Mo"
            ),
        )


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
