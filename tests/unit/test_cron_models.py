# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from pydantic import ValidationError

from copaw.app.crons.models import CronJobSpec, EvolutionJobConfig, ScheduleSpec


class CronJobSpecTests(unittest.TestCase):
    def test_evolution_job_fills_default_dispatch_when_missing(self) -> None:
        spec = CronJobSpec(
            id="_auto_evolution_daily",
            name="每日自动进化",
            schedule=ScheduleSpec(cron="0 12 * * *", timezone="Asia/Shanghai"),
            task_type="evolution",
            evolution_config=EvolutionJobConfig(
                trigger_type="cron",
                timeout_seconds=300,
            ),
        )

        self.assertEqual(spec.dispatch.type, "channel")
        self.assertEqual(spec.dispatch.channel, "")
        self.assertEqual(spec.dispatch.target.user_id, "")
        self.assertEqual(spec.dispatch.target.session_id, "")
        self.assertEqual(spec.dispatch.mode, "stream")
        self.assertEqual(spec.dispatch.meta, {})

    def test_evolution_job_fills_missing_dispatch_target(self) -> None:
        spec = CronJobSpec(
            id="_auto_evolution_daily",
            name="每日自动进化",
            schedule=ScheduleSpec(cron="0 12 * * *", timezone="Asia/Shanghai"),
            task_type="evolution",
            evolution_config=EvolutionJobConfig(
                trigger_type="auto",
                timeout_seconds=600,
            ),
            dispatch={"type": "channel"},
        )

        self.assertEqual(spec.dispatch.target.user_id, "")
        self.assertEqual(spec.dispatch.target.session_id, "")

    def test_agent_job_still_requires_dispatch_target(self) -> None:
        with self.assertRaises(ValidationError):
            CronJobSpec(
                id="agent-job",
                name="Agent Job",
                schedule=ScheduleSpec(cron="0 9 * * *", timezone="UTC"),
                task_type="agent",
                request={"input": [{"role": "user", "content": "hello"}]},
                dispatch={"type": "channel", "channel": "console"},
            )
