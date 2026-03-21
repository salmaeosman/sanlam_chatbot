from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Iterable
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class ChatSessionRecord:
    session_id: str
    user_id: int
    username: str
    user_label: str
    roles: list[str]
    title: str
    page_id: str | None
    current_path: str | None
    last_response_id: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class ChatMessageRecord:
    id: str
    session_id: str
    role: str
    content: str
    created_at: datetime


class ChatSessionStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._lock = Lock()
        self._connection = sqlite3.connect(database_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    user_label TEXT NOT NULL,
                    roles_json TEXT NOT NULL,
                    title TEXT NOT NULL,
                    page_id TEXT NULL,
                    current_path TEXT NULL,
                    last_response_id TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id)
                )
                """,
            )

    def create_session(
        self,
        *,
        user_id: int,
        username: str,
        user_label: str,
        roles: Iterable[str],
        title: str,
        page_id: str | None,
        current_path: str | None,
    ) -> ChatSessionRecord:
        now = utcnow()
        session = ChatSessionRecord(
            session_id=str(uuid4()),
            user_id=user_id,
            username=username,
            user_label=user_label,
            roles=list(roles),
            title=title,
            page_id=page_id,
            current_path=current_path,
            last_response_id=None,
            created_at=now,
            updated_at=now,
        )

        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO chat_sessions (
                    session_id,
                    user_id,
                    username,
                    user_label,
                    roles_json,
                    title,
                    page_id,
                    current_path,
                    last_response_id,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.user_id,
                    session.username,
                    session.user_label,
                    json.dumps(session.roles),
                    session.title,
                    session.page_id,
                    session.current_path,
                    session.last_response_id,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )

        return session

    def get_session(self, session_id: str) -> ChatSessionRecord | None:
        row = self._connection.execute(
            "SELECT * FROM chat_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return self._map_session(row) if row else None

    def list_messages(self, session_id: str) -> list[ChatMessageRecord]:
        rows = self._connection.execute(
            """
            SELECT * FROM chat_messages
            WHERE session_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (session_id,),
        ).fetchall()
        return [self._map_message(row) for row in rows]

    def add_message(self, session_id: str, role: str, content: str) -> ChatMessageRecord:
        message = ChatMessageRecord(
            id=str(uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            created_at=utcnow(),
        )

        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO chat_messages (id, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.session_id,
                    message.role,
                    message.content,
                    message.created_at.isoformat(),
                ),
            )
            self._connection.execute(
                """
                UPDATE chat_sessions
                SET updated_at = ?
                WHERE session_id = ?
                """,
                (utcnow().isoformat(), session_id),
            )

        return message

    def update_session_context(
        self,
        session_id: str,
        *,
        user_label: str,
        roles: Iterable[str],
        page_id: str | None,
        current_path: str | None,
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE chat_sessions
                SET user_label = ?,
                    roles_json = ?,
                    page_id = ?,
                    current_path = ?,
                    updated_at = ?
                WHERE session_id = ?
                """,
                (
                    user_label,
                    json.dumps(list(roles)),
                    page_id,
                    current_path,
                    utcnow().isoformat(),
                    session_id,
                ),
            )

    def set_last_response_id(self, session_id: str, response_id: str | None) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE chat_sessions
                SET last_response_id = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (response_id, utcnow().isoformat(), session_id),
            )

    def _map_session(self, row: sqlite3.Row) -> ChatSessionRecord:
        return ChatSessionRecord(
            session_id=row["session_id"],
            user_id=row["user_id"],
            username=row["username"],
            user_label=row["user_label"],
            roles=json.loads(row["roles_json"]),
            title=row["title"],
            page_id=row["page_id"],
            current_path=row["current_path"],
            last_response_id=row["last_response_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _map_message(self, row: sqlite3.Row) -> ChatMessageRecord:
        return ChatMessageRecord(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
