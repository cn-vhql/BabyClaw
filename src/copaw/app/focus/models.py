# -*- coding: utf-8 -*-
"""Pydantic models for focus monitoring."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from ...config.config import ActiveHoursConfig


class FocusNote(BaseModel):
    """A persisted focus note written by the agent."""

    id: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    source: str = ""
    created_at: datetime = Field(alias="createdAt")
    session_id: Optional[str] = Field(default=None, alias="sessionId")
    run_id: Optional[str] = Field(default=None, alias="runId")

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


class FocusRunResponse(BaseModel):
    """API response for a manually triggered focus run."""

    status: str = "completed"
    reason: Optional[str] = None
    note_count: int = Field(default=0, alias="noteCount")
    run_id: Optional[str] = Field(default=None, alias="runId")

    model_config = {"populate_by_name": True}
