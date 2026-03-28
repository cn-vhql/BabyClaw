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
from .executor import FocusRunExecutor
from .models import (
    FocusNote,
    FocusRunArchive,
    FocusRunRecord,
)
from .runtime import FocusRunContext, reset_focus_run_context, set_focus_run_context

logger = logging.getLogger(__name__)

FOCUS_NOTIFICATION_NONE = "none"
FOCUS_NOTIFICATION_LAST = "last"
FOCUS_SESSION_PREFIX = "focus:watch"
FOCUS_USER_ID = "focus_watch"


@dataclass(frozen=True)
class FocusRunResult:
    """Lightweight scheduler result for one focus-monitoring execution."""

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


def _build_recent_notes_context(recent_notes, language: str) -> str:
    if not recent_notes:
        return ""

    if (language or "").lower().startswith("zh"):
        lines = [
            "最近已记录的关注要点（避免重复记录相同结论，只有明显新变化才再写入）：",
        ]
        for note in recent_notes:
            tag_text = "、".join(note.tags) if note.tags else "未分类"
            lines.append(f"- {note.title} [{tag_text}] {note.preview_text}")
        return "\n".join(lines)

    lines = [
        "Recent saved focus notes (avoid repeating the same conclusion unless there is a meaningful new change):",
    ]
    for note in recent_notes:
        tag_text = ", ".join(note.tags) if note.tags else "uncategorized"
        lines.append(f"- {note.title} [{tag_text}] {note.preview_text}")
    return "\n".join(lines)


def _build_focus_prompt(tags: list[str], language: str, recent_notes: str) -> str:
    bullet_tags = "\n".join(f"- {tag}" for tag in tags)
    recent_notes_section = f"\n\n{recent_notes}" if recent_notes else ""

    if (language or "").lower().startswith("zh"):
        return textwrap.dedent(
            f"""
            你正在执行一轮固定周期的“关注巡检”。

            当前关注标签：
            {bullet_tags}{recent_notes_section}

            目标：
            1. 围绕这些标签自主探索，可使用已有工具、技能、知识库、浏览能力等。
            2. 只在发现“重要事件、明显变化、值得记录的新进展”时，调用 `write_focus_note` 写入一条或多条要点。
            3. 每条要点要写清标题、要点内容、标签、来源。
            4. 如果没有重要变化，不要写入任何要点，也不要做无意义输出。
            5. 如有必要，你可以调用 `add_focus_tag`、`list_focus_tags`、`remove_focus_tag` 来维护关注标签。

            要求：
            - 重点关注最新变化和事实性信息。
            - 写入要点时内容要简洁、可追溯。
            - 避免重复记录近期已经写过的结论，只有出现明显新增信息时才重新写入。
            - 保持静默执行，不需要面向用户写总结性聊天回复。
            """
        ).strip()

    return textwrap.dedent(
        f"""
        You are running a scheduled focus-monitoring cycle.

        Current focus tags:
        {bullet_tags}{recent_notes_section}

        Goals:
        1. Explore around these tags using the tools, skills, knowledge, and browser abilities you already have.
        2. Only when you find important events, meaningful changes, or notable new developments, call `write_focus_note` to record one or more notes.
        3. Each note should include a clear title, concise content, relevant tags, and a source.
        4. If nothing important changed, stay silent and do not write any notes.
        5. If needed, you may manage the focus tags with `add_focus_tag`, `list_focus_tags`, and `remove_focus_tag`.

        Requirements:
        - Prioritize recent changes and concrete facts.
        - Keep notes concise and traceable.
        - Avoid repeating recently saved conclusions unless there is a meaningful update.
        - This run is silent by default; do not produce a user-facing summary unless it becomes a persisted focus note.
        """
    ).strip()


def _build_notification_text(notes: list[FocusNote], language: str) -> str:
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


def _build_focus_session_id() -> str:
    return f"{FOCUS_SESSION_PREFIX}:{uuid.uuid4().hex}"


def _build_run_summary(status: str, notes: list[FocusNote], reason: str | None) -> str:
    if status == "completed" and notes:
        titles = "；".join(note.title for note in notes[:3])
        if len(notes) > 3:
            titles += "…"
        return f"生成 {len(notes)} 条关注要点：{titles}"
    if status == "completed":
        return "本轮未发现新的重要变化"
    if status == "timed_out":
        return "本轮关注巡检执行超时"
    if status == "cancelled":
        return "本轮关注巡检已取消"
    if status == "failed":
        return reason or "本轮关注巡检执行失败"
    if status == "skipped":
        reason_map = {
            "no_tags": "当前未配置关注标签",
            "disabled": "关注巡检已关闭",
            "within_do_not_disturb": "当前处于免打扰时间",
            "runner_unavailable": "运行器不可用",
            "focus_service_unavailable": "关注服务不可用",
        }
        return reason_map.get(reason or "", "本轮关注巡检被跳过")
    return reason or ""


async def _execute_focus_run(
    *,
    runner: Any,
    channel_manager: Any,
    workspace: Any,
    run_record: FocusRunRecord,
    trigger: str,
    agent_id: str | None = None,
) -> FocusRunRecord:
    focus_service = workspace.focus_service
    agent_config = load_agent_config(agent_id) if agent_id else None
    language = getattr(agent_config, "language", "zh") if agent_config else "zh"
    recent_notes_context = _build_recent_notes_context(
        focus_service.list_recent_note_summaries(limit=5),
        language,
    )
    prompt = _build_focus_prompt(run_record.tag_snapshot, language, recent_notes_context)

    token = set_focus_run_context(
        FocusRunContext(
            run_id=run_record.id,
            session_id=run_record.session_id,
            origin="manual_focus" if trigger == "manual" else "scheduled_focus",
        )
    )

    execution_result = None
    notification_result: dict[str, Any] = {}
    notes: list[FocusNote] = []

    try:
        if not run_record.tag_snapshot:
            run_record.status = "skipped"
            run_record.reason = "no_tags"
            return run_record

        executor = FocusRunExecutor(
            workspace,
            runner=runner,
            user_id=FOCUS_USER_ID,
        )
        execution_result = await asyncio.wait_for(
            executor.execute(
                prompt=prompt,
                session_id=run_record.session_id or _build_focus_session_id(),
            ),
            timeout=180,
        )
        run_record.status = "completed"
    except asyncio.TimeoutError:
        run_record.status = "timed_out"
        run_record.reason = "timeout"
        notification_result = {"status": "timeout"}
    except asyncio.CancelledError:
        run_record.status = "cancelled"
        run_record.reason = "cancelled"
        notification_result = {"status": "cancelled"}
        raise
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("focus run failed: %s", exc, exc_info=True)
        run_record.status = "failed"
        run_record.reason = str(exc)
        notification_result = {"status": "failed", "error": str(exc)}
    finally:
        reset_focus_run_context(token)

        notes = focus_service.list_notes_by_run(run_record.id)
        run_record.note_count = len(notes)
        run_record.finished_at = datetime.now(timezone.utc)

        if run_record.status == "completed" and trigger == "scheduled" and notes:
            target = _resolve_notification_target(
                getattr(
                    get_focus_config(agent_id),
                    "notification_channel",
                    FOCUS_NOTIFICATION_LAST,
                ),
                agent_id,
            )
            if target is None:
                notification_result = {"status": "skipped_no_target"}
            else:
                try:
                    await channel_manager.send_text(
                        channel=target.channel,
                        user_id=target.user_id,
                        session_id=target.session_id,
                        text=_build_notification_text(notes, language),
                        meta={"focus_notification": True},
                    )
                    notification_result = {
                        "status": "sent",
                        "channel": target.channel,
                    }
                except Exception as exc:  # pylint: disable=broad-except
                    logger.warning("focus notification failed: %s", exc, exc_info=True)
                    notification_result = {
                        "status": "failed",
                        "error": str(exc),
                    }
        elif run_record.status == "completed" and trigger == "manual":
            notification_result = {"status": "not_applicable"}
        elif run_record.status == "completed":
            notification_result = {"status": "skipped_no_notes"}

        run_record.notification_status = str(
            notification_result.get("status", run_record.notification_status)
        )
        run_record.archive_id = run_record.id
        run_record.summary = _build_run_summary(
            run_record.status,
            notes,
            run_record.reason,
        )
        focus_service.save_run(run_record)
        focus_service.save_run_archive(
            FocusRunArchive(
                runId=run_record.id,
                prompt=prompt,
                fullOutput=(execution_result.full_output if execution_result else ""),
                toolExecutionLog=(
                    execution_result.tool_execution_log if execution_result else []
                ),
                noteIds=[note.id for note in notes],
                tagSnapshot=run_record.tag_snapshot,
                notificationResult=notification_result,
                errorMessage=run_record.reason,
                createdAt=run_record.finished_at or datetime.now(timezone.utc),
            )
        )

    return run_record


async def _run_focus_task(
    *,
    runner: Any,
    channel_manager: Any,
    workspace: Any,
    run_record: FocusRunRecord,
    agent_id: str | None = None,
    trigger: str,
) -> None:
    try:
        await _execute_focus_run(
            runner=runner,
            channel_manager=channel_manager,
            workspace=workspace,
            run_record=run_record,
            trigger=trigger,
            agent_id=agent_id,
        )
    except asyncio.CancelledError:
        logger.info("focus run cancelled: %s", run_record.id)
    except Exception:
        logger.exception("focus background run failed: %s", run_record.id)
    finally:
        workspace.focus_service.unregister_task(run_record.id)


async def start_focus_run(
    *,
    runner: Any,
    channel_manager: Any,
    workspace: Any,
    agent_id: str | None = None,
    trigger: str = "manual",
) -> tuple[FocusRunRecord | None, FocusRunRecord | None]:
    """Start a focus run asynchronously for manual execution."""
    if workspace is None or getattr(workspace, "focus_service", None) is None:
        raise ValueError("FocusService not initialized")
    if runner is None:
        raise ValueError("Runner not initialized")

    focus_service = workspace.focus_service
    tag_snapshot = focus_service.list_tags()
    session_id = _build_focus_session_id()
    run_record, running = focus_service.create_running_run(
        trigger_type="manual" if trigger == "manual" else "scheduled",
        tag_snapshot=tag_snapshot,
        session_id=session_id,
    )
    if run_record is None:
        return None, running

    task = asyncio.create_task(
        _run_focus_task(
            runner=runner,
            channel_manager=channel_manager,
            workspace=workspace,
            run_record=run_record,
            agent_id=agent_id,
            trigger=trigger,
        )
    )
    focus_service.register_task(run_record.id, task)
    return run_record, None


async def run_focus_once(
    *,
    runner: Any,
    channel_manager: Any,
    workspace: Any,
    agent_id: str | None = None,
    trigger: str = "scheduled",
) -> FocusRunResult:
    """Run one focus-monitoring cycle synchronously for the scheduler."""
    is_manual = trigger == "manual"

    if workspace is None or getattr(workspace, "focus_service", None) is None:
        logger.debug("focus skipped: focus service unavailable")
        return FocusRunResult(status="skipped", reason="focus_service_unavailable")

    if runner is None:
        logger.debug("focus skipped: runner unavailable")
        return FocusRunResult(status="skipped", reason="runner_unavailable")

    focus_service = workspace.focus_service
    focus_config = get_focus_config(agent_id)

    if not is_manual and not getattr(focus_config, "enabled", False):
        logger.debug("focus skipped: disabled")
        return FocusRunResult(status="skipped", reason="disabled")

    if not is_manual and _is_in_quiet_hours(
        getattr(focus_config, "do_not_disturb", None),
    ):
        logger.debug("focus skipped: within do-not-disturb window")
        return FocusRunResult(status="skipped", reason="within_do_not_disturb")

    tags = focus_service.list_tags()
    if not tags and not is_manual:
        logger.debug("focus skipped: no focus tags configured")
        return FocusRunResult(status="skipped", reason="no_tags")

    session_id = _build_focus_session_id()
    run_record, running = focus_service.create_running_run(
        trigger_type="manual" if is_manual else "scheduled",
        tag_snapshot=tags,
        session_id=session_id,
    )
    if run_record is None:
        logger.debug("focus skipped: already running")
        return FocusRunResult(
            status="skipped",
            reason="already_running",
            run_id=running.id if running else None,
        )

    current_task = asyncio.current_task()
    if current_task is not None:
        focus_service.register_task(run_record.id, current_task)

    try:
        final_record = await _execute_focus_run(
            runner=runner,
            channel_manager=channel_manager,
            workspace=workspace,
            run_record=run_record,
            trigger=trigger,
            agent_id=agent_id,
        )
        return FocusRunResult(
            status=final_record.status,
            reason=final_record.reason,
            note_count=final_record.note_count,
            run_id=final_record.id,
        )
    finally:
        focus_service.unregister_task(run_record.id)
