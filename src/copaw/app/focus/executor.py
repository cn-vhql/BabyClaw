# -*- coding: utf-8 -*-
"""Execution helpers for focus monitoring runs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FocusExecutionResult:
    """Captured runtime details for one focus run."""

    full_output: str
    tool_execution_log: list[dict]


class FocusRunExecutor:
    """Run one focus watch cycle and capture output details."""

    def __init__(self, workspace, *, runner, user_id: str) -> None:
        self.workspace = workspace
        self.runner = runner
        self.user_id = user_id
        self._full_output = ""
        self._tool_execution_log: list[dict] = []
        self._processed_message_ids: set[str] = set()

    async def execute(
        self,
        *,
        prompt: str,
        session_id: str,
    ) -> FocusExecutionResult:
        request = {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                },
            ],
            "session_id": session_id,
            "user_id": self.user_id,
            "channel": "console",
        }

        try:
            async for event in self.runner.stream_query(request):
                await self._process_event(event)
        finally:
            self._cleanup_session_file(session_id)

        return FocusExecutionResult(
            full_output=self._full_output.strip(),
            tool_execution_log=self._tool_execution_log,
        )

    async def _process_event(self, event: Any) -> None:
        if type(event).__name__ != "Message":
            return
        if getattr(event, "status", None) != "completed":
            return

        message_id = getattr(event, "id", None)
        if message_id and message_id in self._processed_message_ids:
            return
        if message_id:
            self._processed_message_ids.add(message_id)

        self._process_message(event)

    def _process_message(self, message: Any) -> None:
        message_type = self._normalize_message_type(getattr(message, "type", None))
        role = getattr(message, "role", None)

        content = getattr(message, "content", None)
        if not isinstance(content, list):
            return

        for block in content:
            block_dict = self._serialize_value(block)
            if not isinstance(block_dict, dict):
                continue

            self._process_block_dict(
                block_dict,
                message_type=message_type,
                role=role,
            )

    def _process_block_dict(
        self,
        block_dict: dict[str, Any],
        *,
        message_type: str | None = None,
        role: str | None = None,
    ) -> None:
        block_type = block_dict.get("type")
        if block_type == "data":
            self._process_data_payload(
                block_dict.get("data"),
                message_type=message_type,
            )
            return

        if block_type == "tool_use":
            self._append_tool_call(
                tool_name=block_dict.get("name", ""),
                tool_input=block_dict.get("input", {}),
                call_id=block_dict.get("id"),
            )
            return

        if block_type == "tool_result":
            output = self._deserialize_json_like(block_dict.get("output"))
            self._attach_tool_result(
                output=output,
                tool_name=block_dict.get("name"),
                call_id=block_dict.get("id"),
            )
            tool_output_text = self._stringify_output_text(
                self._normalize_tool_output(output),
            )
            if tool_output_text:
                self._append_output_text(
                    tool_output_text,
                    prefix=f"[工具结果:{block_dict.get('name') or 'unknown_tool'}]",
                )
            return

        if block_type == "thinking":
            self._append_output_text(
                block_dict.get("thinking", ""),
                prefix="[思考]",
                inline_prefix=True,
            )
            return

        if block_type == "text":
            text = block_dict.get("text", "")
            if message_type == "reasoning":
                self._append_output_text(text, prefix="[思考]", inline_prefix=True)
            elif role != "user":
                self._append_output_text(text)
            return

    def _process_data_payload(
        self,
        payload: Any,
        *,
        message_type: str | None = None,
    ) -> None:
        payload = self._deserialize_json_like(payload)
        if payload in (None, "", {}, []):
            return

        if isinstance(payload, dict):
            call_id = payload.get("call_id") or payload.get("id")
            tool_name = payload.get("name") or payload.get("tool")

            if message_type in {"plugin_call", "function_call", "mcp_call"} or (
                tool_name and ("input" in payload or "arguments" in payload)
            ):
                tool_input = payload.get("input", payload.get("arguments"))
                self._append_tool_call(
                    tool_name=tool_name or "",
                    tool_input=self._deserialize_json_like(tool_input),
                    call_id=call_id,
                )
                return

            if message_type in {
                "plugin_call_output",
                "function_call_output",
                "mcp_call_output",
            } or ("output" in payload or "result" in payload):
                output = payload.get("output", payload.get("result"))
                normalized_output = self._deserialize_json_like(output)
                self._attach_tool_result(
                    output=normalized_output,
                    tool_name=tool_name,
                    call_id=call_id,
                )
                tool_output_text = self._stringify_output_text(
                    self._normalize_tool_output(normalized_output),
                )
                if tool_output_text:
                    self._append_output_text(
                        tool_output_text,
                        prefix=f"[工具结果:{tool_name or 'unknown_tool'}]",
                    )
                return

    def _append_tool_call(
        self,
        *,
        tool_name: str,
        tool_input: Any = None,
        call_id: str | None = None,
    ) -> None:
        normalized_tool_name = tool_name or "unknown_tool"
        entry = {
            "tool": normalized_tool_name,
            "timestamp": self._now_iso(),
        }
        if call_id:
            entry["call_id"] = call_id
        if tool_input not in (None, "", {}, []):
            entry["args"] = tool_input
        self._tool_execution_log.append(entry)

    def _attach_tool_result(
        self,
        *,
        output: Any,
        tool_name: str | None = None,
        call_id: str | None = None,
    ) -> None:
        target = None
        for log in reversed(self._tool_execution_log):
            if call_id and log.get("call_id") == call_id:
                target = log
                break
            if not call_id and tool_name and log.get("tool") == tool_name and "result" not in log:
                target = log
                break

        if target is None:
            target = {
                "tool": tool_name or "unknown_tool",
                "timestamp": self._now_iso(),
            }
            if call_id:
                target["call_id"] = call_id
            self._tool_execution_log.append(target)

        target["result"] = output

    def _append_output_text(
        self,
        text: Any,
        *,
        prefix: str | None = None,
        inline_prefix: bool = False,
    ) -> None:
        rendered = self._stringify_output_text(text)
        if not rendered:
            return
        if prefix:
            rendered = f"{prefix}{rendered}" if inline_prefix else f"{prefix}\n{rendered}"
        rendered = rendered.rstrip()
        if not rendered:
            return
        next_segment = f"{rendered}\n"
        if self._full_output.endswith(next_segment):
            return
        self._full_output += next_segment

    def _cleanup_session_file(self, session_id: str) -> None:
        session = getattr(self.runner, "session", None)
        if session is None or not hasattr(session, "_get_save_path"):
            return

        try:
            session_path = Path(
                session._get_save_path(  # pylint: disable=protected-access
                    session_id,
                    self.user_id,
                )
            )
            if session_path.exists():
                session_path.unlink()
        except Exception:
            logger.warning("Failed to clean up focus session file", exc_info=True)

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            try:
                return value.model_dump()
            except Exception:
                logger.debug("model_dump failed for %s", type(value), exc_info=True)
        return value

    @staticmethod
    def _deserialize_json_like(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped or stripped[0] not in "[{":
            return value
        try:
            return json.loads(stripped)
        except Exception:
            return value

    def _normalize_message_type(self, message_type: Any) -> str | None:
        if hasattr(message_type, "value"):
            return message_type.value
        if isinstance(message_type, str):
            return message_type
        return None

    def _normalize_tool_output(self, output: Any) -> Any:
        output = self._deserialize_json_like(output)
        if isinstance(output, list):
            text_parts = [
                block.get("text", "")
                for block in output
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            if text_parts and len(text_parts) == len(output):
                return "\n".join(part for part in text_parts if part).strip()
        return output

    @staticmethod
    def _stringify_output_text(value: Any) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, str):
            return value.strip()
        try:
            return json.dumps(value, ensure_ascii=False, indent=2).strip()
        except Exception:
            return str(value).strip()

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime

        return datetime.now().isoformat()
