# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from copaw.app.crons.api import pause_job, resume_job
from copaw.app.crons.models import CronJobSpec, EvolutionJobConfig, ScheduleSpec
from copaw.app.evolution.config_sync import AUTO_EVOLUTION_JOB_ID


class _FakeCronManager:
    def __init__(self, job: CronJobSpec):
        self.job = job
        self.updated_job: CronJobSpec | None = None
        self.pause_called = False
        self.resume_called = False

    async def get_job(self, job_id: str) -> CronJobSpec | None:
        if job_id == self.job.id:
            return self.job
        return None

    async def create_or_replace_job(self, spec: CronJobSpec) -> None:
        self.updated_job = spec
        self.job = spec

    async def pause_job(self, job_id: str) -> None:
        self.pause_called = True

    async def resume_job(self, job_id: str) -> None:
        self.resume_called = True


def _make_auto_evolution_job(enabled: bool) -> CronJobSpec:
    return CronJobSpec(
        id=AUTO_EVOLUTION_JOB_ID,
        name="每日自动进化",
        enabled=enabled,
        schedule=ScheduleSpec(cron="0 12 * * *", timezone="Asia/Shanghai"),
        task_type="evolution",
        evolution_config=EvolutionJobConfig(
            trigger_type="cron",
            timeout_seconds=300,
        ),
    )


class AutoEvolutionCronApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_pause_auto_evolution_persists_disabled_state(self) -> None:
        mgr = _FakeCronManager(_make_auto_evolution_job(enabled=True))
        workspace = SimpleNamespace()

        with (
            patch(
                "copaw.app.agent_context.get_agent_for_request",
                AsyncMock(return_value=workspace),
            ),
            patch(
                "copaw.app.crons.api.sync_evolution_config_with_cron",
                AsyncMock(),
            ) as sync_mock,
        ):
            response = await pause_job(object(), AUTO_EVOLUTION_JOB_ID, mgr)

        self.assertEqual(response, {"paused": True})
        self.assertIsNotNone(mgr.updated_job)
        assert mgr.updated_job is not None
        self.assertFalse(mgr.updated_job.enabled)
        self.assertFalse(mgr.pause_called)
        sync_mock.assert_awaited_once_with(workspace)

    async def test_resume_auto_evolution_persists_enabled_state(self) -> None:
        mgr = _FakeCronManager(_make_auto_evolution_job(enabled=False))
        workspace = SimpleNamespace()

        with (
            patch(
                "copaw.app.agent_context.get_agent_for_request",
                AsyncMock(return_value=workspace),
            ),
            patch(
                "copaw.app.crons.api.sync_evolution_config_with_cron",
                AsyncMock(),
            ) as sync_mock,
        ):
            response = await resume_job(object(), AUTO_EVOLUTION_JOB_ID, mgr)

        self.assertEqual(response, {"resumed": True})
        self.assertIsNotNone(mgr.updated_job)
        assert mgr.updated_job is not None
        self.assertTrue(mgr.updated_job.enabled)
        self.assertFalse(mgr.resume_called)
        sync_mock.assert_awaited_once_with(workspace)
