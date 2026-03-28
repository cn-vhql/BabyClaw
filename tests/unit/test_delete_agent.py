# -*- coding: utf-8 -*-
"""Tests for agent deletion behavior."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from copaw.app.routers import agents as agents_router
from copaw.config.config import Config, AgentProfileRef


class _DummyManager:
    def __init__(self) -> None:
        self.stopped_agents: list[str] = []

    async def stop_agent(self, agent_id: str) -> bool:
        self.stopped_agents.append(agent_id)
        return True


def _make_request(manager: _DummyManager) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(multi_agent_manager=manager),
        ),
    )


@pytest.mark.asyncio
async def test_delete_agent_removes_workspace_and_resets_active_agent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Deleting the active agent should remove its workspace and reset active_agent."""
    default_dir = tmp_path / "workspaces" / "default"
    cloud_dir = tmp_path / "workspaces" / "cloud"
    default_dir.mkdir(parents=True, exist_ok=True)
    cloud_dir.mkdir(parents=True, exist_ok=True)
    (cloud_dir / "agent.json").write_text('{"id":"cloud"}', encoding="utf-8")
    (cloud_dir / "sessions").mkdir()
    (cloud_dir / "sessions" / "state.json").write_text("{}", encoding="utf-8")

    config = Config()
    config.agents.active_agent = "cloud"
    config.agents.profiles = {
        "default": AgentProfileRef(
            id="default",
            workspace_dir=str(default_dir),
        ),
        "cloud": AgentProfileRef(
            id="cloud",
            workspace_dir=str(cloud_dir),
        ),
    }

    saved_configs: list[Config] = []

    def _save_config(updated_config: Config) -> None:
        saved_configs.append(updated_config.model_copy(deep=True))

    monkeypatch.setattr(
        agents_router,
        "_load_config_with_agent_recovery",
        lambda agent_id=None: config,
    )
    monkeypatch.setattr(agents_router, "save_config", _save_config)

    manager = _DummyManager()
    response = await agents_router.delete_agent(
        "cloud",
        _make_request(manager),
    )

    assert response == {"success": True, "agent_id": "cloud"}
    assert manager.stopped_agents == ["cloud"]
    assert not cloud_dir.exists()
    assert "cloud" not in config.agents.profiles
    assert config.agents.active_agent == "default"
    assert saved_configs[-1].agents.active_agent == "default"
    assert "cloud" not in saved_configs[-1].agents.profiles
