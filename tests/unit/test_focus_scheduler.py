# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from copaw.app.focus.runtime import get_focus_run_context
from copaw.app.focus.scheduler import run_focus_once
from copaw.app.focus.service import FocusService


class _FakeChannelManager:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send_text(self, **kwargs) -> None:
        self.calls.append(kwargs)


class _FakeRunner:
    def __init__(self, focus_service: FocusService, *, write_note: bool) -> None:
        self._focus_service = focus_service
        self._write_note = write_note

    async def stream_query(self, _req):
        if self._write_note:
            ctx = get_focus_run_context()
            assert ctx is not None
            self._focus_service.write_note(
                title="OpenAI update",
                content="Observed a notable new change.",
                tags=["OpenAI"],
                source=ctx.origin,
                session_id=ctx.session_id,
                run_id=ctx.run_id,
            )

        if False:
            yield None


class FocusSchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_manual_run_bypasses_disabled_and_skips_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            focus_service = FocusService(Path(tmp_dir))
            focus_service.replace_tags(["OpenAI"])
            channel_manager = _FakeChannelManager()
            workspace = SimpleNamespace(focus_service=focus_service)
            runner = _FakeRunner(focus_service, write_note=True)

            with patch(
                "copaw.app.focus.scheduler.get_focus_config",
                return_value=SimpleNamespace(
                    enabled=False,
                    do_not_disturb=None,
                    notification_channel="last",
                ),
            ), patch(
                "copaw.app.focus.scheduler.load_agent_config",
                return_value=SimpleNamespace(language="zh", last_dispatch=None),
            ):
                result = await run_focus_once(
                    runner=runner,
                    channel_manager=channel_manager,
                    workspace=workspace,
                    agent_id="default",
                    trigger="manual",
                )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.note_count, 1)
        self.assertEqual(len(channel_manager.calls), 0)

    async def test_manual_run_skips_when_no_focus_tags_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            focus_service = FocusService(Path(tmp_dir))
            workspace = SimpleNamespace(focus_service=focus_service)

            with patch(
                "copaw.app.focus.scheduler.get_focus_config",
                return_value=SimpleNamespace(
                    enabled=False,
                    do_not_disturb=None,
                    notification_channel="last",
                ),
            ), patch(
                "copaw.app.focus.scheduler.load_agent_config",
                return_value=SimpleNamespace(language="zh", last_dispatch=None),
            ):
                result = await run_focus_once(
                    runner=_FakeRunner(focus_service, write_note=False),
                    channel_manager=_FakeChannelManager(),
                    workspace=workspace,
                    agent_id="default",
                    trigger="manual",
                )

        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.reason, "no_tags")
