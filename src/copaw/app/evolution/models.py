# -*- coding: utf-8 -*-
"""Data models for the evolution system."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field
from shortuuid import ShortUUID

_uuid = ShortUUID()

CORE_EVOLUTION_FILES: tuple[str, ...] = (
    "SOUL.md",
    "PROFILE.md",
    "PLAN.md",
    "EVOLUTION.md",
)

EvolutionTriggerType = Literal["manual", "cron", "auto"]
EvolutionStatus = Literal[
    "running",
    "success",
    "failed",
    "cancelled",
    "reverted",
]


class EvolutionConfig(BaseModel):
    """Evolution configuration."""

    enabled: bool = False
    auto_evolution: bool = False
    max_generations: int | None = None
    archive_enabled: bool = True


class EvolutionRecord(BaseModel):
    """Lightweight evolution record used by list/detail APIs."""

    id: str = Field(default_factory=lambda: _uuid.uuid())
    generation: int
    agent_id: str
    agent_name: str
    timestamp: datetime
    trigger_type: EvolutionTriggerType = "manual"
    status: EvolutionStatus = "running"
    is_active: bool = False
    archive_id: Optional[str] = None
    reverted_to_record_id: Optional[str] = None
    error_message: Optional[str] = None
    tool_calls_count: int = 0
    tools_used: list[str] = Field(default_factory=list)
    output_summary: str = ""
    duration_seconds: Optional[float] = None
    tokens_used: Optional[int] = None


class EvolutionArchiveMeta(BaseModel):
    """Archive metadata saved to meta.json."""

    archive_id: str
    evolution_id: str
    generation: int
    timestamp: datetime
    changed_files: list[str] = Field(default_factory=list)
    tool_execution_log: list[dict] = Field(default_factory=list)
    structured_records: list[dict] = Field(default_factory=list)
    full_output: str = ""
    memory_snapshot: Optional[dict] = None
    reverted_to_record_id: Optional[str] = None


class EvolutionArchive(BaseModel):
    """Evolution archive returned by the API."""

    archive_id: str
    evolution_id: str
    generation: int
    timestamp: datetime
    before_files: dict[str, str] = Field(default_factory=dict)
    after_files: dict[str, str] = Field(default_factory=dict)
    changed_files: list[str] = Field(default_factory=list)
    tool_execution_log: list[dict] = Field(default_factory=list)
    structured_records: list[dict] = Field(default_factory=list)
    full_output: str = ""
    memory_snapshot: Optional[dict] = None
    reverted_to_record_id: Optional[str] = None


class EvolutionIndexFile(BaseModel):
    """On-disk JSON index for evolution records."""

    version: int = 2
    generation_counter: int = 0
    active_record_id: Optional[str] = None
    running_record_id: Optional[str] = None
    records: list[EvolutionRecord] = Field(default_factory=list)


class EvolutionRunRequest(BaseModel):
    """Request to execute evolution."""

    trigger_type: EvolutionTriggerType = "manual"
    custom_prompt: Optional[str] = None
    timeout_seconds: int = 300


class EvolutionRollbackResult(BaseModel):
    """Rollback response payload."""

    active_record_id: str
    reverted_record: EvolutionRecord
    active_record: EvolutionRecord
