from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
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

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        gemini_status = await app.state.services.gemini.get_status()
        return HealthResponse(
            status="ok",
            llmProvider=gemini_status["provider"],
            llmModel=gemini_status["model"],
            llmBaseUrl=gemini_status["baseUrl"],
            llmReachable=gemini_status["reachable"],
            llmModelAvailable=gemini_status["modelAvailable"],
            userMgmtApiUrl=settings.user_mgmt_api_url,
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
            build_welcome_message(user, payload.page_id),
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

    return app


def get_services(request: Request) -> ServiceContainer:
    return request.app.state.services


async def get_bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return authorization.split(" ", 1)[1].strip()


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
        suggestions=build_suggestions(context["user"].get("roles", []), session.page_id),
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
