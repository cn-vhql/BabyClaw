# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from copaw.app.focus.models import FocusRunArchive, FocusRunRecord
from copaw.app.focus.service import FocusService


class FocusServiceTests(unittest.TestCase):
    def test_focus_service_persists_tags_notes_runs_and_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = FocusService(Path(tmp_dir))

            tags = service.replace_tags(["OpenAI", "openai", "NVIDIA"])
            self.assertEqual(tags, ["OpenAI", "NVIDIA"])
            self.assertEqual(service.list_tags(), ["OpenAI", "NVIDIA"])

            note = service.write_note(
                title="Model update",
                content="A new API capability was observed.",
                tags=["OpenAI", "Release", "release"],
                source="web",
                session_id="focus:watch:test",
                run_id="run-1",
            )
            duplicate = service.write_note(
                title="Model update",
                content="A new API capability was observed.",
                tags=["OpenAI", "Release"],
                source="web",
                session_id="focus:watch:test",
                run_id="run-1",
            )

            self.assertEqual(note.id, duplicate.id)
            self.assertEqual(note.preview_text, "A new API capability was observed.")
            self.assertEqual(note.tags, ["OpenAI", "Release"])
            self.assertEqual(note.run_id, "run-1")

            notes_page, total = service.list_notes(page=1, page_size=10)
            self.assertEqual(total, 1)
            self.assertEqual(notes_page[0].id, note.id)
            self.assertEqual(notes_page[0].preview_text, note.preview_text)

            run_notes = service.list_notes_by_run("run-1")
            self.assertEqual(len(run_notes), 1)
            self.assertEqual(run_notes[0].id, note.id)

            run, running = service.create_running_run(
                trigger_type="manual",
                tag_snapshot=["OpenAI"],
                session_id="focus:watch:run-1",
            )
            self.assertIsNotNone(run)
            self.assertIsNone(running)

            assert run is not None
            run.status = "completed"
            run.note_count = 1
            run.summary = "生成 1 条关注要点"
            run.finished_at = datetime.now(timezone.utc)
            run.notification_status = "not_applicable"
            run.archive_id = run.id
            service.save_run(run)

            stored_run = service.get_run(run.id)
            self.assertIsNotNone(stored_run)
            assert stored_run is not None
            self.assertEqual(stored_run.status, "completed")
            self.assertEqual(stored_run.note_count, 1)

            runs_page, run_total = service.list_runs(page=1, page_size=10)
            self.assertEqual(run_total, 1)
            self.assertEqual(runs_page[0].id, run.id)

            archive = FocusRunArchive(
                runId=run.id,
                prompt="watch OpenAI",
                fullOutput="done",
                toolExecutionLog=[{"tool": "search"}],
                noteIds=[note.id],
                tagSnapshot=["OpenAI"],
                notificationResult={"status": "not_applicable"},
                errorMessage=None,
                createdAt=datetime.now(timezone.utc),
            )
            service.save_run_archive(archive)

            loaded_archive = service.get_run_archive(run.id)
            self.assertIsNotNone(loaded_archive)
            assert loaded_archive is not None
            self.assertEqual(loaded_archive.run_id, run.id)
            self.assertEqual(loaded_archive.note_ids, [note.id])

            self.assertTrue(service.remove_tag("nvidia"))
            self.assertEqual(service.list_tags(), ["OpenAI", "Release"])

    def test_create_running_run_enforces_single_flight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = FocusService(Path(tmp_dir))
            first, first_running = service.create_running_run(
                trigger_type="manual",
                tag_snapshot=["A"],
                session_id="focus:watch:first",
            )
            self.assertIsNotNone(first)
            self.assertIsNone(first_running)

            second, running = service.create_running_run(
                trigger_type="manual",
                tag_snapshot=["B"],
                session_id="focus:watch:second",
            )
            self.assertIsNone(second)
            self.assertIsNotNone(running)

            assert first is not None
            first.status = "completed"
            first.finished_at = datetime.now(timezone.utc)
            service.save_run(first)

            third, third_running = service.create_running_run(
                trigger_type="scheduled",
                tag_snapshot=["C"],
                session_id="focus:watch:third",
            )
            self.assertIsNotNone(third)
            self.assertIsNone(third_running)
