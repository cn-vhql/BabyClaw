# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from ..channels.schema import DEFAULT_CHANNEL

# ---------------------------------------------------------------------------
# APScheduler v3 uses ISO 8601 weekday numbering (0=Mon … 6=Sun) for
# CronTrigger(day_of_week=...), while standard crontab uses 0=Sun … 6=Sat.
# from_crontab() does NOT convert either.  Three-letter English abbreviations
# (mon, tue, …, sun) are unambiguous in both systems, so we normalise the
# 5th cron field to abbreviations at validation time.
# ---------------------------------------------------------------------------

_CRONTAB_NUM_TO_NAME: dict[str, str] = {
    "0": "sun",
    "1": "mon",
    "2": "tue",
    "3": "wed",
    "4": "thu",
    "5": "fri",
    "6": "sat",
    "7": "sun",
}


def _default_evolution_dispatch() -> dict[str, Any]:
    """Return a no-op dispatch payload for evolution cron jobs."""
    return {
        "type": "channel",
        "channel": "",
        "target": {
            "user_id": "",
            "session_id": "",
        },
        "mode": "stream",
        "meta": {},
    }


def _crontab_dow_to_name(field: str) -> str:
    """Convert the day-of-week field from crontab numbers to abbreviations.

    Handles: ``*``, single values, comma-separated lists, and ranges.
    Already-named values (``mon``, ``tue``, …) are passed through unchanged.
    """
    if field == "*":
        return field

    def _convert_token(tok: str) -> str:
        if "/" in tok:
            base, step = tok.rsplit("/", 1)
            return f"{_convert_token(base)}/{step}"
        if "-" in tok:
            parts = tok.split("-", 1)
            return "-".join(_CRONTAB_NUM_TO_NAME.get(p, p) for p in parts)
        return _CRONTAB_NUM_TO_NAME.get(tok, tok)

    return ",".join(_convert_token(t) for t in field.split(","))


class ScheduleSpec(BaseModel):
    type: Literal["cron"] = "cron"
    cron: str = Field(...)
    timezone: str = "UTC"

    @field_validator("cron")
    @classmethod
    def normalize_cron_5_fields(cls, v: str) -> str:
        parts = [p for p in v.split() if p]
        if len(parts) == 5:
            parts[4] = _crontab_dow_to_name(parts[4])
            return " ".join(parts)

        if len(parts) == 4:
            # treat as: hour dom month dow
            hour, dom, month, dow = parts
            return f"0 {hour} {dom} {month} {_crontab_dow_to_name(dow)}"

        if len(parts) == 3:
            # treat as: dom month dow
            dom, month, dow = parts
            return f"0 0 {dom} {month} {_crontab_dow_to_name(dow)}"

        # 6 fields (seconds) or too short: reject
        raise ValueError(
            "cron must have 5 fields "
            "(or 4/3 fields that can be normalized); seconds not supported.",
        )


class DispatchTarget(BaseModel):
    user_id: str
    session_id: str


class DispatchSpec(BaseModel):
    type: Literal["channel"] = "channel"
    channel: str = Field(default=DEFAULT_CHANNEL)
    target: DispatchTarget
    mode: Literal["stream", "final"] = Field(default="stream")
    meta: Dict[str, Any] = Field(default_factory=dict)


class JobRuntimeSpec(BaseModel):
    max_concurrency: int = Field(default=1, ge=1)
    timeout_seconds: int = Field(default=120, ge=1)
    misfire_grace_seconds: int = Field(default=60, ge=0)


class CronJobRequest(BaseModel):
    """Passthrough payload to runner.stream_query(request=...).

    This is aligned with AgentRequest(extra="allow"). We keep it permissive.
    """

    model_config = ConfigDict(extra="allow")

    input: Any
    session_id: Optional[str] = None
    user_id: Optional[str] = None


TaskType = Literal["text", "agent", "evolution"]


class EvolutionJobConfig(BaseModel):
    """Configuration for evolution task type."""

    trigger_type: Literal["cron", "auto"] = "cron"
    timeout_seconds: int = 300


class CronJobSpec(BaseModel):
    id: str
    name: str
    enabled: bool = True

    schedule: ScheduleSpec
    task_type: TaskType = "agent"
    text: Optional[str] = None
    request: Optional[CronJobRequest] = None
    evolution_config: Optional[EvolutionJobConfig] = None
    dispatch: DispatchSpec

    runtime: JobRuntimeSpec = Field(default_factory=JobRuntimeSpec)
    meta: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_evolution_dispatch(cls, data: Any) -> Any:
        if not isinstance(data, dict) or data.get("task_type") != "evolution":
            return data

        normalized = dict(data)
        dispatch = _default_evolution_dispatch()
        raw_dispatch = normalized.get("dispatch")

        if isinstance(raw_dispatch, dict):
            dispatch.update(
                {
                    key: value
                    for key, value in raw_dispatch.items()
                    if key != "target" and value is not None
                }
            )

            raw_target = raw_dispatch.get("target")
            if isinstance(raw_target, dict):
                target = dict(dispatch["target"])
                target.update(
                    {
                        key: value
                        for key, value in raw_target.items()
                        if value is not None
                    }
                )
                dispatch["target"] = target

        normalized["dispatch"] = dispatch
        return normalized

    @model_validator(mode="after")
    def _validate_task_type_fields(self) -> "CronJobSpec":
        if self.task_type == "text":
            if not (self.text and self.text.strip()):
                raise ValueError("task_type is text but text is empty")
        elif self.task_type == "agent":
            if self.request is None:
                raise ValueError("task_type is agent but request is missing")
            # Keep request.user_id and request.session_id in sync with target
            target = self.dispatch.target
            self.request = self.request.model_copy(
                update={
                    "user_id": target.user_id,
                    "session_id": target.session_id,
                }
            )
        elif self.task_type == "evolution":
            if self.evolution_config is None:
                raise ValueError("task_type is evolution but evolution_config is missing")
        return self


class JobsFile(BaseModel):
    version: int = 1
    jobs: list[CronJobSpec] = Field(default_factory=list)


class CronJobState(BaseModel):
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_status: Optional[
        Literal["success", "error", "running", "skipped", "cancelled"]
    ] = None
    last_error: Optional[str] = None


class CronJobView(BaseModel):
    spec: CronJobSpec
    state: CronJobState = Field(default_factory=CronJobState)
