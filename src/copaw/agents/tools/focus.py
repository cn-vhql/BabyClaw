# -*- coding: utf-8 -*-
"""Focus note tools exposed to the agent."""

from __future__ import annotations

import logging
from pathlib import Path

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ...app.focus.runtime import get_focus_run_context
from ...app.focus.service import FocusService

logger = logging.getLogger(__name__)


def _get_focus_service() -> FocusService:
    from ...app.agent_context import get_current_agent_id
    from ...config.config import load_agent_config

    agent_id = get_current_agent_id()
    config = load_agent_config(agent_id)
    return FocusService(Path(config.workspace_dir))


def _ok(text: str) -> ToolResponse:
    return ToolResponse(content=[TextBlock(type="text", text=text)])


def _error(text: str) -> ToolResponse:
    return ToolResponse(content=[TextBlock(type="text", text=text)])


def list_focus_tags() -> ToolResponse:
    """List all persisted focus tags for the current agent."""
    try:
        service = _get_focus_service()
        tags = service.list_tags()
        if not tags:
            return _ok("No focus tags configured yet.")
        return _ok("Configured focus tags:\n- " + "\n- ".join(tags))
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("list_focus_tags failed: %s", exc, exc_info=True)
        return _error(f"Failed to list focus tags: {exc}")


def add_focus_tag(tag: str) -> ToolResponse:
    """Add a focus tag for future scheduled monitoring."""
    try:
        service = _get_focus_service()
        created = service.add_tag(tag)
        clean_tag = " ".join((tag or "").strip().split())
        if not clean_tag:
            return _error("Tag cannot be empty.")
        if created:
            return _ok(f"Added focus tag: {clean_tag}")
        return _ok(f"Focus tag already existed: {clean_tag}")
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("add_focus_tag failed: %s", exc, exc_info=True)
        return _error(f"Failed to add focus tag: {exc}")


def remove_focus_tag(tag: str) -> ToolResponse:
    """Remove a focus tag from scheduled monitoring."""
    try:
        service = _get_focus_service()
        deleted = service.remove_tag(tag)
        clean_tag = " ".join((tag or "").strip().split())
        if not clean_tag:
            return _error("Tag cannot be empty.")
        if deleted:
            return _ok(f"Removed focus tag: {clean_tag}")
        return _ok(f"Focus tag not found: {clean_tag}")
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("remove_focus_tag failed: %s", exc, exc_info=True)
        return _error(f"Failed to remove focus tag: {exc}")


def write_focus_note(
    title: str,
    content: str,
    tags: list[str] | str | None = None,
    source: str | None = None,
) -> ToolResponse:
    """Write a focus note that will appear in the focus timeline."""
    try:
        service = _get_focus_service()
        ctx = get_focus_run_context()
        note = service.write_note(
            title=title,
            content=content,
            tags=tags,
            source=(source or (ctx.origin if ctx else "manual") or "manual"),
            session_id=ctx.session_id if ctx else None,
            run_id=ctx.run_id if ctx else None,
        )
        tag_text = ", ".join(note.tags) if note.tags else "no tags"
        return _ok(
            f"Focus note saved: {note.title}\n"
            f"Tags: {tag_text}\n"
            f"Source: {note.source}"
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("write_focus_note failed: %s", exc, exc_info=True)
        return _error(f"Failed to write focus note: {exc}")
