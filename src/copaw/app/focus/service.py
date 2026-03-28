# -*- coding: utf-8 -*-
"""Service layer for focus monitoring."""

from __future__ import annotations

import asyncio
from pathlib import Path

from .models import FocusNote, FocusNoteSummary, FocusRunArchive, FocusRunRecord
from .repo.sqlite_repo import SQLiteFocusRepository


class FocusService:
    """Workspace-scoped service for focus tags, notes, and run records."""

    def __init__(self, workspace_dir: Path | str):
        self.workspace_dir = Path(workspace_dir)
        self.repo = SQLiteFocusRepository(self.workspace_dir / "focus.sqlite3")

    def list_tags(self) -> list[str]:
        return self.repo.list_tags()

    def replace_tags(self, tags: list[str]) -> list[str]:
        return self.repo.replace_tags(tags)

    def add_tag(self, tag: str) -> bool:
        return self.repo.add_tag(tag)

    def remove_tag(self, tag: str) -> bool:
        return self.repo.remove_tag(tag)

    def has_tags(self) -> bool:
        return bool(self.list_tags())

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
        return self.repo.write_note(
            title=title,
            content=content,
            tags=tags,
            source=source,
            session_id=session_id,
            run_id=run_id,
        )

    def list_notes(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        query: str | None = None,
    ) -> tuple[list[FocusNoteSummary], int]:
        return self.repo.list_notes(page=page, page_size=page_size, query=query)

    def get_note(self, note_id: str) -> FocusNote | None:
        return self.repo.get_note(note_id)

    def list_notes_by_run(self, run_id: str) -> list[FocusNote]:
        return self.repo.list_notes_by_run(run_id)

    def list_recent_note_summaries(self, *, limit: int = 5) -> list[FocusNoteSummary]:
        return self.repo.list_recent_note_summaries(limit=limit)

    def create_running_run(
        self,
        *,
        trigger_type: str,
        tag_snapshot: list[str],
        session_id: str,
    ) -> tuple[FocusRunRecord | None, FocusRunRecord | None]:
        return self.repo.create_running_run(
            trigger_type=trigger_type,
            tag_snapshot=tag_snapshot,
            session_id=session_id,
        )

    def save_run(self, run: FocusRunRecord) -> None:
        self.repo.save_run(run)

    def get_run(self, run_id: str) -> FocusRunRecord | None:
        return self.repo.get_run(run_id)

    def get_running_run(self) -> FocusRunRecord | None:
        return self.repo.get_running_run()

    def list_runs(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        status: str | None = None,
    ) -> tuple[list[FocusRunRecord], int]:
        return self.repo.list_runs(page=page, page_size=page_size, status=status)

    def register_task(self, run_id: str, task: asyncio.Task) -> None:
        self.repo.register_task(run_id, task)

    def unregister_task(self, run_id: str) -> None:
        self.repo.unregister_task(run_id)

    async def cancel_running_run(self, run_id: str) -> FocusRunRecord | None:
        return await self.repo.cancel_running_run(run_id)

    def save_run_archive(self, archive: FocusRunArchive) -> None:
        self.repo.save_run_archive(archive)

    def get_run_archive(self, run_id: str) -> FocusRunArchive | None:
        return self.repo.get_run_archive(run_id)
