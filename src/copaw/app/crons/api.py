# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request

from .manager import CronManager
from .models import CronJobSpec, CronJobView
from ..evolution.config_sync import (
    AUTO_EVOLUTION_JOB_ID,
    sync_evolution_config_with_cron,
)

router = APIRouter(prefix="/cron", tags=["cron"])


async def get_cron_manager(
    request: Request,
) -> CronManager:
    """Get cron manager for the active agent."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    if workspace.cron_manager is None:
        raise HTTPException(
            status_code=500,
            detail="CronManager not initialized",
        )
    return workspace.cron_manager


async def _sync_auto_evolution_enabled_state(
    request: Request,
    mgr: CronManager,
    *,
    job_id: str,
    enabled: bool,
) -> None:
    if job_id != AUTO_EVOLUTION_JOB_ID:
        return

    job = await mgr.get_job(job_id)
    if job is not None:
        await mgr.create_or_replace_job(job.model_copy(update={"enabled": enabled}))

    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    await sync_evolution_config_with_cron(workspace)


@router.get("/jobs", response_model=list[CronJobSpec])
async def list_jobs(mgr: CronManager = Depends(get_cron_manager)):
    return await mgr.list_jobs()


@router.get("/jobs/{job_id}", response_model=CronJobView)
async def get_job(job_id: str, mgr: CronManager = Depends(get_cron_manager)):
    job = await mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return CronJobView(spec=job, state=mgr.get_state(job_id))


@router.post("/jobs", response_model=CronJobSpec)
async def create_job(
    request: Request,
    spec: CronJobSpec,
    mgr: CronManager = Depends(get_cron_manager),
):
    # server generates id; ignore client-provided spec.id
    job_id = str(uuid.uuid4())
    created = spec.model_copy(update={"id": job_id})
    await mgr.create_or_replace_job(created)
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    await sync_evolution_config_with_cron(workspace)
    return created


@router.put("/jobs/{job_id}", response_model=CronJobSpec)
async def replace_job(
    request: Request,
    job_id: str,
    spec: CronJobSpec,
    mgr: CronManager = Depends(get_cron_manager),
):
    if spec.id != job_id:
        raise HTTPException(status_code=400, detail="job_id mismatch")
    await mgr.create_or_replace_job(spec)
    if job_id == AUTO_EVOLUTION_JOB_ID:
        from ..agent_context import get_agent_for_request

        workspace = await get_agent_for_request(request)
        await sync_evolution_config_with_cron(workspace)
    return spec


@router.delete("/jobs/{job_id}")
async def delete_job(
    request: Request,
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    ok = await mgr.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="job not found")
    if job_id == AUTO_EVOLUTION_JOB_ID:
        from ..agent_context import get_agent_for_request

        workspace = await get_agent_for_request(request)
        await sync_evolution_config_with_cron(workspace)
    return {"deleted": True}


@router.post("/jobs/{job_id}/pause")
async def pause_job(
    request: Request,
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    try:
        if job_id == AUTO_EVOLUTION_JOB_ID:
            await _sync_auto_evolution_enabled_state(
                request,
                mgr,
                job_id=job_id,
                enabled=False,
            )
        else:
            await mgr.pause_job(job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"paused": True}


@router.post("/jobs/{job_id}/resume")
async def resume_job(
    request: Request,
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    try:
        if job_id == AUTO_EVOLUTION_JOB_ID:
            await _sync_auto_evolution_enabled_state(
                request,
                mgr,
                job_id=job_id,
                enabled=True,
            )
        else:
            await mgr.resume_job(job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"resumed": True}


@router.post("/jobs/{job_id}/run")
async def run_job(job_id: str, mgr: CronManager = Depends(get_cron_manager)):
    try:
        await mgr.run_job(job_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="job not found") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"started": True}


@router.get("/jobs/{job_id}/state")
async def get_job_state(
    job_id: str,
    mgr: CronManager = Depends(get_cron_manager),
):
    job = await mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return mgr.get_state(job_id).model_dump(mode="json")
