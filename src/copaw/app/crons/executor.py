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
        from ..evolution.config_sync import sync_evolution_config_with_cron
        from ..evolution.executor import EvolutionExecutor
        from ..evolution.models import EvolutionRunRequest

        logger.info(
            "cron evolution: job_id=%s executing evolution",
            job.id,
        )

        assert job.evolution_config is not None
        assert self._workspace is not None, "Workspace required for evolution tasks"

        await sync_evolution_config_with_cron(self._workspace)

        if not self._workspace.config.evolution.enabled:
            logger.info(
                "cron evolution: job_id=%s skipped because evolution is disabled",
                job.id,
            )
            return

        evolution_repo = self._workspace.evolution_repo
        running = await evolution_repo.get_running_record()
        if running:
            logger.info(
                "cron evolution: job_id=%s skipped because record %s is running",
                job.id,
                running.id,
            )
            return

        generation = await evolution_repo.get_current_generation()
        next_generation = generation + 1
        max_gen = self._workspace.config.evolution.max_generations
        if max_gen is not None and max_gen > 0 and next_generation > max_gen:
            await evolution_repo.create_failed_record(
                generation=next_generation,
                agent_id=self._workspace.agent_id,
                agent_name=self._workspace.config.name,
                trigger_type=job.evolution_config.trigger_type,
                error_message=f"已达到最大代数限制 ({max_gen})",
            )
            logger.info(
                "cron evolution: job_id=%s blocked by max generation limit",
                job.id,
            )
            return

        record, _ = await evolution_repo.create_running_record(
            agent_id=self._workspace.agent_id,
            agent_name=self._workspace.config.name,
            trigger_type=job.evolution_config.trigger_type,
        )
        if record is None:
            logger.info("cron evolution: job_id=%s skipped by single-flight lock", job.id)
            return

        executor = EvolutionExecutor(
            workspace=self._workspace,
            repo=evolution_repo,
        )
        request = EvolutionRunRequest(
            trigger_type=job.evolution_config.trigger_type,
            timeout_seconds=job.evolution_config.timeout_seconds,
        )

        try:
            current_task = asyncio.current_task()
            if current_task is not None:
                evolution_repo.register_task(record.id, current_task)
            await executor.execute_with_record(request, record)
            logger.info(
                "cron evolution: job_id=%s completed successfully",
                job.id,
            )
        except Exception as e:
            logger.error(
                "cron evolution: job_id=%s failed: %s",
                job.id,
                e,
                exc_info=True,
            )
            raise
        finally:
            evolution_repo.unregister_task(record.id)
