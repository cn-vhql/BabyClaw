# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from copaw.app.focus.executor import FocusRunExecutor


class Message:
    def __init__(self, *, message_id: str, status: str, content, type=None, role="assistant"):
        self.id = message_id
        self.status = status
        self.content = content
        self.type = type
        self.role = role


class FakeRunner:
    def __init__(self, events):
        self._events = events
        self.session = None

    async def stream_query(self, request):  # noqa: ANN001
        self.request = request
        for event in self._events:
            yield event


class FocusExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_executor_captures_plugin_call_and_output_from_data_payload(self) -> None:
        events = [
            Message(
                message_id="call-1",
                status="completed",
                type="plugin_call",
                content=[
                    {
                        "type": "data",
                        "data": {
                            "id": "tool-call-1",
                            "tool": "web_search",
                            "arguments": {"query": "OpenAI latest"},
                        },
                    }
                ],
            ),
            Message(
                message_id="call-output-1",
                status="completed",
                type="plugin_call_output",
                content=[
                    {
                        "type": "data",
                        "data": {
                            "id": "tool-call-1",
                            "tool": "web_search",
                            "result": {"items": ["result-a", "result-b"]},
                        },
                    }
                ],
            ),
            Message(
                message_id="text-1",
                status="completed",
                content=[{"type": "text", "text": "## 巡检结论\n- 发现新的动态"}],
            ),
        ]

        executor = FocusRunExecutor(workspace=object(), runner=FakeRunner(events), user_id="focus_watch")
        result = await executor.execute(prompt="watch", session_id="focus:test")

        self.assertEqual(len(result.tool_execution_log), 1)
        self.assertEqual(result.tool_execution_log[0]["tool"], "web_search")
        self.assertEqual(
            result.tool_execution_log[0]["args"],
            {"query": "OpenAI latest"},
        )
        self.assertEqual(
            result.tool_execution_log[0]["result"],
            {"items": ["result-a", "result-b"]},
        )
        self.assertIn("## 巡检结论", result.full_output)
        self.assertIn("[工具结果:web_search]", result.full_output)

