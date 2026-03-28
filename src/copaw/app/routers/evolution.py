# -*- coding: utf-8 -*-
"""API routes for evolution management."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request

from ...config.config import save_agent_config
from ..evolution.config_sync import (
    AUTO_EVOLUTION_JOB_ID,
    sync_evolution_config_with_cron,
)
from ..evolution.executor import EvolutionExecutor
from ..evolution.models import (
    EvolutionArchive,
    EvolutionRecord,
    EvolutionRollbackResult,
    EvolutionRunRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evolution", tags=["evolution"])


async def _get_workspace_and_repo(request: Request):
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    return workspace, workspace.evolution_repo


async def _run_evolution_task(
    *,
    workspace,
    repo,
    req: EvolutionRunRequest,
    record: EvolutionRecord,
) -> None:
    try:
        executor = EvolutionExecutor(
            workspace=workspace,
            repo=repo,
        )
        await executor.execute_with_record(req, record)
    except Exception as exc:
        logger.error("Background evolution failed: %s", exc, exc_info=True)
        latest = await repo.get_record(record.id)
        if latest and latest.status == "running":
            latest.status = "failed"
            latest.error_message = str(exc)
            await repo.save_record(latest)
    finally:
        repo.unregister_task(record.id)


@router.get("/config")
async def get_evolution_config(request: Request) -> dict:
    workspace, _ = await _get_workspace_and_repo(request)
    config = await sync_evolution_config_with_cron(workspace)
    return config.model_dump(mode="json")


@router.put("/config")
async def update_evolution_config(
    request: Request,
    config: dict,
) -> dict:
    from ..agent_context import get_agent_for_request
    from ...config.evolution import EvolutionConfig

    workspace = await get_agent_for_request(request)
    agent_id = workspace.agent_id

    evolution_config = EvolutionConfig(**config)
    if not evolution_config.enabled:
        evolution_config.auto_evolution = False

    workspace.config.evolution = evolution_config
    save_agent_config(agent_id, workspace.config)

    if workspace.cron_manager:
        await _sync_evolution_cron_job(
            workspace=workspace,
            enabled=evolution_config.enabled and evolution_config.auto_evolution,
        )

    return evolution_config.model_dump(mode="json")


async def _sync_evolution_cron_job(*, workspace, enabled: bool) -> None:
    from ..crons.models import CronJobSpec, EvolutionJobConfig, ScheduleSpec

    cron_repo = workspace.cron_manager._repo if workspace.cron_manager else None
    if not cron_repo:
        return

    job_id = AUTO_EVOLUTION_JOB_ID
    if enabled:
        job_spec = CronJobSpec(
            id=job_id,
            name="每日自动进化（12:00）",
            enabled=True,
            schedule=ScheduleSpec(
                type="cron",
                cron="0 12 * * *",
                timezone="Asia/Shanghai",
            ),
            task_type="evolution",
            evolution_config=EvolutionJobConfig(
                trigger_type="cron",
                timeout_seconds=300,
            ),
            dispatch={
                "type": "channel",
                "channel": "",
                "target": {
                    "user_id": "",
                    "session_id": "",
                },
                "mode": "stream",
            },
        )
        await cron_repo.upsert_job(job_spec)
        return

    existing_job = await cron_repo.get_job(job_id)
    if existing_job and existing_job.id.startswith("_auto_"):
        await cron_repo.delete_job(job_id)


@router.get("/records")
async def list_evolution_records(
    request: Request,
    limit: int = 50,
) -> list[dict]:
    _, repo = await _get_workspace_and_repo(request)
    return await repo.list_records(limit=limit)


@router.get("/records/{record_id}")
async def get_evolution_record(
    record_id: str,
    request: Request,
) -> dict:
    _, repo = await _get_workspace_and_repo(request)
    record = await repo.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record.model_dump(mode="json")


@router.get("/records/{record_id}/archive")
async def get_evolution_archive_by_record(
    record_id: str,
    request: Request,
) -> dict:
    _, repo = await _get_workspace_and_repo(request)
    record = await repo.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    archive = await repo.get_archive_by_evolution_id(record_id)
    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found")
    return archive.model_dump(mode="json")


@router.get("/archives/{archive_id}")
async def get_evolution_archive(
    archive_id: str,
    request: Request,
) -> dict:
    _, repo = await _get_workspace_and_repo(request)
    archive = await repo.get_archive(archive_id)
    if not archive:
        archive = await repo.get_archive_by_evolution_id(archive_id)
    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found")
    return archive.model_dump(mode="json")


@router.post("/run")
async def run_evolution(
    request: Request,
    req: EvolutionRunRequest,
) -> dict:
    workspace, repo = await _get_workspace_and_repo(request)
    await sync_evolution_config_with_cron(workspace)

    if not workspace.config.evolution.enabled:
        raise HTTPException(status_code=400, detail="Evolution is disabled")

    running = await repo.get_running_record()
    if running:
        raise HTTPException(
            status_code=409,
            detail=f"Evolution is already running: {running.id}",
        )

    generation = await repo.get_current_generation()
    next_generation = generation + 1
    max_gen = workspace.config.evolution.max_generations
    if max_gen is not None and max_gen > 0 and next_generation > max_gen:
        record = await repo.create_failed_record(
            generation=next_generation,
            agent_id=workspace.agent_id,
            agent_name=workspace.config.name,
            trigger_type=req.trigger_type,
            error_message=f"已达到最大代数限制 ({max_gen})",
        )
        return record.model_dump(mode="json")

    record, _ = await repo.create_running_record(
        agent_id=workspace.agent_id,
        agent_name=workspace.config.name,
        trigger_type=req.trigger_type,
    )
    if record is None:
        raise HTTPException(status_code=409, detail="Evolution is already running")

    task = asyncio.create_task(
        _run_evolution_task(
            workspace=workspace,
            repo=repo,
            req=req,
            record=record,
        )
    )
    repo.register_task(record.id, task)
    return record.model_dump(mode="json")


@router.post("/records/{record_id}/cancel")
async def cancel_evolution_record(
    record_id: str,
    request: Request,
) -> dict:
    _, repo = await _get_workspace_and_repo(request)
    record = await repo.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if record.status != "running":
        raise HTTPException(status_code=400, detail="Only running records can be cancelled")

    cancelled = await repo.cancel_running_record(record_id)
    if not cancelled:
        raise HTTPException(status_code=500, detail="Failed to cancel record")
    return cancelled.model_dump(mode="json")


@router.post("/records/{record_id}/rollback")
async def rollback_evolution_record(
    record_id: str,
    request: Request,
) -> dict:
    _, repo = await _get_workspace_and_repo(request)
    record = await repo.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    try:
        reverted_record, active_record = await repo.rollback_to_previous(record_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = EvolutionRollbackResult(
        active_record_id=active_record.id,
        reverted_record=reverted_record,
        active_record=active_record,
    )
    return result.model_dump(mode="json")


@router.get("/archives/{archive_id}/files/{filename}")
async def get_archive_file(
    archive_id: str,
    filename: str,
    request: Request,
) -> dict:
    _, repo = await _get_workspace_and_repo(request)
    content = await repo.get_archive_file(archive_id, filename)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {"filename": filename, "content": content}


@router.delete("/records/{record_id}")
async def delete_evolution_record(
    record_id: str,
    request: Request,
) -> dict:
    _, repo = await _get_workspace_and_repo(request)
    record = await repo.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if record.status not in {"failed", "cancelled"}:
        raise HTTPException(
            status_code=400,
            detail=f"Can only delete failed or cancelled records, current status: {record.status}",
        )

    success = await repo.delete_record(record_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete record")
    return {"message": "Record deleted successfully"}
