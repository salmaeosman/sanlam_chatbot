from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="bawaba-de-sanlam-ai-chatbot", alias="APP_NAME")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8001, alias="APP_PORT")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com",
        alias="GEMINI_BASE_URL",
    )
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    gemini_timeout_seconds: float = Field(default=60.0, alias="GEMINI_TIMEOUT_SECONDS")
    gemini_max_output_tokens: int = Field(default=700, alias="GEMINI_MAX_OUTPUT_TOKENS")

    user_mgmt_api_url: str = Field(default="http://localhost:3000", alias="USER_MGMT_API_URL")
    user_mgmt_timeout_seconds: float = Field(default=20.0, alias="USER_MGMT_TIMEOUT_SECONDS")

    frontend_origins_raw: str = Field(
        default="http://localhost:5173",
        alias="FRONTEND_ORIGINS",
    )

    chatbot_db_path: Path = Field(
        default=Path("data") / "chatbot.sqlite3",
        alias="CHATBOT_DB_PATH",
    )
    recent_reclamations_limit: int = Field(default=5, alias="RECENT_RECLAMATIONS_LIMIT")
    recent_notifications_limit: int = Field(default=5, alias="RECENT_NOTIFICATIONS_LIMIT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def frontend_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.frontend_origins_raw.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.chatbot_db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
