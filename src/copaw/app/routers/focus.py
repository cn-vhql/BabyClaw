# -*- coding: utf-8 -*-
"""API routes for the focus monitoring feature."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query, Request

from ...config.config import FocusConfig, save_agent_config
from ..focus.models import (
    FocusRunResponse,
    FocusSettingsResponse,
    FocusSettingsUpdate,
)
from ..focus.scheduler import run_focus_once

router = APIRouter(prefix="/focus", tags=["focus"])


@router.get("/settings", response_model=FocusSettingsResponse)
async def get_focus_settings(request: Request) -> FocusSettingsResponse:
    """Get current focus settings for the active agent."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    focus = workspace.config.focus or FocusConfig()
    tags = workspace.focus_service.list_tags() if workspace.focus_service else []
    return FocusSettingsResponse(
        enabled=focus.enabled,
        every=focus.every,
        notificationChannel=focus.notification_channel,
        doNotDisturb=focus.do_not_disturb,
        tags=tags,
    )


@router.put("/settings", response_model=FocusSettingsResponse)
async def put_focus_settings(
    request: Request,
    body: FocusSettingsUpdate,
) -> FocusSettingsResponse:
    """Update focus settings and reschedule the watcher."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    if workspace.focus_service is None:
        raise HTTPException(status_code=500, detail="FocusService not initialized")

    focus = FocusConfig(
        enabled=body.enabled,
        every=body.every,
        notification_channel=body.notification_channel,
        do_not_disturb=body.do_not_disturb,
    )
    workspace.config.focus = focus
    save_agent_config(workspace.agent_id, workspace.config)
    tags = workspace.focus_service.replace_tags(body.tags)

    async def reschedule_in_background() -> None:
        try:
            if workspace.cron_manager is not None:
                await workspace.cron_manager.reschedule_focus()
        except Exception as exc:  # pylint: disable=broad-except
            import logging

            logging.getLogger(__name__).warning(
                "Background focus reschedule failed: %s",
                exc,
            )

    asyncio.create_task(reschedule_in_background())

    return FocusSettingsResponse(
        enabled=focus.enabled,
        every=focus.every,
        notificationChannel=focus.notification_channel,
        doNotDisturb=focus.do_not_disturb,
        tags=tags,
    )


@router.get("/notes")
async def list_focus_notes(
    request: Request,
    limit: int = Query(default=200, ge=1, le=500),
) -> dict:
    """List focus notes for the active agent."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    if workspace.focus_service is None:
        raise HTTPException(status_code=500, detail="FocusService not initialized")

    notes = workspace.focus_service.list_notes(limit=limit)
    return {"notes": [note.model_dump(mode="json", by_alias=True) for note in notes]}


@router.post("/run", response_model=FocusRunResponse)
async def run_focus_now(request: Request) -> FocusRunResponse:
    """Trigger one immediate focus-monitoring cycle for the active agent."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    if workspace.focus_service is None:
        raise HTTPException(status_code=500, detail="FocusService not initialized")

    result = await run_focus_once(
        runner=workspace.runner,
        channel_manager=workspace.channel_manager,
        workspace=workspace,
        agent_id=workspace.agent_id,
        trigger="manual",
    )
    return FocusRunResponse(
        status=result.status,
        reason=result.reason,
        noteCount=result.note_count,
        runId=result.run_id,
    )
