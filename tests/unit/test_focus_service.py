# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sqlite3
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
            self.assertEqual(service.list_tags(), ["OpenAI"])

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

    def test_write_note_normalizes_stringified_tags_without_polluting_focus_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = FocusService(Path(tmp_dir))
            service.replace_tags(["俄乌战争", "台海战争"])

            note = service.write_note(
                title="俄乌战争：能源制裁升级",
                content="出现新的制裁动态。",
                tags='["俄乌战争,能源经济制裁]',
                source="web",
            )

            self.assertEqual(note.tags, ["俄乌战争", "能源经济制裁"])
            self.assertEqual(service.list_tags(), ["俄乌战争", "台海战争"])

    def test_service_repairs_polluted_focus_tags_notes_and_runs_on_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            service = FocusService(workspace)
            db_path = workspace / "focus.sqlite3"

            polluted_tags = [
                "俄乌战争",
                "台海战争",
                "[",
                '"',
                "俄",
                "乌",
                "战",
                "争",
                ",",
                "能",
                "源",
                "经",
                "济",
                "制",
                "裁",
                "]",
            ]
            polluted_note_tags = ['[', '"', "俄", "乌", "战", "争", ",", "能", "源", "经", "济", "制", "裁", "]"]
            polluted_run_tags = [
                "俄乌战争",
                "台海战争",
                "[",
                '"',
                "俄",
                "乌",
                "战",
                "争",
                ",",
                "能",
                "源",
                "经",
                "济",
                "制",
                "裁",
                "]",
            ]

            with sqlite3.connect(db_path) as conn:
                conn.execute("DELETE FROM focus_tags")
                conn.execute("DELETE FROM focus_notes")
                conn.execute("DELETE FROM focus_runs")
                now = datetime.now(timezone.utc).isoformat()
                for position, tag in enumerate(polluted_tags):
                    conn.execute(
                        """
                        INSERT INTO focus_tags (
                            name, normalized_name, position, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (tag, tag.lower(), position, now, now),
                    )
                conn.execute(
                    """
                    INSERT INTO focus_notes (
                        id, title, content, preview_text, fingerprint, source, tags_json,
                        created_at, session_id, run_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "note-1",
                        "俄乌战争：能源制裁升级",
                        "出现新的制裁动态。",
                        "出现新的制裁动态。",
                        "",
                        "web",
                        json.dumps(polluted_note_tags, ensure_ascii=False),
                        now,
                        None,
                        "run-1",
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO focus_runs (
                        id, status, reason, trigger_type, started_at, finished_at,
                        note_count, summary, notification_status, archive_id,
                        tag_snapshot_json, session_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "run-1",
                        "completed",
                        None,
                        "manual",
                        now,
                        now,
                        1,
                        "生成 1 条关注要点",
                        "not_applicable",
                        "run-1",
                        json.dumps(polluted_run_tags, ensure_ascii=False),
                        "focus:run-1",
                    ),
                )
                conn.commit()

            repaired = FocusService(workspace)
            self.assertEqual(repaired.list_tags(), ["俄乌战争", "台海战争"])

            note = repaired.get_note("note-1")
            self.assertIsNotNone(note)
            assert note is not None
            self.assertEqual(note.tags, ["俄乌战争", "能源经济制裁"])

            run = repaired.get_run("run-1")
            self.assertIsNotNone(run)
            assert run is not None
            self.assertEqual(run.tag_snapshot, ["俄乌战争", "台海战争"])
