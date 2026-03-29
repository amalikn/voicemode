"""SQLite-backed runtime session and event storage."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any


class SessionStore:
    """Persistent runtime state for diagnostics and read-aloud resume."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    started_at REAL NOT NULL,
                    ended_at REAL,
                    mode TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    state TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS read_progress (
                    document_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_path TEXT,
                    cursor INTEGER NOT NULL,
                    updated_at REAL NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}'
                );
                """
            )

    def create_session(self, mode: str, metadata: dict[str, Any] | None = None) -> str:
        session_id = f"rt_{uuid.uuid4().hex[:12]}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, started_at, mode, metadata_json)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, time.time(), mode, json.dumps(metadata or {})),
            )
        return session_id

    def close_session(self, session_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE session_id = ?",
                (time.time(), session_id),
            )

    def record_event(
        self,
        session_id: str,
        event_type: str,
        state: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO events (session_id, created_at, event_type, state, details_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, time.time(), event_type, state, json.dumps(details or {})),
            )

    def recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id, created_at, event_type, state, details_json
                FROM events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "session_id": row["session_id"],
                "created_at": row["created_at"],
                "event_type": row["event_type"],
                "state": row["state"],
                "details": json.loads(row["details_json"]),
            }
            for row in rows
        ]

    def diagnostics_summary(self, recent_limit: int = 20) -> dict[str, Any]:
        with self._connect() as conn:
            session_counts = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_sessions,
                    SUM(CASE WHEN ended_at IS NULL THEN 1 ELSE 0 END) AS open_sessions
                FROM sessions
                """
            ).fetchone()
            event_count_row = conn.execute("SELECT COUNT(*) AS total_events FROM events").fetchone()
            failure_counts = conn.execute(
                """
                SELECT event_type, COUNT(*) AS count
                FROM events
                WHERE event_type IN ('FAIL', 'TIMEOUT')
                GROUP BY event_type
                """
            ).fetchall()
            latest_progress = conn.execute(
                """
                SELECT document_id, title, source_path, cursor, updated_at, details_json
                FROM read_progress
                ORDER BY updated_at DESC
                LIMIT 5
                """
            ).fetchall()
        failures = {row["event_type"]: row["count"] for row in failure_counts}
        documents = [
            {
                "document_id": row["document_id"],
                "title": row["title"],
                "source_path": row["source_path"],
                "cursor": row["cursor"],
                "updated_at": row["updated_at"],
                "details": json.loads(row["details_json"]),
            }
            for row in latest_progress
        ]
        return {
            "total_sessions": int(session_counts["total_sessions"] or 0),
            "open_sessions": int(session_counts["open_sessions"] or 0),
            "total_events": int(event_count_row["total_events"] or 0),
            "failure_counts": {
                "FAIL": int(failures.get("FAIL", 0)),
                "TIMEOUT": int(failures.get("TIMEOUT", 0)),
            },
            "recent_read_documents": documents,
            "recent_event_limit": recent_limit,
        }

    def save_read_progress(
        self,
        document_id: str,
        title: str,
        source_path: str | None,
        cursor: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO read_progress (document_id, title, source_path, cursor, updated_at, details_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    title = excluded.title,
                    source_path = excluded.source_path,
                    cursor = excluded.cursor,
                    updated_at = excluded.updated_at,
                    details_json = excluded.details_json
                """,
                (
                    document_id,
                    title,
                    source_path,
                    cursor,
                    time.time(),
                    json.dumps(details or {}),
                ),
            )

    def load_read_progress(self, document_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT document_id, title, source_path, cursor, updated_at, details_json
                FROM read_progress
                WHERE document_id = ?
                """,
                (document_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "document_id": row["document_id"],
            "title": row["title"],
            "source_path": row["source_path"],
            "cursor": row["cursor"],
            "updated_at": row["updated_at"],
            "details": json.loads(row["details_json"]),
        }
