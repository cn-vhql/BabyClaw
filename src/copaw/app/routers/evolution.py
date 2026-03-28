# -*- coding: utf-8 -*-
"""API routes for evolution management."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from ...config.config import save_agent_config
from ..evolution.models import EvolutionArchive, EvolutionRecord, EvolutionRunRequest
from ..evolution.executor import EvolutionExecutor

router = APIRouter(prefix="/evolution", tags=["evolution"])


@router.get("/config")
async def get_evolution_config(request: Request) -> dict:
    """Get evolution configuration."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    return workspace.config.evolution.model_dump(mode="json")


@router.put("/config")
async def update_evolution_config(
    request: Request,
    config: dict,
) -> dict:
    """Update evolution configuration."""
    from ..agent_context import get_agent_for_request
    from ...config.evolution import EvolutionConfig

    workspace = await get_agent_for_request(request)
    agent_id = workspace.agent_id

    # Parse and validate config
    evolution_config = EvolutionConfig(**config)
    workspace.config.evolution = evolution_config
    save_agent_config(agent_id, workspace.config)

    # Auto-create/delete default evolution cron job when auto_evolution changes
    cron_manager = workspace.cron_manager
    if cron_manager:
        await _sync_evolution_cron_job(
            workspace=workspace,
            enabled=evolution_config.auto_evolution,
        )

    return evolution_config.model_dump(mode="json")


async def _sync_evolution_cron_job(*, workspace, enabled: bool) -> None:
    """Create or delete the default evolution cron job.

    Args:
        workspace: Workspace instance
        enabled: Whether to create (True) or delete (False) the job
    """
    from ..crons.models import CronJobSpec, ScheduleSpec, EvolutionJobConfig

    cron_repo = workspace.cron_manager._repo if workspace.cron_manager else None
    if not cron_repo:
        return

    job_id = "_auto_evolution_daily"

    if enabled:
        # Create default evolution cron job at 12:00 daily
        job_spec = CronJobSpec(
            id=job_id,
            name="每日自动进化（12:00）",
            enabled=True,
            schedule=ScheduleSpec(
                type="cron",
                cron="0 12 * * *",  # Daily at 12:00
                timezone="Asia/Shanghai",
            ),
            task_type="evolution",
            evolution_config=EvolutionJobConfig(
                trigger_type="cron",
                max_iterations=10,
                timeout_seconds=300,
            ),
            # Evolution tasks don't use dispatch
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
    else:
        # Delete the auto evolution job if exists
        existing_job = await cron_repo.get_job(job_id)
        if existing_job and existing_job.id.startswith("_auto_"):
            await cron_repo.delete_job(job_id)



@router.get("/records")
async def list_evolution_records(
    request: Request,
    limit: int = 50,
) -> List[dict]:
    """List evolution records."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    repo = workspace.evolution_repo
    records = await repo.list_records(limit=limit)
    return records


@router.get("/records/{record_id}")
async def get_evolution_record(
    record_id: str,
    request: Request,
) -> dict:
    """Get evolution record details."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    repo = workspace.evolution_repo
    record = await repo.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record.model_dump(mode="json")


@router.get("/records/{record_id}/archive")
async def get_evolution_archive_by_record(
    record_id: str,
    request: Request,
) -> dict:
    """Get evolution archive by evolution record ID."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    repo = workspace.evolution_repo
    record = await repo.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    archive = await repo.get_archive_by_evolution_id(record_id)
    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found")
    archive = await repo.enrich_archive(archive, record=record)
    return archive.model_dump(mode="json")


@router.get("/archives/{archive_id}")
async def get_evolution_archive(
    archive_id: str,
    request: Request,
) -> dict:
    """Get evolution archive details."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    repo = workspace.evolution_repo
    archive = await repo.get_archive(archive_id)
    if not archive:
        archive = await repo.get_archive_by_evolution_id(archive_id)
    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found")
    archive = await repo.enrich_archive(archive)
    return archive.model_dump(mode="json")


@router.post("/run")
async def run_evolution(
    request: Request,
    req: EvolutionRunRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Manually trigger evolution (runs in background)."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    repo = workspace.evolution_repo

    # Get current generation for the new record
    generation = await repo.get_current_generation()
    next_generation = generation + 1

    # Check max_generations limit
    max_gen = workspace.config.evolution.max_generations
    if max_gen is not None and max_gen > 0 and next_generation > max_gen:
        # Return a failed record immediately
        from datetime import datetime

        record = EvolutionRecord(
            generation=next_generation,
            agent_id=workspace.agent_id,
            agent_name=workspace.config.name,
            timestamp=datetime.now(),
            trigger_type=req.trigger_type,
            status="failed",
            error_message=f"已达到最大代数限制 ({max_gen})",
        )
        await repo.save_record(record)
        return record.model_dump(mode="json")

    # Create a running record immediately
    from datetime import datetime

    record = EvolutionRecord(
        generation=next_generation,
        agent_id=workspace.agent_id,
        agent_name=workspace.config.name,
        timestamp=datetime.now(),
        trigger_type=req.trigger_type,
        status="running",
    )

    # Save the running record
    await repo.save_record(record)

    # Run evolution in background
    async def run_evolution_background():
        try:
            executor = EvolutionExecutor(
                workspace=workspace,
                repo=repo,
            )
            # Pass the existing record so executor updates it instead of creating a new one
            await executor.execute_with_record(req, record)
        except Exception as e:
            import logging

            logging.getLogger(__name__).error(
                f"Background evolution failed: {e}", exc_info=True
            )

    background_tasks.add_task(run_evolution_background)

    # Return immediately with the record
    return record.model_dump(mode="json")


@router.get("/archives/{archive_id}/files/{filename}")
async def get_archive_file(
    archive_id: str,
    filename: str,
    request: Request,
) -> dict:
    """Get file content from archive."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    repo = workspace.evolution_repo
    content = await repo.get_archive_file(archive_id, filename)

    if content is None:
        raise HTTPException(status_code=404, detail="File not found")

    return {"filename": filename, "content": content}


@router.delete("/records/{record_id}")
async def delete_evolution_record(
    record_id: str,
    request: Request,
) -> dict:
    """Delete a failed or running evolution record."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    repo = workspace.evolution_repo

    # Check if record exists
    record = await repo.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # Allow deleting failed and running records
    if record.status not in ["failed", "running"]:
        raise HTTPException(
            status_code=400,
            detail=f"Can only delete failed or running records, current status: {record.status}"
        )

    # Delete the record
    success = await repo.delete_record(record_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete record")

    return {"message": "Record deleted successfully"}
