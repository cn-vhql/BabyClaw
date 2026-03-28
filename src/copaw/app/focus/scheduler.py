# -*- coding: utf-8 -*-
"""Scheduled focus monitoring execution."""

from __future__ import annotations

import asyncio
import logging
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ...config import get_focus_config, load_config
from ...config.config import load_agent_config
from .runtime import FocusRunContext, reset_focus_run_context, set_focus_run_context

logger = logging.getLogger(__name__)

FOCUS_NOTIFICATION_NONE = "none"
FOCUS_NOTIFICATION_LAST = "last"
FOCUS_SESSION_ID = "focus:watch"
FOCUS_USER_ID = "focus_watch"


@dataclass(frozen=True)
class FocusRunResult:
    """Result for one focus-monitoring execution."""

    status: str
    reason: str | None = None
    note_count: int = 0
    run_id: str | None = None


def _is_in_quiet_hours(quiet_hours: Any) -> bool:
    if (
        not quiet_hours
        or not hasattr(quiet_hours, "start")
        or not hasattr(quiet_hours, "end")
    ):
        return False

    try:
        start_parts = quiet_hours.start.strip().split(":")
        end_parts = quiet_hours.end.strip().split(":")
        start_t = time(
            int(start_parts[0]),
            int(start_parts[1]) if len(start_parts) > 1 else 0,
        )
        end_t = time(
            int(end_parts[0]),
            int(end_parts[1]) if len(end_parts) > 1 else 0,
        )
    except (ValueError, IndexError, AttributeError):
        return False

    user_tz = load_config().user_timezone or "UTC"
    try:
        now = datetime.now(ZoneInfo(user_tz)).time()
    except (ZoneInfoNotFoundError, KeyError):
        logger.warning(
            "Invalid timezone %r in config, falling back to UTC for focus quiet-hours check.",
            user_tz,
        )
        now = datetime.now(timezone.utc).time()

    if start_t <= end_t:
        return start_t <= now <= end_t
    return now >= start_t or now <= end_t


def _build_focus_prompt(tags: list[str], language: str) -> str:
    bullet_tags = "\n".join(f"- {tag}" for tag in tags)
    if (language or "").lower().startswith("zh"):
        return textwrap.dedent(
            f"""
            你正在执行一轮固定周期的“关注巡检”。

            当前关注标签：
            {bullet_tags}

            目标：
            1. 围绕这些标签自主探索，可使用已有工具、技能、知识库、浏览能力等。
            2. 只在发现“重要事件、明显变化、值得记录的新进展”时，调用 `write_focus_note` 写入一条或多条要点。
            3. 每条要点要写清标题、要点内容、标签、来源。
            4. 如果没有重要变化，不要写入任何要点，也不要做无意义输出。
            5. 如有必要，你可以调用 `add_focus_tag`、`list_focus_tags`、`remove_focus_tag` 来维护关注标签。

            要求：
            - 重点关注最新变化和事实性信息。
            - 写入要点时内容要简洁、可追溯。
            - 保持静默执行，不需要面向用户写总结性聊天回复。
            """
        ).strip()

    return textwrap.dedent(
        f"""
        You are running a scheduled focus-monitoring cycle.

        Current focus tags:
        {bullet_tags}

        Goals:
        1. Explore around these tags using the tools, skills, knowledge, and browser abilities you already have.
        2. Only when you find important events, meaningful changes, or notable new developments, call `write_focus_note` to record one or more notes.
        3. Each note should include a clear title, concise content, relevant tags, and a source.
        4. If nothing important changed, stay silent and do not write any notes.
        5. If needed, you may manage the focus tags with `add_focus_tag`, `list_focus_tags`, and `remove_focus_tag`.

        Requirements:
        - Prioritize recent changes and concrete facts.
        - Keep notes concise and traceable.
        - This run is silent by default; do not produce a user-facing summary unless it becomes a persisted focus note.
        """
    ).strip()


def _build_notification_text(notes, language: str) -> str:
    lines = []
    if (language or "").lower().startswith("zh"):
        lines.append("关注巡检发现新的重要动态：")
        for note in notes:
            tag_text = "、".join(note.tags) if note.tags else "未分类"
            lines.append(f"- {note.title} [{tag_text}] 来源: {note.source}")
            lines.append(f"  {note.content}")
        return "\n".join(lines)

    lines.append("Focus monitoring found new updates:")
    for note in notes:
        tag_text = ", ".join(note.tags) if note.tags else "uncategorized"
        lines.append(f"- {note.title} [{tag_text}] Source: {note.source}")
        lines.append(f"  {note.content}")
    return "\n".join(lines)


def _resolve_notification_target(notification_channel: str, agent_id: str | None):
    target = (notification_channel or FOCUS_NOTIFICATION_LAST).strip().lower()
    if target == FOCUS_NOTIFICATION_NONE:
        return None

    agent_config = load_agent_config(agent_id) if agent_id else None
    last_dispatch = agent_config.last_dispatch if agent_config else None
    if not last_dispatch:
        return None

    if target != FOCUS_NOTIFICATION_LAST and target != last_dispatch.channel.lower():
        return None

    if not last_dispatch.channel or not last_dispatch.user_id or not last_dispatch.session_id:
        return None

    return last_dispatch


async def run_focus_once(
    *,
    runner: Any,
    channel_manager: Any,
    workspace: Any,
    agent_id: str | None = None,
    trigger: str = "scheduled",
) -> FocusRunResult:
    """Run one focus-monitoring cycle."""
    is_manual = trigger == "manual"

    if workspace is None or getattr(workspace, "focus_service", None) is None:
        logger.debug("focus skipped: focus service unavailable")
        return FocusRunResult(
            status="skipped",
            reason="focus_service_unavailable",
        )

    if runner is None:
        logger.debug("focus skipped: runner unavailable")
        return FocusRunResult(
            status="skipped",
            reason="runner_unavailable",
        )

    focus_config = get_focus_config(agent_id)
    if not is_manual and not getattr(focus_config, "enabled", False):
        logger.debug("focus skipped: disabled")
        return FocusRunResult(status="skipped", reason="disabled")

    if not is_manual and _is_in_quiet_hours(
        getattr(focus_config, "do_not_disturb", None),
    ):
        logger.debug("focus skipped: within do-not-disturb window")
        return FocusRunResult(
            status="skipped",
            reason="within_do_not_disturb",
        )

    tags = workspace.focus_service.list_tags()
    if not tags:
        logger.debug("focus skipped: no focus tags configured")
        return FocusRunResult(status="skipped", reason="no_tags")

    agent_config = load_agent_config(agent_id) if agent_id else None
    language = getattr(agent_config, "language", "zh") if agent_config else "zh"
    prompt = _build_focus_prompt(tags, language)
    run_id = str(uuid.uuid4())

    req = {
        "input": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            },
        ],
        "session_id": FOCUS_SESSION_ID,
        "user_id": FOCUS_USER_ID,
    }

    token = set_focus_run_context(
        FocusRunContext(
            run_id=run_id,
            session_id=FOCUS_SESSION_ID,
            origin="manual_focus" if is_manual else "scheduled_focus",
        )
    )

    async def _run_only() -> None:
        async for _ in runner.stream_query(req):
            pass

    try:
        await asyncio.wait_for(_run_only(), timeout=180)
    except asyncio.TimeoutError:
        logger.warning("focus run timed out")
        return FocusRunResult(
            status="timed_out",
            reason="timeout",
            run_id=run_id,
        )
    finally:
        reset_focus_run_context(token)

    notes = workspace.focus_service.list_notes_by_run(run_id)
    note_count = len(notes)
    if not notes or channel_manager is None or is_manual:
        return FocusRunResult(
            status="completed",
            note_count=note_count,
            run_id=run_id,
        )

    target = _resolve_notification_target(
        getattr(focus_config, "notification_channel", FOCUS_NOTIFICATION_LAST),
        agent_id,
    )
    if target is None:
        return FocusRunResult(
            status="completed",
            note_count=note_count,
            run_id=run_id,
        )

    await channel_manager.send_text(
        channel=target.channel,
        user_id=target.user_id,
        session_id=target.session_id,
        text=_build_notification_text(notes, language),
        meta={"focus_notification": True},
    )
    return FocusRunResult(
        status="completed",
        note_count=note_count,
        run_id=run_id,
    )
