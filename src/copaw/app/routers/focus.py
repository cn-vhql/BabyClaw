# -*- coding: utf-8 -*-
"""API routes for the focus monitoring feature."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query, Request

from ...config.config import FocusConfig, save_agent_config
from ..focus.models import (
    FocusNote,
    FocusNoteSummary,
    FocusNotesPage,
    FocusRunArchive,
    FocusRunDetail,
    FocusRunRecord,
    FocusRunsPage,
    FocusSettingsResponse,
    FocusSettingsUpdate,
)
from ..focus.scheduler import start_focus_run

router = APIRouter(prefix="/focus", tags=["focus"])


def _to_note_summary(note: FocusNote) -> FocusNoteSummary:
    return FocusNoteSummary(
        id=note.id,
        title=note.title,
        previewText=note.preview_text,
        tags=note.tags,
        source=note.source,
        createdAt=note.created_at,
        runId=note.run_id,
    )


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


@router.get("/notes", response_model=FocusNotesPage)
async def list_focus_notes(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    q: str | None = Query(default=None),
) -> FocusNotesPage:
    """List paginated focus note summaries for the active agent."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    if workspace.focus_service is None:
        raise HTTPException(status_code=500, detail="FocusService not initialized")

    items, total = workspace.focus_service.list_notes(
        page=page,
        page_size=page_size,
        query=q,
    )
    return FocusNotesPage(items=items, total=total, page=page, pageSize=page_size)


@router.get("/notes/{note_id}", response_model=FocusNote)
async def get_focus_note(
    request: Request,
    note_id: str,
) -> FocusNote:
    """Get one complete focus note."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    if workspace.focus_service is None:
        raise HTTPException(status_code=500, detail="FocusService not initialized")

    note = workspace.focus_service.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Focus note not found")
    return note


@router.get("/runs", response_model=FocusRunsPage)
async def list_focus_runs(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    status: str | None = Query(default=None),
) -> FocusRunsPage:
    """List paginated focus run summaries for the active agent."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    if workspace.focus_service is None:
        raise HTTPException(status_code=500, detail="FocusService not initialized")

    items, total = workspace.focus_service.list_runs(
        page=page,
        page_size=page_size,
        status=status,
    )
    return FocusRunsPage(items=items, total=total, page=page, pageSize=page_size)


@router.get("/runs/{run_id}", response_model=FocusRunDetail)
async def get_focus_run(
    request: Request,
    run_id: str,
) -> FocusRunDetail:
    """Get one focus run detail."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    if workspace.focus_service is None:
        raise HTTPException(status_code=500, detail="FocusService not initialized")

    run = workspace.focus_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Focus run not found")

    notes = workspace.focus_service.list_notes_by_run(run_id)
    return FocusRunDetail(
        **run.model_dump(mode="json"),
        generatedNotes=[_to_note_summary(note) for note in notes],
    )


@router.get("/runs/{run_id}/archive", response_model=FocusRunArchive)
async def get_focus_run_archive(
    request: Request,
    run_id: str,
) -> FocusRunArchive:
    """Get JSON archive details for one focus run."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    if workspace.focus_service is None:
        raise HTTPException(status_code=500, detail="FocusService not initialized")

    archive = workspace.focus_service.get_run_archive(run_id)
    if archive is None:
        raise HTTPException(status_code=404, detail="Focus run archive not found")
    return archive


@router.post("/run", response_model=FocusRunRecord)
async def run_focus_now(request: Request) -> FocusRunRecord:
    """Trigger one immediate focus-monitoring cycle for the active agent."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    if workspace.focus_service is None:
        raise HTTPException(status_code=500, detail="FocusService not initialized")
    if workspace.runner is None:
        raise HTTPException(status_code=500, detail="Runner not initialized")

    run_record, running = await start_focus_run(
        runner=workspace.runner,
        channel_manager=workspace.channel_manager,
        workspace=workspace,
        agent_id=workspace.agent_id,
        trigger="manual",
    )
    if run_record is None:
        raise HTTPException(
            status_code=409,
            detail=f"Focus run is already running: {running.id if running else 'unknown'}",
        )
    return run_record


@router.post("/runs/{run_id}/cancel", response_model=FocusRunRecord)
async def cancel_focus_run(
    request: Request,
    run_id: str,
) -> FocusRunRecord:
    """Cancel one running focus-monitoring cycle."""
    from ..agent_context import get_agent_for_request

    workspace = await get_agent_for_request(request)
    if workspace.focus_service is None:
        raise HTTPException(status_code=500, detail="FocusService not initialized")

    run = workspace.focus_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Focus run not found")
    if run.status != "running":
        raise HTTPException(status_code=400, detail="Only running focus runs can be cancelled")

    cancelled = await workspace.focus_service.cancel_running_run(run_id)
    if cancelled is None:
        raise HTTPException(status_code=500, detail="Failed to cancel focus run")
    return cancelled
