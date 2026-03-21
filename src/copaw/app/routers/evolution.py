# -*- coding: utf-8 -*-
"""API routes for evolution management."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Request

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

    return evolution_config.model_dump(mode="json")


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
        raise HTTPException(status_code=404, detail="Archive not found")
    return archive.model_dump(mode="json")


@router.post("/run")
async def run_evolution(
    request: Request,
    req: EvolutionRunRequest,
) -> dict:
    """Manually trigger evolution."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)

    executor = EvolutionExecutor(
        workspace=workspace,
        repo=workspace.evolution_repo,
    )

    # Execute evolution
    record = await executor.execute(req)
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
