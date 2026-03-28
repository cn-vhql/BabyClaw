# -*- coding: utf-8 -*-
"""Pydantic models for focus monitoring."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from ...config.config import ActiveHoursConfig

FocusRunStatus = Literal[
    "running",
    "completed",
    "skipped",
    "timed_out",
    "failed",
    "cancelled",
]
FocusTriggerType = Literal["manual", "scheduled"]


class FocusNoteSummary(BaseModel):
    """Lightweight focus note summary used in list responses."""

    id: str
    title: str
    preview_text: str = Field(default="", alias="previewText")
    tags: list[str] = Field(default_factory=list)
    source: str = ""
    created_at: datetime = Field(alias="createdAt")
    run_id: Optional[str] = Field(default=None, alias="runId")

    model_config = {"populate_by_name": True}


class FocusNote(FocusNoteSummary):
    """Complete persisted focus note."""

    content: str
    session_id: Optional[str] = Field(default=None, alias="sessionId")
    fingerprint: Optional[str] = None

    model_config = {"populate_by_name": True}


class FocusRunRecord(BaseModel):
    """Persisted focus run summary."""

    id: str
    status: FocusRunStatus = "running"
    reason: Optional[str] = None
    trigger_type: FocusTriggerType = Field(default="manual", alias="triggerType")
    started_at: datetime = Field(alias="startedAt")
    finished_at: Optional[datetime] = Field(default=None, alias="finishedAt")
    note_count: int = Field(default=0, alias="noteCount")
    summary: str = ""
    notification_status: str = Field(default="pending", alias="notificationStatus")
    archive_id: Optional[str] = Field(default=None, alias="archiveId")
    tag_snapshot: list[str] = Field(default_factory=list, alias="tagSnapshot")
    session_id: Optional[str] = Field(default=None, alias="sessionId")

    model_config = {"populate_by_name": True}


class FocusRunDetail(FocusRunRecord):
    """Detailed focus run with generated note summaries."""

    generated_notes: list[FocusNoteSummary] = Field(
        default_factory=list,
        alias="generatedNotes",
    )

    model_config = {"populate_by_name": True}


class FocusRunArchive(BaseModel):
    """Large run details stored in JSON archives."""

    run_id: str = Field(alias="runId")
    prompt: str = ""
    full_output: str = Field(default="", alias="fullOutput")
    tool_execution_log: list[dict] = Field(
        default_factory=list,
        alias="toolExecutionLog",
    )
    note_ids: list[str] = Field(default_factory=list, alias="noteIds")
    tag_snapshot: list[str] = Field(default_factory=list, alias="tagSnapshot")
    notification_result: dict = Field(default_factory=dict, alias="notificationResult")
    error_message: Optional[str] = Field(default=None, alias="errorMessage")
    created_at: datetime = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class FocusNotesPage(BaseModel):
    """Paginated note list response."""

    items: list[FocusNoteSummary] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = Field(default=10, alias="pageSize")

    model_config = {"populate_by_name": True}


class FocusRunsPage(BaseModel):
    """Paginated run list response."""

    items: list[FocusRunRecord] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = Field(default=10, alias="pageSize")

    model_config = {"populate_by_name": True}


class FocusSettingsResponse(BaseModel):
    """API response for focus settings."""

    enabled: bool = False
    every: str = "6h"
    notification_channel: str = Field(default="last", alias="notificationChannel")
    do_not_disturb: Optional[ActiveHoursConfig] = Field(
        default=None,
        alias="doNotDisturb",
    )
    tags: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class FocusSettingsUpdate(BaseModel):
    """Request body for updating focus settings."""

    enabled: bool = False
    every: str = "6h"
    notification_channel: str = Field(default="last", alias="notificationChannel")
    do_not_disturb: Optional[ActiveHoursConfig] = Field(
        default=None,
        alias="doNotDisturb",
    )
    tags: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "extra": "allow"}
