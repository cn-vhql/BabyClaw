# -*- coding: utf-8 -*-
"""Data models for the evolution system."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from shortuuid import ShortUUID

# Generate short UUIDs
_uuid = ShortUUID()


class EvolutionConfig(BaseModel):
    """Evolution configuration."""

    enabled: bool = False
    auto_evolution: bool = False
    max_generations: int | None = None  # None or 0 means unlimited
    archive_enabled: bool = True
    # Manual archive management, no max_archives limit


class EvolutionRecord(BaseModel):
    """Single evolution record."""

    id: str = Field(default_factory=lambda: _uuid.uuid())
    generation: int
    agent_id: str
    agent_name: str
    timestamp: datetime
    trigger_type: str = "manual"  # manual, cron, auto

    # Snapshots before and after evolution
    soul_before: Optional[str] = None
    soul_after: Optional[str] = None
    profile_before: Optional[str] = None
    profile_after: Optional[str] = None
    plan_before: Optional[str] = None
    plan_after: Optional[str] = None

    # Execution result
    status: str = "running"  # running, success, failed, cancelled
    error_message: Optional[str] = None

    # Tool usage records
    tool_calls_count: int = 0
    tools_used: list[str] = Field(default_factory=list)

    # Output summary
    output_summary: str = ""

    # Metadata
    duration_seconds: Optional[float] = None
    tokens_used: Optional[int] = None


class EvolutionArchive(BaseModel):
    """Evolution archive (complete snapshot)."""

    archive_id: str = Field(default_factory=lambda: _uuid.uuid())
    evolution_id: str
    generation: int
    timestamp: datetime

    # File snapshots
    files: dict[str, str] = Field(default_factory=dict)

    # Tool execution log
    tool_execution_log: list[dict] = Field(default_factory=list)

    # Full output
    full_output: str = ""

    # Memory snapshot
    memory_snapshot: Optional[dict] = None


class EvolutionRunRequest(BaseModel):
    """Request to execute evolution."""

    trigger_type: str = "manual"  # manual, cron, auto
    custom_prompt: Optional[str] = None  # Override SOUL.md
    max_iterations: int = 10
    timeout_seconds: int = 300
