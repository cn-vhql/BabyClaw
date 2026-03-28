# -*- coding: utf-8 -*-
"""Context variables for agent runtime behavior."""
from contextvars import ContextVar
from pathlib import Path

# Context variable to store the current agent's workspace directory
current_workspace_dir: ContextVar[Path | None] = ContextVar(
    "current_workspace_dir",
    default=None,
)

current_allowed_write_files: ContextVar[tuple[str, ...] | None] = ContextVar(
    "current_allowed_write_files",
    default=None,
)


def get_current_workspace_dir() -> Path | None:
    """Get the current agent's workspace directory from context.

    Returns:
        Path to the current agent's workspace directory, or None if not set.
    """
    return current_workspace_dir.get()


def set_current_workspace_dir(workspace_dir: Path | None) -> None:
    """Set the current agent's workspace directory in context.

    Args:
        workspace_dir: Path to the agent's workspace directory.
    """
    current_workspace_dir.set(workspace_dir)


def get_current_allowed_write_files() -> tuple[str, ...] | None:
    """Get the current write allowlist for file tools."""
    return current_allowed_write_files.get()


def set_current_allowed_write_files(
    allowed_files: tuple[str, ...] | None,
) -> None:
    """Set the write allowlist for file tools."""
    current_allowed_write_files.set(allowed_files)
