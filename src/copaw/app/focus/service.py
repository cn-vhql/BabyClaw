# -*- coding: utf-8 -*-
"""Service layer for focus monitoring."""

from __future__ import annotations

from pathlib import Path

from .models import FocusNote
from .repo.sqlite_repo import SQLiteFocusRepository


class FocusService:
    """Workspace-scoped service for focus tags and notes."""

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

    def list_notes(self, *, limit: int = 200) -> list[FocusNote]:
        return self.repo.list_notes(limit=limit)

    def list_notes_by_run(self, run_id: str) -> list[FocusNote]:
        return self.repo.list_notes_by_run(run_id)
