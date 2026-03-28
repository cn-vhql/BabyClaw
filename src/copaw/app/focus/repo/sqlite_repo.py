# -*- coding: utf-8 -*-
"""SQLite repository for focus tags and notes."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..models import FocusNote


class SQLiteFocusRepository:
    """Persist focus tags and notes in a workspace-scoped SQLite database."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.executescript(
                    """
                    PRAGMA journal_mode=WAL;

                    CREATE TABLE IF NOT EXISTS focus_tags (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        normalized_name TEXT NOT NULL UNIQUE,
                        position INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS focus_notes (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        source TEXT NOT NULL,
                        tags_json TEXT NOT NULL DEFAULT '[]',
                        created_at TEXT NOT NULL,
                        session_id TEXT,
                        run_id TEXT
                    );

                    CREATE INDEX IF NOT EXISTS idx_focus_notes_created_at
                    ON focus_notes(created_at DESC);

                    CREATE INDEX IF NOT EXISTS idx_focus_notes_run_id
                    ON focus_notes(run_id);
                    """
                )
                conn.commit()

    @staticmethod
    def _normalize_tag(tag: str) -> str:
        return " ".join((tag or "").strip().split()).lower()

    @staticmethod
    def _clean_tag(tag: str) -> str:
        return " ".join((tag or "").strip().split())

    def list_tags(self) -> list[str]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT name FROM focus_tags
                    ORDER BY position ASC, created_at ASC
                    """
                ).fetchall()
        return [str(row["name"]) for row in rows]

    def replace_tags(self, tags: list[str]) -> list[str]:
        cleaned = []
        seen = set()
        for raw_tag in tags:
            tag = self._clean_tag(raw_tag)
            normalized = self._normalize_tag(tag)
            if not tag or normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append((tag, normalized))

        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM focus_tags")
                for position, (name, normalized_name) in enumerate(cleaned):
                    conn.execute(
                        """
                        INSERT INTO focus_tags (
                            name, normalized_name, position, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (name, normalized_name, position, now, now),
                    )
                conn.commit()
        return [name for name, _ in cleaned]

    def add_tag(self, tag: str) -> bool:
        name = self._clean_tag(tag)
        normalized_name = self._normalize_tag(name)
        if not name:
            return False

        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._connect() as conn:
                existing = conn.execute(
                    "SELECT id FROM focus_tags WHERE normalized_name = ?",
                    (normalized_name,),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        UPDATE focus_tags
                        SET name = ?, updated_at = ?
                        WHERE normalized_name = ?
                        """,
                        (name, now, normalized_name),
                    )
                    conn.commit()
                    return False

                row = conn.execute(
                    "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM focus_tags"
                ).fetchone()
                next_pos = int(row["next_pos"]) if row else 0
                conn.execute(
                    """
                    INSERT INTO focus_tags (
                        name, normalized_name, position, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (name, normalized_name, next_pos, now, now),
                )
                conn.commit()
        return True

    def remove_tag(self, tag: str) -> bool:
        normalized_name = self._normalize_tag(tag)
        if not normalized_name:
            return False

        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM focus_tags WHERE normalized_name = ?",
                    (normalized_name,),
                )
                conn.commit()
                deleted = cursor.rowcount > 0
        return deleted

    def write_note(
        self,
        *,
        title: str,
        content: str,
        tags: list[str] | None = None,
        source: str = "manual",
        session_id: str | None = None,
        run_id: str | None = None,
    ) -> FocusNote:
        clean_title = " ".join((title or "").strip().split())
        clean_content = (content or "").strip()
        if not clean_title:
            raise ValueError("title is required")
        if not clean_content:
            raise ValueError("content is required")

        clean_tags = []
        seen = set()
        for raw_tag in tags or []:
            tag = self._clean_tag(raw_tag)
            normalized = self._normalize_tag(tag)
            if not tag or normalized in seen:
                continue
            seen.add(normalized)
            clean_tags.append(tag)

        for tag in clean_tags:
            self.add_tag(tag)

        note = FocusNote(
            id=str(uuid.uuid4()),
            title=clean_title,
            content=clean_content,
            tags=clean_tags,
            source=(source or "manual").strip() or "manual",
            createdAt=datetime.now(timezone.utc),
            sessionId=session_id,
            runId=run_id,
        )

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO focus_notes (
                        id, title, content, source, tags_json,
                        created_at, session_id, run_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        note.id,
                        note.title,
                        note.content,
                        note.source,
                        json.dumps(note.tags, ensure_ascii=False),
                        note.created_at.isoformat(),
                        note.session_id,
                        note.run_id,
                    ),
                )
                conn.commit()
        return note

    def list_notes(self, *, limit: int = 200) -> list[FocusNote]:
        max_limit = max(1, min(limit, 500))
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, title, content, source, tags_json,
                           created_at, session_id, run_id
                    FROM focus_notes
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (max_limit,),
                ).fetchall()
        return [self._row_to_note(row) for row in rows]

    def list_notes_by_run(self, run_id: str) -> list[FocusNote]:
        if not run_id:
            return []
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, title, content, source, tags_json,
                           created_at, session_id, run_id
                    FROM focus_notes
                    WHERE run_id = ?
                    ORDER BY created_at ASC
                    """,
                    (run_id,),
                ).fetchall()
        return [self._row_to_note(row) for row in rows]

    @staticmethod
    def _row_to_note(row: sqlite3.Row) -> FocusNote:
        return FocusNote(
            id=str(row["id"]),
            title=str(row["title"]),
            content=str(row["content"]),
            tags=json.loads(row["tags_json"] or "[]"),
            source=str(row["source"]),
            createdAt=datetime.fromisoformat(str(row["created_at"])),
            sessionId=row["session_id"],
            runId=row["run_id"],
        )
