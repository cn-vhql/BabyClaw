# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from .models import CronJobSpec

logger = logging.getLogger(__name__)


class CronExecutor:
    def __init__(self, *, runner: Any, channel_manager: Any, workspace: Any = None):
        self._runner = runner
        self._channel_manager = channel_manager
        self._workspace = workspace

    async def execute(self, job: CronJobSpec) -> None:
        """Execute one job once.

        - task_type text: send fixed text to channel
        - task_type agent: ask agent with prompt, send reply to channel (
            stream_query + send_event)
        - task_type evolution: execute digital life evolution
        """
        target_user_id = job.dispatch.target.user_id
        target_session_id = job.dispatch.target.session_id
        dispatch_meta: Dict[str, Any] = dict(job.dispatch.meta or {})
        logger.info(
            "cron execute: job_id=%s channel=%s task_type=%s "
            "target_user_id=%s target_session_id=%s",
            job.id,
            job.dispatch.channel,
            job.task_type,
            target_user_id[:40] if target_user_id else "",
            target_session_id[:40] if target_session_id else "",
        )

        if job.task_type == "text" and job.text:
            logger.info(
                "cron send_text: job_id=%s channel=%s len=%s",
                job.id,
                job.dispatch.channel,
                len(job.text or ""),
            )
            await self._channel_manager.send_text(
                channel=job.dispatch.channel,
                user_id=target_user_id,
                session_id=target_session_id,
                text=job.text.strip(),
                meta=dispatch_meta,
            )
            return

        if job.task_type == "evolution":
            await self._execute_evolution(job)
            return

        # agent: run request as the dispatch target user so context matches
        logger.info(
            "cron agent: job_id=%s channel=%s stream_query then send_event",
            job.id,
            job.dispatch.channel,
        )
        assert job.request is not None
        req: Dict[str, Any] = job.request.model_dump(mode="json")
        req["user_id"] = target_user_id or "cron"
        req["session_id"] = target_session_id or f"cron:{job.id}"

        async def _run() -> None:
            async for event in self._runner.stream_query(req):
                await self._channel_manager.send_event(
                    channel=job.dispatch.channel,
                    user_id=target_user_id,
                    session_id=target_session_id,
                    event=event,
                    meta=dispatch_meta,
                )

        try:
            await asyncio.wait_for(
                _run(),
                timeout=job.runtime.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "cron execute: job_id=%s timed out after %ss",
                job.id,
                job.runtime.timeout_seconds,
            )
            raise
        except asyncio.CancelledError:
            logger.info("cron execute: job_id=%s cancelled", job.id)
            raise

    async def _execute_evolution(self, job: CronJobSpec) -> None:
        """Execute evolution task."""
        from ..evolution.executor import EvolutionExecutor

        logger.info(
            "cron evolution: job_id=%s executing evolution",
            job.id,
        )

        assert job.evolution_config is not None
        assert self._workspace is not None, "Workspace required for evolution tasks"

        # Get evolution repository
        evolution_repo = self._workspace.evolution_repo

        # Create executor
        executor = EvolutionExecutor(
            workspace=self._workspace,
            repo=evolution_repo,
        )

        # Build request
        from ..evolution.models import EvolutionRunRequest

        request = EvolutionRunRequest(
            trigger_type=job.evolution_config.trigger_type,
            max_iterations=job.evolution_config.max_iterations,
            timeout_seconds=job.evolution_config.timeout_seconds,
        )

        try:
            # Execute evolution
            await asyncio.wait_for(
                executor.execute(request),
                timeout=job.evolution_config.timeout_seconds,
            )
            logger.info(
                "cron evolution: job_id=%s completed successfully",
                job.id,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "cron evolution: job_id=%s timed out after %ss",
                job.id,
                job.evolution_config.timeout_seconds,
            )
            raise
        except Exception as e:
            logger.error(
                "cron evolution: job_id=%s failed: %s",
                job.id,
                e,
                exc_info=True,
            )
            raise
