# -*- coding: utf-8 -*-
"""Synchronize evolution config with the default auto-evolution cron job."""

from __future__ import annotations

from ...config.config import save_agent_config

AUTO_EVOLUTION_JOB_ID = "_auto_evolution_daily"


async def sync_evolution_config_with_cron(workspace, *, persist: bool = True):
    """Keep evolution config aligned with the default auto-evolution cron job."""
    current = workspace.config.evolution.model_copy(deep=True)
    updated = current.model_copy(deep=True)

    cron_repo = workspace.cron_manager._repo if workspace.cron_manager else None
    auto_job_enabled = False
    if cron_repo is not None:
        auto_job = await cron_repo.get_job(AUTO_EVOLUTION_JOB_ID)
        auto_job_enabled = bool(
            auto_job
            and auto_job.enabled
            and auto_job.task_type == "evolution"
        )

    if auto_job_enabled:
        updated.enabled = True
        updated.auto_evolution = True
    elif updated.auto_evolution:
        updated.auto_evolution = False

    if updated.model_dump(mode="json") != current.model_dump(mode="json"):
        workspace.config.evolution = updated
        if persist:
            save_agent_config(workspace.agent_id, workspace.config)

    return workspace.config.evolution
