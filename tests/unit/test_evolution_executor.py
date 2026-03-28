# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from copaw.agents.tools.file_io import write_file
from copaw.app.evolution.models import (
    CORE_EVOLUTION_FILES,
    EvolutionArchive,
    EvolutionRecord,
)
from copaw.app.evolution.repo.json_repo import JsonEvolutionRepository
from copaw.config.context import (
    set_current_allowed_write_files,
    set_current_workspace_dir,
)


class JsonEvolutionRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_archive_keeps_index_lightweight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_dir = Path(tmp_dir)
            repo = JsonEvolutionRepository(workspace_dir)

            record = EvolutionRecord(
                id="record-1",
                generation=1,
                agent_id="default",
                agent_name="Default Agent",
                timestamp=datetime.fromisoformat("2026-03-28T12:00:00"),
                trigger_type="manual",
                status="success",
                is_active=True,
                archive_id="record-1",
                output_summary="更新了 SOUL.md",
            )
            await repo.save_record(record)

            archive = EvolutionArchive(
                archive_id="record-1",
                evolution_id="record-1",
                generation=1,
                timestamp=datetime.fromisoformat("2026-03-28T12:01:00"),
                before_files={"SOUL.md": "old soul"},
                after_files={"SOUL.md": "new soul"},
                changed_files=["SOUL.md"],
                tool_execution_log=[{"tool": "read_file"}],
                full_output="done",
            )
            await repo.save_archive(archive)

            index_content = (workspace_dir / "evolution.json").read_text(encoding="utf-8")
            self.assertIn('"generation_counter": 0', index_content)
            self.assertNotIn("before_files", index_content)
            self.assertNotIn("after_files", index_content)
            self.assertIn('"archive_id": "record-1"', index_content)

            loaded_archive = await repo.get_archive("record-1")
            self.assertIsNotNone(loaded_archive)
            assert loaded_archive is not None
            self.assertEqual(loaded_archive.before_files["SOUL.md"], "old soul")
            self.assertEqual(loaded_archive.after_files["SOUL.md"], "new soul")

    async def test_cancel_running_record_marks_status_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = JsonEvolutionRepository(Path(tmp_dir))
            record, running = await repo.create_running_record(
                agent_id="default",
                agent_name="Default Agent",
                trigger_type="manual",
            )

            self.assertIsNone(running)
            assert record is not None

            task = asyncio.create_task(asyncio.sleep(60))
            repo.register_task(record.id, task)

            cancelled = await repo.cancel_running_record(record.id)
            self.assertIsNotNone(cancelled)
            assert cancelled is not None
            self.assertEqual(cancelled.status, "cancelled")

    async def test_rollback_restores_previous_archive_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_dir = Path(tmp_dir)
            repo = JsonEvolutionRepository(workspace_dir)

            previous = EvolutionRecord(
                id="gen-1",
                generation=1,
                agent_id="default",
                agent_name="Default Agent",
                timestamp=datetime.fromisoformat("2026-03-28T10:00:00"),
                trigger_type="manual",
                status="success",
                is_active=False,
                archive_id="gen-1",
                output_summary="gen1",
            )
            latest = EvolutionRecord(
                id="gen-2",
                generation=2,
                agent_id="default",
                agent_name="Default Agent",
                timestamp=datetime.fromisoformat("2026-03-28T11:00:00"),
                trigger_type="manual",
                status="success",
                is_active=True,
                archive_id="gen-2",
                output_summary="gen2",
            )
            await repo.save_record(previous)
            await repo.save_record(latest)

            await repo.save_archive(
                EvolutionArchive(
                    archive_id="gen-1",
                    evolution_id="gen-1",
                    generation=1,
                    timestamp=datetime.fromisoformat("2026-03-28T10:01:00"),
                    before_files={},
                    after_files={filename: f"{filename}-v1" for filename in CORE_EVOLUTION_FILES},
                    changed_files=list(CORE_EVOLUTION_FILES),
                )
            )
            await repo.save_archive(
                EvolutionArchive(
                    archive_id="gen-2",
                    evolution_id="gen-2",
                    generation=2,
                    timestamp=datetime.fromisoformat("2026-03-28T11:01:00"),
                    before_files={},
                    after_files={filename: f"{filename}-v2" for filename in CORE_EVOLUTION_FILES},
                    changed_files=list(CORE_EVOLUTION_FILES),
                )
            )

            for filename in CORE_EVOLUTION_FILES:
                (workspace_dir / filename).write_text(f"{filename}-current", encoding="utf-8")

            reverted, active = await repo.rollback_to_previous("gen-2")

            self.assertEqual(reverted.status, "reverted")
            self.assertEqual(reverted.reverted_to_record_id, "gen-1")
            self.assertTrue(active.is_active)
            self.assertEqual(active.id, "gen-1")

            for filename in CORE_EVOLUTION_FILES:
                self.assertEqual(
                    (workspace_dir / filename).read_text(encoding="utf-8"),
                    f"{filename}-v1",
                )


class EvolutionFileGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_write_file_only_allows_core_files_in_evolution_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_dir = Path(tmp_dir)
            set_current_workspace_dir(workspace_dir)
            set_current_allowed_write_files(CORE_EVOLUTION_FILES)

            allowed = await write_file("SOUL.md", "allowed")
            denied = await write_file("notes.txt", "denied")

            self.assertTrue((workspace_dir / "SOUL.md").exists())
            self.assertFalse((workspace_dir / "notes.txt").exists())
            self.assertIn("Wrote", allowed.content[0]["text"])
            self.assertIn("can only modify", denied.content[0]["text"])

            set_current_allowed_write_files(None)
