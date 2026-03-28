# -*- coding: utf-8 -*-
"""Runtime helpers for scheduled focus monitoring."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True)
class FocusRunContext:
    """Context propagated to focus note tools during a scheduled run."""

    run_id: str | None = None
    session_id: str | None = None
    origin: str = "manual"


_current_focus_run: ContextVar[FocusRunContext | None] = ContextVar(
    "current_focus_run",
    default=None,
)


def set_focus_run_context(ctx: FocusRunContext) -> Token:
    """Set the current focus run context."""
    return _current_focus_run.set(ctx)


def reset_focus_run_context(token: Token) -> None:
    """Reset the current focus run context."""
    _current_focus_run.reset(token)


def get_focus_run_context() -> FocusRunContext | None:
    """Get the current focus run context."""
    return _current_focus_run.get()
