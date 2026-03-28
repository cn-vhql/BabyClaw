# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from copaw.app.focus.service import FocusService


class FocusServiceTests(unittest.TestCase):
    def test_focus_service_persists_tags_and_notes(self) -> None:
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
                session_id="focus:watch",
                run_id="run-1",
            )

            self.assertEqual(note.title, "Model update")
            self.assertEqual(note.tags, ["OpenAI", "Release"])
            self.assertEqual(note.source, "web")
            self.assertEqual(note.session_id, "focus:watch")
            self.assertEqual(note.run_id, "run-1")

            all_tags = service.list_tags()
            self.assertEqual(all_tags, ["OpenAI", "NVIDIA", "Release"])

            notes = service.list_notes(limit=10)
            self.assertEqual(len(notes), 1)
            self.assertEqual(notes[0].id, note.id)

            run_notes = service.list_notes_by_run("run-1")
            self.assertEqual(len(run_notes), 1)
            self.assertEqual(run_notes[0].id, note.id)

            self.assertTrue(service.remove_tag("nvidia"))
            self.assertEqual(service.list_tags(), ["OpenAI", "Release"])
