# -*- coding: utf-8 -*-
"""Tests for recovering agent registrations from existing workspaces."""
import json
from pathlib import Path

from copaw.config import utils as config_utils


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def test_recover_agent_profiles_restores_orphan_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Existing workspaces should be re-registered into config.json."""
    monkeypatch.setattr(config_utils, "WORKING_DIR", tmp_path)

    config_path = tmp_path / "config.json"
    _write_json(
        config_path,
        {
            "agents": {
                "active_agent": "default",
                "profiles": {
                    "default": {
                        "id": "default",
                        "workspace_dir": str(
                            tmp_path / "workspaces" / "default",
                        ),
                    },
                },
            },
        },
    )
    _write_json(
        tmp_path / "workspaces" / "VobMdW" / "agent.json",
        {
            "id": "VobMdW",
            "name": "Cloud",
            "workspace_dir": str(tmp_path / "workspaces" / "VobMdW"),
        },
    )

    recovered = config_utils.recover_agent_profiles(config_path=config_path)

    assert [ref.id for ref in recovered] == ["VobMdW"]
    config = config_utils.load_config(config_path)
    assert "VobMdW" in config.agents.profiles
    assert (
        config.agents.profiles["VobMdW"].workspace_dir
        == str(tmp_path / "workspaces" / "VobMdW")
    )


def test_recover_agent_profiles_ignores_deleted_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Deleted workspaces should not be auto-restored."""
    monkeypatch.setattr(config_utils, "WORKING_DIR", tmp_path)

    config_path = tmp_path / "config.json"
    _write_json(
        config_path,
        {
            "agents": {
                "active_agent": "default",
                "profiles": {
                    "default": {
                        "id": "default",
                        "workspace_dir": str(
                            tmp_path / "workspaces" / "default",
                        ),
                    },
                },
            },
        },
    )
    workspace_dir = tmp_path / "workspaces" / "VobMdW"
    _write_json(
        workspace_dir / "agent.json",
        {
            "id": "VobMdW",
            "name": "Cloud",
            "workspace_dir": str(workspace_dir),
        },
    )
    config_utils.mark_agent_workspace_deleted(workspace_dir)

    recovered = config_utils.recover_agent_profiles(config_path=config_path)

    assert recovered == []
    config = config_utils.load_config(config_path)
    assert "VobMdW" not in config.agents.profiles
