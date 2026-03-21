from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ChatRole = Literal["assistant", "user"]


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    page_id: str | None = Field(default=None, alias="pageId")
    current_path: str | None = Field(default=None, alias="currentPath")


class SendMessageRequest(CreateSessionRequest):
    message: str = Field(min_length=1, max_length=4000)


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    role: ChatRole
    content: str
    created_at: datetime = Field(alias="createdAt")


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId")
    title: str
    page_id: str | None = Field(default=None, alias="pageId")
    current_path: str | None = Field(default=None, alias="currentPath")
    suggestions: list[str]
    messages: list[ChatMessageResponse]


class HealthResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    llm_provider: str = Field(alias="llmProvider")
    llm_model: str = Field(alias="llmModel")
    llm_base_url: str = Field(alias="llmBaseUrl")
    llm_reachable: bool = Field(alias="llmReachable")
    llm_model_available: bool = Field(alias="llmModelAvailable")
    user_mgmt_api_url: str = Field(alias="userMgmtApiUrl")
