# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import unittest
import json
from datetime import datetime
from pathlib import Path

from copaw.app.evolution.executor import EvolutionExecutor
from copaw.app.evolution.models import EvolutionArchive, EvolutionRecord
from copaw.app.evolution.repo.json_repo import JsonEvolutionRepository
from copaw.app.runner.session import sanitize_filename


class Message:
    def __init__(
        self,
        *,
        message_id: str,
        message_type: str,
        content: list[dict] | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.id = message_id
        self.status = "completed"
        self.type = message_type
        self.content = content or []
        self.metadata = metadata


class JsonEvolutionRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_archive_by_evolution_id_returns_saved_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = JsonEvolutionRepository(Path(tmp_dir))
            archive = EvolutionArchive(
                evolution_id="record-1",
                generation=1,
                timestamp=datetime.now(),
                tool_execution_log=[{"tool": "read_file"}],
                structured_records=[
                    {
                        "type": "metadata",
                        "data": {"changed": True},
                    },
                ],
            )

            await repo.save_archive(archive)
            loaded = await repo.get_archive_by_evolution_id("record-1")

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.archive_id, archive.archive_id)
            self.assertEqual(loaded.evolution_id, "record-1")
            self.assertEqual(loaded.structured_records[0]["type"], "metadata")

    async def test_list_records_repairs_tool_count_from_archive_backfill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_dir = Path(tmp_dir)
            repo = JsonEvolutionRepository(workspace_dir)
            record = EvolutionRecord(
                id="record-repair-count",
                generation=5,
                agent_id="default",
                agent_name="Default Agent",
                timestamp=datetime.fromisoformat("2026-03-28T12:00:00"),
                duration_seconds=10,
                tool_calls_count=0,
                tools_used=[],
            )
            archive = EvolutionArchive(
                evolution_id=record.id,
                generation=5,
                timestamp=datetime.fromisoformat("2026-03-28T12:00:11"),
            )

            await repo.save_record(record)
            await repo.save_archive(archive)

            sessions_dir = workspace_dir / "sessions"
            sessions_dir.mkdir(parents=True, exist_ok=True)
            session_file = sessions_dir / (
                f"{sanitize_filename('evolution_system')}_"
                f"{sanitize_filename('evolution:record-repair-count')}.json"
            )
            session_file.write_text(
                json.dumps(
                    {
                        "agent": {
                            "memory": {
                                "content": [
                                    [
                                        [
                                            {
                                                "id": "repair-tool-call",
                                                "role": "assistant",
                                                "type": "plugin_call",
                                                "timestamp": "2026-03-28 12:00:02.000",
                                                "metadata": {},
                                                "content": [
                                                    {
                                                        "type": "tool_use",
                                                        "id": "call-repair",
                                                        "name": "read_file",
                                                        "input": {
                                                            "file_path": "SOUL.md",
                                                        },
                                                    },
                                                ],
                                            },
                                        ],
                                        [],
                                    ],
                                    [
                                        [
                                            {
                                                "id": "repair-tool-result",
                                                "role": "system",
                                                "type": "plugin_call_output",
                                                "timestamp": "2026-03-28 12:00:04.000",
                                                "metadata": {},
                                                "content": [
                                                    {
                                                        "type": "tool_result",
                                                        "id": "call-repair",
                                                        "name": "read_file",
                                                        "output": [
                                                            {
                                                                "type": "text",
                                                                "text": "SOUL content",
                                                            },
                                                        ],
                                                    },
                                                ],
                                            },
                                        ],
                                        [],
                                    ],
                                ],
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            records = await repo.list_records(limit=10)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["tool_calls_count"], 1)
            self.assertEqual(records[0]["tools_used"], ["read_file"])

            repaired = await repo.get_record(record.id)

            self.assertIsNotNone(repaired)
            assert repaired is not None
            self.assertEqual(repaired.tool_calls_count, 1)
            self.assertEqual(repaired.tools_used, ["read_file"])

    async def test_enrich_archive_backfills_from_legacy_evolution_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_dir = Path(tmp_dir)
            repo = JsonEvolutionRepository(workspace_dir)
            record = EvolutionRecord(
                id="record-legacy",
                generation=1,
                agent_id="default",
                agent_name="Default Agent",
                timestamp=datetime.fromisoformat("2026-03-21T20:11:48.922000"),
                duration_seconds=40,
            )
            archive = EvolutionArchive(
                evolution_id=record.id,
                generation=1,
                timestamp=datetime.fromisoformat("2026-03-21T20:12:29.806865"),
            )

            sessions_dir = workspace_dir / "sessions"
            sessions_dir.mkdir(parents=True, exist_ok=True)
            session_file = sessions_dir / (
                f"{sanitize_filename('evolution_system')}_"
                f"{sanitize_filename('evolution:record-legacy')}.json"
            )
            session_file.write_text(
                json.dumps(
                    {
                        "agent": {
                            "memory": {
                                "content": [
                                    [
                                        [
                                            {
                                                "id": "msg-tool-call",
                                                "role": "assistant",
                                                "type": "plugin_call",
                                                "timestamp": "2026-03-21 20:11:52.687",
                                                "metadata": {},
                                                "content": [
                                                    {
                                                        "type": "tool_use",
                                                        "id": "call-1",
                                                        "name": "read_file",
                                                        "input": {
                                                            "file_path": "SOUL.md",
                                                        },
                                                    },
                                                ],
                                            },
                                        ],
                                        [],
                                    ],
                                    [
                                        [
                                            {
                                                "id": "msg-tool-result",
                                                "role": "system",
                                                "type": "plugin_call_output",
                                                "timestamp": "2026-03-21 20:11:54.686",
                                                "metadata": {},
                                                "content": [
                                                    {
                                                        "type": "tool_result",
                                                        "id": "call-1",
                                                        "name": "read_file",
                                                        "output": [
                                                            {
                                                                "type": "text",
                                                                "text": "SOUL content",
                                                            },
                                                        ],
                                                    },
                                                ],
                                            },
                                        ],
                                        [],
                                    ],
                                    [
                                        [
                                            {
                                                "id": "msg-final",
                                                "role": "assistant",
                                                "type": "message",
                                                "timestamp": "2026-03-21 20:12:29.708",
                                                "metadata": {},
                                                "content": [
                                                    {
                                                        "type": "text",
                                                        "text": "done",
                                                    },
                                                ],
                                            },
                                        ],
                                        [],
                                    ],
                                ],
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            enriched = await repo.enrich_archive(archive, record=record)

            self.assertEqual(len(enriched.tool_execution_log), 1)
            self.assertEqual(enriched.tool_execution_log[0]["tool"], "read_file")
            self.assertEqual(
                enriched.tool_execution_log[0]["args"],
                {"file_path": "SOUL.md"},
            )
            self.assertEqual(
                enriched.tool_execution_log[0]["result"],
                "SOUL content",
            )
            self.assertIn("[工具结果:read_file]", enriched.full_output)
            self.assertIn("SOUL content", enriched.full_output)
            self.assertTrue(enriched.full_output.rstrip().endswith("done"))

    async def test_enrich_archive_backfills_from_unified_evolution_session_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_dir = Path(tmp_dir)
            repo = JsonEvolutionRepository(workspace_dir)
            record = EvolutionRecord(
                id="record-window",
                generation=12,
                agent_id="default",
                agent_name="Default Agent",
                timestamp=datetime.fromisoformat("2026-03-27T04:00:00.003423"),
                duration_seconds=20,
            )
            archive = EvolutionArchive(
                evolution_id=record.id,
                generation=12,
                timestamp=datetime.fromisoformat("2026-03-27T04:00:22.000000"),
            )

            sessions_dir = workspace_dir / "sessions"
            sessions_dir.mkdir(parents=True, exist_ok=True)
            session_file = sessions_dir / (
                f"{sanitize_filename('evolution_system')}_"
                f"{sanitize_filename('evolution:default')}.json"
            )
            session_file.write_text(
                json.dumps(
                    {
                        "agent": {
                            "memory": {
                                "content": [
                                    [
                                        [
                                            {
                                                "id": "old-tool-call",
                                                "role": "assistant",
                                                "type": "plugin_call",
                                                "timestamp": "2026-03-27 03:59:00.000",
                                                "metadata": {},
                                                "content": [
                                                    {
                                                        "type": "tool_use",
                                                        "id": "call-old",
                                                        "name": "read_file",
                                                        "input": {"file_path": "OLD.md"},
                                                    },
                                                ],
                                            },
                                        ],
                                        [],
                                    ],
                                    [
                                        [
                                            {
                                                "id": "new-tool-call",
                                                "role": "assistant",
                                                "type": "plugin_call",
                                                "timestamp": "2026-03-27 04:00:05.000",
                                                "metadata": {},
                                                "content": [
                                                    {
                                                        "type": "tool_use",
                                                        "id": "call-new",
                                                        "name": "write_file",
                                                        "input": {"file_path": "EVOLUTION.md"},
                                                    },
                                                ],
                                            },
                                        ],
                                        [],
                                    ],
                                    [
                                        [
                                            {
                                                "id": "new-tool-result",
                                                "role": "system",
                                                "type": "plugin_call_output",
                                                "timestamp": "2026-03-27 04:00:08.000",
                                                "metadata": {},
                                                "content": [
                                                    {
                                                        "type": "tool_result",
                                                        "id": "call-new",
                                                        "name": "write_file",
                                                        "output": [
                                                            {
                                                                "type": "text",
                                                                "text": "Wrote EVOLUTION.md",
                                                            },
                                                        ],
                                                    },
                                                ],
                                            },
                                        ],
                                        [],
                                    ],
                                    [
                                        [
                                            {
                                                "id": "new-final",
                                                "role": "assistant",
                                                "type": "message",
                                                "timestamp": "2026-03-27 04:00:18.000",
                                                "metadata": {},
                                                "content": [
                                                    {
                                                        "type": "text",
                                                        "text": "generation complete",
                                                    },
                                                ],
                                            },
                                        ],
                                        [],
                                    ],
                                ],
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            enriched = await repo.enrich_archive(archive, record=record)

            self.assertEqual(len(enriched.tool_execution_log), 1)
            self.assertEqual(enriched.tool_execution_log[0]["tool"], "write_file")
            self.assertEqual(
                enriched.tool_execution_log[0]["result"],
                "Wrote EVOLUTION.md",
            )
            self.assertIn("[工具结果:write_file]", enriched.full_output)
            self.assertIn("Wrote EVOLUTION.md", enriched.full_output)
            self.assertTrue(
                enriched.full_output.rstrip().endswith("generation complete")
            )

    async def test_enrich_archive_keeps_repeated_same_tool_calls_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_dir = Path(tmp_dir)
            repo = JsonEvolutionRepository(workspace_dir)
            record = EvolutionRecord(
                id="record-repeat-tools",
                generation=3,
                agent_id="default",
                agent_name="Default Agent",
                timestamp=datetime.fromisoformat("2026-03-27T04:00:00"),
                duration_seconds=15,
            )
            archive = EvolutionArchive(
                evolution_id=record.id,
                generation=3,
                timestamp=datetime.fromisoformat("2026-03-27T04:00:16"),
            )

            sessions_dir = workspace_dir / "sessions"
            sessions_dir.mkdir(parents=True, exist_ok=True)
            session_file = sessions_dir / (
                f"{sanitize_filename('evolution_system')}_"
                f"{sanitize_filename('evolution:default')}.json"
            )
            session_file.write_text(
                json.dumps(
                    {
                        "agent": {
                            "memory": {
                                "content": [
                                    [
                                        [
                                            {
                                                "id": "tool-call-1",
                                                "role": "assistant",
                                                "type": "plugin_call",
                                                "timestamp": "2026-03-27 04:00:02.000",
                                                "metadata": {},
                                                "content": [
                                                    {
                                                        "type": "tool_use",
                                                        "id": "call-1",
                                                        "name": "read_file",
                                                        "input": {"file_path": "SOUL.md"},
                                                    },
                                                ],
                                            },
                                        ],
                                        [],
                                    ],
                                    [
                                        [
                                            {
                                                "id": "tool-result-1",
                                                "role": "system",
                                                "type": "plugin_call_output",
                                                "timestamp": "2026-03-27 04:00:03.000",
                                                "metadata": {},
                                                "content": [
                                                    {
                                                        "type": "tool_result",
                                                        "id": "call-1",
                                                        "name": "read_file",
                                                        "output": [
                                                            {
                                                                "type": "text",
                                                                "text": "SOUL content",
                                                            },
                                                        ],
                                                    },
                                                ],
                                            },
                                        ],
                                        [],
                                    ],
                                    [
                                        [
                                            {
                                                "id": "tool-call-2",
                                                "role": "assistant",
                                                "type": "plugin_call",
                                                "timestamp": "2026-03-27 04:00:04.000",
                                                "metadata": {},
                                                "content": [
                                                    {
                                                        "type": "tool_use",
                                                        "id": "call-2",
                                                        "name": "read_file",
                                                        "input": {"file_path": "PROFILE.md"},
                                                    },
                                                ],
                                            },
                                        ],
                                        [],
                                    ],
                                    [
                                        [
                                            {
                                                "id": "tool-result-2",
                                                "role": "system",
                                                "type": "plugin_call_output",
                                                "timestamp": "2026-03-27 04:00:05.000",
                                                "metadata": {},
                                                "content": [
                                                    {
                                                        "type": "tool_result",
                                                        "id": "call-2",
                                                        "name": "read_file",
                                                        "output": [
                                                            {
                                                                "type": "text",
                                                                "text": "PROFILE content",
                                                            },
                                                        ],
                                                    },
                                                ],
                                            },
                                        ],
                                        [],
                                    ],
                                    [
                                        [
                                            {
                                                "id": "final-message",
                                                "role": "assistant",
                                                "type": "message",
                                                "timestamp": "2026-03-27 04:00:10.000",
                                                "metadata": {},
                                                "content": [
                                                    {
                                                        "type": "text",
                                                        "text": "done",
                                                    },
                                                ],
                                            },
                                        ],
                                        [],
                                    ],
                                ],
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            enriched = await repo.enrich_archive(archive, record=record)

            self.assertEqual(len(enriched.tool_execution_log), 2)
            self.assertEqual(
                enriched.tool_execution_log[0]["args"],
                {"file_path": "SOUL.md"},
            )
            self.assertEqual(
                enriched.tool_execution_log[0]["result"],
                "SOUL content",
            )
            self.assertEqual(
                enriched.tool_execution_log[1]["args"],
                {"file_path": "PROFILE.md"},
            )
            self.assertEqual(
                enriched.tool_execution_log[1]["result"],
                "PROFILE content",
            )


class EvolutionExecutorEventTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.executor = EvolutionExecutor(workspace=object(), repo=object())
        self.executor._current_record = EvolutionRecord(
            generation=1,
            agent_id="default",
            agent_name="Default Agent",
            timestamp=datetime.now(),
        )

    async def test_process_event_deduplicates_completed_messages(self) -> None:
        text_message = Message(
            message_id="msg-1",
            message_type="message",
            content=[{"type": "text", "text": "hello world"}],
        )

        await self.executor._process_event(text_message)
        await self.executor._process_event(text_message)

        self.assertEqual(self.executor._full_output, "hello world\n")
        self.assertEqual(self.executor._current_record.output_summary, "hello world")

    async def test_process_event_tracks_tool_calls_and_structured_records(self) -> None:
        tool_call_message = Message(
            message_id="msg-tool-call",
            message_type="plugin_call",
            content=[
                {
                    "type": "data",
                    "data": {
                        "call_id": "call-1",
                        "name": "read_file",
                        "arguments": '{"path": "SOUL.md"}',
                    },
                },
            ],
        )
        tool_result_message = Message(
            message_id="msg-tool-result",
            message_type="plugin_call_output",
            content=[
                {
                    "type": "data",
                    "data": {
                        "call_id": "call-1",
                        "output": '{"ok": true}',
                    },
                },
            ],
        )
        structured_message = Message(
            message_id="msg-structured",
            message_type="message",
            metadata={"structured_output": {"updated_files": ["SOUL.md"]}},
        )

        await self.executor._process_event(tool_call_message)
        await self.executor._process_event(tool_result_message)
        await self.executor._process_event(structured_message)

        self.assertEqual(self.executor._current_record.tool_calls_count, 1)
        self.assertEqual(self.executor._current_record.tools_used, ["read_file"])
        self.assertEqual(len(self.executor._tool_execution_log), 1)
        self.assertEqual(
            self.executor._tool_execution_log[0]["args"],
            {"path": "SOUL.md"},
        )
        self.assertEqual(
            self.executor._tool_execution_log[0]["result"],
            {"ok": True},
        )
        self.assertEqual(len(self.executor._structured_records), 1)
        self.assertEqual(self.executor._structured_records[0]["type"], "structured_output")

    async def test_process_event_keeps_same_tool_name_calls_separate(self) -> None:
        first_tool_call = Message(
            message_id="msg-tool-call-1",
            message_type="plugin_call",
            content=[
                {
                    "type": "data",
                    "data": {
                        "call_id": "call-1",
                        "name": "read_file",
                        "arguments": '{"path": "SOUL.md"}',
                    },
                },
            ],
        )
        first_tool_result = Message(
            message_id="msg-tool-result-1",
            message_type="plugin_call_output",
            content=[
                {
                    "type": "data",
                    "data": {
                        "call_id": "call-1",
                        "name": "read_file",
                        "output": '{"content": "SOUL"}',
                    },
                },
            ],
        )
        second_tool_call = Message(
            message_id="msg-tool-call-2",
            message_type="plugin_call",
            content=[
                {
                    "type": "data",
                    "data": {
                        "call_id": "call-2",
                        "name": "read_file",
                        "arguments": '{"path": "PROFILE.md"}',
                    },
                },
            ],
        )
        second_tool_result = Message(
            message_id="msg-tool-result-2",
            message_type="plugin_call_output",
            content=[
                {
                    "type": "data",
                    "data": {
                        "call_id": "call-2",
                        "name": "read_file",
                        "output": '{"content": "PROFILE"}',
                    },
                },
            ],
        )

        await self.executor._process_event(first_tool_call)
        await self.executor._process_event(first_tool_result)
        await self.executor._process_event(second_tool_call)
        await self.executor._process_event(second_tool_result)

        self.assertEqual(self.executor._current_record.tool_calls_count, 2)
        self.assertEqual(len(self.executor._tool_execution_log), 2)
        self.assertEqual(
            self.executor._tool_execution_log[0]["args"],
            {"path": "SOUL.md"},
        )
        self.assertEqual(
            self.executor._tool_execution_log[0]["result"],
            {"content": "SOUL"},
        )
        self.assertEqual(
            self.executor._tool_execution_log[1]["args"],
            {"path": "PROFILE.md"},
        )
        self.assertEqual(
            self.executor._tool_execution_log[1]["result"],
            {"content": "PROFILE"},
        )
        self.assertIn("[工具结果:read_file]", self.executor._full_output)
