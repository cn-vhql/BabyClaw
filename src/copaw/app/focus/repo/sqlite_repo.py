# -*- coding: utf-8 -*-
"""SQLite repository for focus tags, notes, and run records."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..models import (
    FocusNote,
    FocusNoteSummary,
    FocusRunArchive,
    FocusRunRecord,
)


class SQLiteFocusRepository:
    """Persist focus tags, notes, runs, and archives in a workspace."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.archives_dir = self.path.parent / "focus_run_archives"
        self.archives_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._running_tasks: dict[str, asyncio.Task] = {}
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
                        preview_text TEXT NOT NULL DEFAULT '',
                        fingerprint TEXT,
                        source TEXT NOT NULL,
                        tags_json TEXT NOT NULL DEFAULT '[]',
                        created_at TEXT NOT NULL,
                        session_id TEXT,
                        run_id TEXT
                    );

                    CREATE TABLE IF NOT EXISTS focus_runs (
                        id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        reason TEXT,
                        trigger_type TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        finished_at TEXT,
                        note_count INTEGER NOT NULL DEFAULT 0,
                        summary TEXT NOT NULL DEFAULT '',
                        notification_status TEXT NOT NULL DEFAULT 'pending',
                        archive_id TEXT,
                        tag_snapshot_json TEXT NOT NULL DEFAULT '[]',
                        session_id TEXT
                    );
                    """
                )
                self._ensure_column(
                    conn,
                    table="focus_notes",
                    column="preview_text",
                    ddl="TEXT NOT NULL DEFAULT ''",
                )
                self._ensure_column(
                    conn,
                    table="focus_notes",
                    column="fingerprint",
                    ddl="TEXT",
                )
                self._backfill_preview_text(conn)
                self._backfill_fingerprint(conn)
                self._ensure_indexes(conn)
                conn.commit()

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        *,
        table: str,
        column: str,
        ddl: str,
    ) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {str(row["name"]) for row in rows}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def _backfill_preview_text(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT id, title, content
            FROM focus_notes
            WHERE preview_text IS NULL OR preview_text = ''
            """
        ).fetchall()
        for row in rows:
            preview = self._build_preview_text(str(row["content"]))
            conn.execute(
                """
                UPDATE focus_notes
                SET preview_text = ?
                WHERE id = ?
                """,
                (preview, str(row["id"])),
            )

    def _backfill_fingerprint(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT id, title, content, source, tags_json
            FROM focus_notes
            WHERE fingerprint IS NULL OR fingerprint = ''
            """
        ).fetchall()
        for row in rows:
            tags = json.loads(row["tags_json"] or "[]")
            fingerprint = self._build_note_fingerprint(
                title=str(row["title"]),
                content=str(row["content"]),
                tags=[str(tag) for tag in tags],
                source=str(row["source"]),
            )
            conn.execute(
                """
                UPDATE focus_notes
                SET fingerprint = ?
                WHERE id = ?
                """,
                (fingerprint, str(row["id"])),
            )

    def _ensure_indexes(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_focus_notes_created_at
            ON focus_notes(created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_focus_notes_run_id
            ON focus_notes(run_id);

            CREATE INDEX IF NOT EXISTS idx_focus_notes_run_fingerprint
            ON focus_notes(run_id, fingerprint);

            CREATE INDEX IF NOT EXISTS idx_focus_runs_started_at
            ON focus_runs(started_at DESC);

            CREATE INDEX IF NOT EXISTS idx_focus_runs_status
            ON focus_runs(status);
            """
        )

    @staticmethod
    def _normalize_tag(tag: str) -> str:
        return " ".join((tag or "").strip().split()).lower()

    @staticmethod
    def _clean_tag(tag: str) -> str:
        return " ".join((tag or "").strip().split())

    @staticmethod
    def _build_preview_text(content: str) -> str:
        text = (content or "").strip()
        text = re.sub(r"```[\s\S]*?```", " ", text)
        text = re.sub(r"`([^`]*)`", r"\1", text)
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^[-*+]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"[*_~|]", " ", text)
        text = re.sub(r"\r?\n+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:400]

    @classmethod
    def _build_note_fingerprint(
        cls,
        *,
        title: str,
        content: str,
        tags: list[str],
        source: str,
    ) -> str:
        normalized = json.dumps(
            {
                "title": cls._clean_tag(title),
                "content": (content or "").strip(),
                "tags": [cls._normalize_tag(tag) for tag in tags],
                "source": (source or "").strip().lower(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

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
                return cursor.rowcount > 0

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

        preview_text = self._build_preview_text(clean_content)
        fingerprint = self._build_note_fingerprint(
            title=clean_title,
            content=clean_content,
            tags=clean_tags,
            source=source,
        )

        with self._lock:
            with self._connect() as conn:
                if run_id:
                    existing = conn.execute(
                        """
                        SELECT id, title, content, preview_text, fingerprint, source, tags_json,
                               created_at, session_id, run_id
                        FROM focus_notes
                        WHERE run_id = ? AND fingerprint = ?
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (run_id, fingerprint),
                    ).fetchone()
                    if existing:
                        return self._row_to_note(existing)

                note = FocusNote(
                    id=str(uuid.uuid4()),
                    title=clean_title,
                    content=clean_content,
                    previewText=preview_text,
                    tags=clean_tags,
                    source=(source or "manual").strip() or "manual",
                    createdAt=datetime.now(timezone.utc),
                    sessionId=session_id,
                    runId=run_id,
                    fingerprint=fingerprint,
                )
                conn.execute(
                    """
                    INSERT INTO focus_notes (
                        id, title, content, preview_text, fingerprint, source, tags_json,
                        created_at, session_id, run_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        note.id,
                        note.title,
                        note.content,
                        note.preview_text,
                        note.fingerprint,
                        note.source,
                        json.dumps(note.tags, ensure_ascii=False),
                        note.created_at.isoformat(),
                        note.session_id,
                        note.run_id,
                    ),
                )
                conn.commit()
        return note

    def list_notes(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        query: str | None = None,
    ) -> tuple[list[FocusNoteSummary], int]:
        safe_page = max(1, page)
        safe_page_size = max(1, min(page_size, 100))
        offset = (safe_page - 1) * safe_page_size
        keyword = (query or "").strip()

        where = ""
        params: list[object] = []
        if keyword:
            where = (
                "WHERE title LIKE ? OR preview_text LIKE ? OR content LIKE ? "
                "OR source LIKE ? OR tags_json LIKE ?"
            )
            like = f"%{keyword}%"
            params.extend([like, like, like, like, like])

        with self._lock:
            with self._connect() as conn:
                total = int(
                    conn.execute(
                        f"SELECT COUNT(*) AS count FROM focus_notes {where}",
                        params,
                    ).fetchone()["count"]
                )
                rows = conn.execute(
                    f"""
                    SELECT id, title, preview_text, source, tags_json, created_at, run_id
                    FROM focus_notes
                    {where}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    [*params, safe_page_size, offset],
                ).fetchall()
        return [self._row_to_note_summary(row) for row in rows], total

    def get_note(self, note_id: str) -> FocusNote | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT id, title, content, preview_text, fingerprint, source, tags_json,
                           created_at, session_id, run_id
                    FROM focus_notes
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (note_id,),
                ).fetchone()
        return self._row_to_note(row) if row else None

    def list_notes_by_run(self, run_id: str) -> list[FocusNote]:
        if not run_id:
            return []
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, title, content, preview_text, fingerprint, source, tags_json,
                           created_at, session_id, run_id
                    FROM focus_notes
                    WHERE run_id = ?
                    ORDER BY created_at ASC
                    """,
                    (run_id,),
                ).fetchall()
        return [self._row_to_note(row) for row in rows]

    def list_recent_note_summaries(self, *, limit: int = 5) -> list[FocusNoteSummary]:
        safe_limit = max(1, min(limit, 20))
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, title, preview_text, source, tags_json, created_at, run_id
                    FROM focus_notes
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                ).fetchall()
        return [self._row_to_note_summary(row) for row in rows]

    def create_running_run(
        self,
        *,
        trigger_type: str,
        tag_snapshot: list[str],
        session_id: str,
    ) -> tuple[FocusRunRecord | None, FocusRunRecord | None]:
        with self._lock:
            with self._connect() as conn:
                existing = conn.execute(
                    """
                    SELECT id, status, reason, trigger_type, started_at, finished_at,
                           note_count, summary, notification_status, archive_id,
                           tag_snapshot_json, session_id
                    FROM focus_runs
                    WHERE status = 'running'
                    ORDER BY started_at DESC
                    LIMIT 1
                    """
                ).fetchone()
                if existing:
                    return None, self._row_to_run(existing)

                run = FocusRunRecord(
                    id=str(uuid.uuid4()),
                    status="running",
                    reason=None,
                    triggerType=trigger_type,
                    startedAt=datetime.now(timezone.utc),
                    finishedAt=None,
                    noteCount=0,
                    summary="",
                    notificationStatus="pending",
                    archiveId=None,
                    tagSnapshot=tag_snapshot,
                    sessionId=session_id,
                )
                conn.execute(
                    """
                    INSERT INTO focus_runs (
                        id, status, reason, trigger_type, started_at, finished_at,
                        note_count, summary, notification_status, archive_id,
                        tag_snapshot_json, session_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run.id,
                        run.status,
                        run.reason,
                        run.trigger_type,
                        run.started_at.isoformat(),
                        None,
                        run.note_count,
                        run.summary,
                        run.notification_status,
                        run.archive_id,
                        json.dumps(run.tag_snapshot, ensure_ascii=False),
                        run.session_id,
                    ),
                )
                conn.commit()
        return run, None

    def save_run(self, run: FocusRunRecord) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO focus_runs (
                        id, status, reason, trigger_type, started_at, finished_at,
                        note_count, summary, notification_status, archive_id,
                        tag_snapshot_json, session_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        status = excluded.status,
                        reason = excluded.reason,
                        trigger_type = excluded.trigger_type,
                        started_at = excluded.started_at,
                        finished_at = excluded.finished_at,
                        note_count = excluded.note_count,
                        summary = excluded.summary,
                        notification_status = excluded.notification_status,
                        archive_id = excluded.archive_id,
                        tag_snapshot_json = excluded.tag_snapshot_json,
                        session_id = excluded.session_id
                    """,
                    (
                        run.id,
                        run.status,
                        run.reason,
                        run.trigger_type,
                        run.started_at.isoformat(),
                        run.finished_at.isoformat() if run.finished_at else None,
                        run.note_count,
                        run.summary,
                        run.notification_status,
                        run.archive_id,
                        json.dumps(run.tag_snapshot, ensure_ascii=False),
                        run.session_id,
                    ),
                )
                conn.commit()

    def get_run(self, run_id: str) -> FocusRunRecord | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT id, status, reason, trigger_type, started_at, finished_at,
                           note_count, summary, notification_status, archive_id,
                           tag_snapshot_json, session_id
                    FROM focus_runs
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (run_id,),
                ).fetchone()
        return self._row_to_run(row) if row else None

    def get_running_run(self) -> FocusRunRecord | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT id, status, reason, trigger_type, started_at, finished_at,
                           note_count, summary, notification_status, archive_id,
                           tag_snapshot_json, session_id
                    FROM focus_runs
                    WHERE status = 'running'
                    ORDER BY started_at DESC
                    LIMIT 1
                    """
                ).fetchone()
        return self._row_to_run(row) if row else None

    def list_runs(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        status: str | None = None,
    ) -> tuple[list[FocusRunRecord], int]:
        safe_page = max(1, page)
        safe_page_size = max(1, min(page_size, 100))
        offset = (safe_page - 1) * safe_page_size
        where = ""
        params: list[object] = []
        if status:
            where = "WHERE status = ?"
            params.append(status)

        with self._lock:
            with self._connect() as conn:
                total = int(
                    conn.execute(
                        f"SELECT COUNT(*) AS count FROM focus_runs {where}",
                        params,
                    ).fetchone()["count"]
                )
                rows = conn.execute(
                    f"""
                    SELECT id, status, reason, trigger_type, started_at, finished_at,
                           note_count, summary, notification_status, archive_id,
                           tag_snapshot_json, session_id
                    FROM focus_runs
                    {where}
                    ORDER BY started_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    [*params, safe_page_size, offset],
                ).fetchall()
        return [self._row_to_run(row) for row in rows], total

    def register_task(self, run_id: str, task: asyncio.Task) -> None:
        self._running_tasks[run_id] = task

        def _cleanup(_: asyncio.Task) -> None:
            self._running_tasks.pop(run_id, None)

        task.add_done_callback(_cleanup)

    def unregister_task(self, run_id: str) -> None:
        self._running_tasks.pop(run_id, None)

    async def cancel_running_run(self, run_id: str) -> FocusRunRecord | None:
        task = self._running_tasks.get(run_id)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        run = self.get_run(run_id)
        if run and run.status == "running":
            run.status = "cancelled"
            run.reason = "cancelled"
            run.finished_at = datetime.now(timezone.utc)
            run.summary = run.summary or "本轮巡检已取消"
            run.notification_status = "cancelled"
            self.save_run(run)
        return self.get_run(run_id)

    def save_run_archive(self, archive: FocusRunArchive) -> None:
        archive_path = self.archives_dir / archive.run_id
        archive_path.mkdir(parents=True, exist_ok=True)
        (archive_path / "meta.json").write_text(
            json.dumps(archive.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_run_archive(self, run_id: str) -> FocusRunArchive | None:
        archive_path = self.archives_dir / run_id / "meta.json"
        if not archive_path.exists():
            return None
        return FocusRunArchive(
            **json.loads(archive_path.read_text(encoding="utf-8"))
        )

    @staticmethod
    def _row_to_note_summary(row: sqlite3.Row) -> FocusNoteSummary:
        return FocusNoteSummary(
            id=str(row["id"]),
            title=str(row["title"]),
            previewText=str(row["preview_text"] or ""),
            tags=json.loads(row["tags_json"] or "[]"),
            source=str(row["source"]),
            createdAt=datetime.fromisoformat(str(row["created_at"])),
            runId=row["run_id"],
        )

    @staticmethod
    def _row_to_note(row: sqlite3.Row) -> FocusNote:
        return FocusNote(
            id=str(row["id"]),
            title=str(row["title"]),
            content=str(row["content"]),
            previewText=str(row["preview_text"] or ""),
            tags=json.loads(row["tags_json"] or "[]"),
            source=str(row["source"]),
            createdAt=datetime.fromisoformat(str(row["created_at"])),
            sessionId=row["session_id"],
            runId=row["run_id"],
            fingerprint=row["fingerprint"],
        )

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> FocusRunRecord:
        return FocusRunRecord(
            id=str(row["id"]),
            status=str(row["status"]),
            reason=row["reason"],
            triggerType=str(row["trigger_type"]),
            startedAt=datetime.fromisoformat(str(row["started_at"])),
            finishedAt=(
                datetime.fromisoformat(str(row["finished_at"]))
                if row["finished_at"]
                else None
            ),
            noteCount=int(row["note_count"] or 0),
            summary=str(row["summary"] or ""),
            notificationStatus=str(row["notification_status"] or "pending"),
            archiveId=row["archive_id"],
            tagSnapshot=json.loads(row["tag_snapshot_json"] or "[]"),
            sessionId=row["session_id"],
        )
