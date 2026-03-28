# -*- coding: utf-8 -*-
"""Evolution executor for running digital life evolution."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .models import (
    CORE_EVOLUTION_FILES,
    EvolutionArchive,
    EvolutionRecord,
    EvolutionRunRequest,
)

if TYPE_CHECKING:
    from .repo.json_repo import JsonEvolutionRepository

logger = logging.getLogger(__name__)


class EvolutionExecutor:
    """Execute one evolution run against the current workspace."""

    def __init__(
        self,
        workspace,
        repo: "JsonEvolutionRepository",
    ) -> None:
        self.workspace = workspace
        self.repo = repo
        self._current_record: EvolutionRecord | None = None
        self._tool_execution_log: list[dict] = []
        self._structured_records: list[dict] = []
        self._full_output: str = ""
        self._processed_message_ids: set[str] = set()
        self._before_files: dict[str, str] = {}
        self._after_files: dict[str, str] = {}
        self._changed_files: list[str] = []

    async def execute_with_record(
        self,
        request: EvolutionRunRequest,
        record: EvolutionRecord,
    ) -> EvolutionRecord:
        """Execute evolution against an existing running record."""
        self._current_record = record
        self._tool_execution_log = []
        self._structured_records = []
        self._full_output = ""
        self._processed_message_ids = set()
        self._before_files = await self._snapshot_files()
        self._after_files = {}
        self._changed_files = []

        evolution_prompt = await self._build_evolution_prompt(
            request,
            record.generation - 1,
        )
        session_id = f"evolution:{self.workspace.agent_id}:{record.id}"
        start_time = datetime.now()

        try:
            await asyncio.wait_for(
                self._run_agent(
                    session_id=session_id,
                    evolution_prompt=evolution_prompt,
                ),
                timeout=request.timeout_seconds,
            )
            self._current_record.status = "success"
            self._current_record.is_active = True
        except asyncio.TimeoutError:
            self._current_record.status = "failed"
            self._current_record.error_message = "Execution timeout"
            logger.warning(
                "Evolution timeout: agent=%s generation=%s",
                self.workspace.agent_id,
                record.generation,
            )
        except asyncio.CancelledError:
            self._current_record.status = "cancelled"
            self._current_record.error_message = "Execution cancelled"
            logger.info(
                "Evolution cancelled: agent=%s generation=%s",
                self.workspace.agent_id,
                record.generation,
            )
        except Exception as exc:
            self._current_record.status = "failed"
            self._current_record.error_message = str(exc)
            logger.error("Evolution failed: %s", exc, exc_info=True)
        finally:
            await self._finalize_evolution(start_time)
            await self.repo.save_record(self._current_record)
            if self.workspace.config.evolution.archive_enabled:
                await self._create_archive()
            self._cleanup_session_file(session_id)

        return self._current_record

    async def _run_agent(
        self,
        *,
        session_id: str,
        evolution_prompt: str,
    ) -> None:
        agent_request = {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": evolution_prompt}],
                },
            ],
            "session_id": session_id,
            "user_id": "evolution_system",
            "channel": "console",
        }

        async for event in self.workspace.runner.stream_query(agent_request):
            await self._process_event(event)

    async def _build_evolution_prompt(
        self,
        request: EvolutionRunRequest,
        current_generation: int,
    ) -> str:
        if request.custom_prompt:
            base_prompt = request.custom_prompt
        else:
            soul_path = self.workspace.workspace_dir / "SOUL.md"
            if soul_path.exists():
                try:
                    base_prompt = soul_path.read_text(encoding="utf-8")
                except Exception as exc:
                    logger.warning("Failed to read SOUL.md: %s", exc)
                    base_prompt = "你是进化的智能体。请自主探索、学习并更新自己的核心文件。"
            else:
                base_prompt = "你是进化的智能体。请自主探索、学习并更新自己的核心文件。"

        evolution_context = f"""

---

# 进化任务

你是第 {current_generation + 1} 代智能体。现在开始你的进化过程。

## 你的能力
1. 你可以使用 `read_file` 查看文件
2. 你可以使用 `glob_search` 和 `grep_search` 探索代码与工作区
3. 你可以使用 `write_file` / `edit_file` 更新核心文件

## 你只能修改的文件
- SOUL.md
- PROFILE.md
- PLAN.md
- EVOLUTION.md

## 进化原则
- 每次进化都是独立运行，不依赖之前的聊天上下文
- 你的长期记忆只沉淀在四个核心文件里
- 只根据真实发现做更新，不编造不存在的能力
- 如果没有必要修改，就明确记录“本代未调整”

## 建议流程
1. 阅读 SOUL.md / PROFILE.md / PLAN.md / EVOLUTION.md
2. 用 grep_search / glob_search 了解当前项目和工具
3. 反思哪些描述需要修正、补充或精简
4. 更新核心文件
5. 在 EVOLUTION.md 记录本代改动、原因和效果
"""
        return base_prompt + evolution_context

    async def _snapshot_files(self) -> dict[str, str]:
        snapshots: dict[str, str] = {}
        for filename in CORE_EVOLUTION_FILES:
            file_path = self.workspace.workspace_dir / filename
            if file_path.exists():
                try:
                    snapshots[filename] = file_path.read_text(encoding="utf-8")
                except Exception as exc:
                    logger.warning("Failed to read %s: %s", file_path, exc)
        return snapshots

    async def _finalize_evolution(self, start_time: datetime) -> None:
        self._after_files = await self._snapshot_files()
        self._changed_files = [
            filename
            for filename in CORE_EVOLUTION_FILES
            if self._before_files.get(filename) != self._after_files.get(filename)
        ]
        self._current_record.duration_seconds = (
            datetime.now() - start_time
        ).total_seconds()
        if self.workspace.config.evolution.archive_enabled:
            self._current_record.archive_id = self._current_record.id
        self._current_record.output_summary = self._build_output_summary()

    def _build_output_summary(self) -> str:
        if self._changed_files:
            changed = "、".join(self._changed_files)
            return f"更新了 {changed}"

        if self._current_record.status == "success":
            return "本代未检测到核心文件改动"

        if self._current_record.error_message:
            return self._current_record.error_message[:200]

        summary = self._full_output.strip().splitlines()
        if summary:
            return summary[0][:200]
        return ""

    async def _process_event(self, event) -> None:
        event_class = type(event).__name__
        logger.debug("Processing event: %s", event_class)
        if event_class != "Message":
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
        self._record_metadata(
            self._serialize_value(getattr(message, "metadata", None)),
            message_type=message_type,
        )

        content = getattr(message, "content", None)
        if not isinstance(content, list):
            return

        for block in content:
            block_dict = self._serialize_value(block)
            if isinstance(block_dict, dict):
                self._process_block_dict(
                    block_dict,
                    message_type=message_type,
                    role=role,
                )

    def _process_block_dict(
        self,
        block: dict,
        *,
        message_type: str | None = None,
        role: str | None = None,
    ) -> None:
        block_type = block.get("type")
        if block_type == "tool_use":
            self._append_tool_call(
                tool_name=block.get("name", ""),
                tool_input=block.get("input", {}),
                call_id=block.get("id"),
            )
            return

        if block_type == "tool_result":
            output = block.get("output")
            self._attach_tool_result(
                output=output,
                tool_name=block.get("name"),
                call_id=block.get("id"),
            )
            tool_output_text = self._stringify_output_text(
                self._normalize_tool_output(output),
            )
            if tool_output_text:
                self._append_output_text(
                    tool_output_text,
                    prefix=f"[工具结果:{block.get('name') or 'unknown_tool'}]",
                )
            return

        if block_type == "thinking":
            self._append_output_text(
                block.get("thinking", ""),
                prefix="[思考]",
                inline_prefix=True,
            )
            return

        if block_type == "text":
            text = block.get("text", "")
            if message_type == "reasoning":
                self._append_output_text(text, prefix="[思考]", inline_prefix=True)
            elif role != "user":
                self._append_output_text(text)
            return

        if block_type == "data":
            self._process_data_payload(
                block.get("data"),
                message_type=message_type,
            )

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

        self._append_structured_record(
            payload,
            record_type="data",
            source=message_type,
        )

    def _append_tool_call(
        self,
        *,
        tool_name: str,
        tool_input: Any = None,
        call_id: str | None = None,
    ) -> None:
        normalized_tool_name = tool_name or "unknown_tool"
        if normalized_tool_name not in self._current_record.tools_used:
            self._current_record.tools_used.append(normalized_tool_name)

        existing = self._find_tool_log(
            call_id=call_id,
            tool_name=normalized_tool_name,
            require_open=False,
        )
        if existing is None:
            self._current_record.tool_calls_count += 1
            existing = {
                "tool": normalized_tool_name,
                "timestamp": datetime.now().isoformat(),
            }
            if call_id:
                existing["call_id"] = call_id
            self._tool_execution_log.append(existing)

        if tool_input not in (None, "", {}, []):
            existing["args"] = tool_input

    def _attach_tool_result(
        self,
        *,
        output: Any,
        tool_name: str | None = None,
        call_id: str | None = None,
    ) -> None:
        target = self._find_tool_log(
            call_id=call_id,
            tool_name=tool_name,
            require_open=True,
        )
        if target is None:
            target = {
                "tool": tool_name or "unknown_tool",
                "timestamp": datetime.now().isoformat(),
            }
            if call_id:
                target["call_id"] = call_id
            self._tool_execution_log.append(target)
        target["result"] = output

    def _find_tool_log(
        self,
        *,
        call_id: str | None = None,
        tool_name: str | None = None,
        require_open: bool = False,
    ) -> dict[str, Any] | None:
        if call_id:
            for log in reversed(self._tool_execution_log):
                if require_open and "result" in log:
                    continue
                if log.get("call_id") == call_id:
                    return log
            if tool_name:
                for log in reversed(self._tool_execution_log):
                    if require_open and "result" in log:
                        continue
                    if log.get("tool") == tool_name and not log.get("call_id"):
                        return log
            return None

        if tool_name:
            for log in reversed(self._tool_execution_log):
                if require_open and "result" in log:
                    continue
                if log.get("tool") == tool_name:
                    return log
        return None

    def _record_metadata(
        self,
        metadata: Any,
        *,
        message_type: str | None = None,
    ) -> None:
        if metadata in (None, "", {}, []):
            return

        if isinstance(metadata, dict):
            structured_output = metadata.get("structured_output")
            if structured_output not in (None, "", {}, []):
                self._append_structured_record(
                    self._serialize_value(structured_output),
                    record_type="structured_output",
                    source=message_type,
                )
                remaining_metadata = {
                    key: value
                    for key, value in metadata.items()
                    if key != "structured_output" and value not in (None, "", {}, [])
                }
                if remaining_metadata:
                    self._append_structured_record(
                        remaining_metadata,
                        record_type="metadata",
                        source=message_type,
                    )
                return

        self._append_structured_record(
            metadata,
            record_type="metadata",
            source=message_type,
        )

    def _append_structured_record(
        self,
        data: Any,
        *,
        record_type: str,
        source: str | None = None,
    ) -> None:
        if data in (None, "", {}, []):
            return

        record = {
            "type": record_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }
        if source:
            record["source"] = source
        self._structured_records.append(record)

    def _deserialize_json_like(self, value: Any) -> Any:
        value = self._serialize_value(value)
        if not isinstance(value, str):
            return value

        stripped = value.strip()
        if not stripped or stripped[0] not in "[{":
            return value
        try:
            return json.loads(stripped)
        except Exception:
            return value

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

    def _stringify_output_text(self, value: Any) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, str):
            return value.strip()
        try:
            return json.dumps(value, ensure_ascii=False, indent=2).strip()
        except Exception:
            return str(value).strip()

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

    def _serialize_value(self, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            try:
                return value.model_dump()
            except Exception:
                logger.debug("model_dump failed for %s", type(value), exc_info=True)
        return value

    def _normalize_message_type(self, message_type: Any) -> str | None:
        if hasattr(message_type, "value"):
            return message_type.value
        if isinstance(message_type, str):
            return message_type
        return None

    async def _create_archive(self) -> None:
        archive = EvolutionArchive(
            archive_id=self._current_record.id,
            evolution_id=self._current_record.id,
            generation=self._current_record.generation,
            timestamp=datetime.now(),
            before_files=self._before_files,
            after_files=self._after_files,
            changed_files=self._changed_files,
            tool_execution_log=self._tool_execution_log,
            structured_records=self._structured_records,
            full_output=self._full_output,
            reverted_to_record_id=self._current_record.reverted_to_record_id,
        )
        await self.repo.save_archive(archive)

    def _cleanup_session_file(self, session_id: str) -> None:
        session = getattr(self.workspace.runner, "session", None)
        if session is None or not hasattr(session, "_get_save_path"):
            return

        try:
            session_path = Path(
                session._get_save_path(  # pylint: disable=protected-access
                    session_id,
                    "evolution_system",
                )
            )
            if session_path.exists():
                session_path.unlink()
        except Exception:
            logger.warning("Failed to clean up evolution session file", exc_info=True)
