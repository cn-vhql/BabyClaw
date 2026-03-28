# -*- coding: utf-8 -*-
"""Evolution executor for running digital life evolution."""

from __future__ import annotations

import asyncio
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .models import EvolutionArchive, EvolutionRecord, EvolutionRunRequest

if TYPE_CHECKING:
    from .repo.json_repo import JsonEvolutionRepository

logger = logging.getLogger(__name__)


class EvolutionExecutor:
    """Evolution executor for running evolution process."""

    # Protected files that cannot be modified
    PROTECTED_FILES = {
        "agent.json",
        "sessions",
        "memory",
        "chats.json",
        "token_usage.json",
    }

    def __init__(
        self,
        workspace,  # Workspace instance
        repo: "JsonEvolutionRepository",
    ) -> None:
        """Initialize executor with workspace and repository."""
        self.workspace = workspace
        self.repo = repo
        self._current_record: EvolutionRecord | None = None
        self._tool_execution_log: list[dict] = []
        self._structured_records: list[dict] = []
        self._full_output: str = ""
        self._processed_message_ids: set[str] = set()

    async def execute_with_record(
        self,
        request: EvolutionRunRequest,
        record: EvolutionRecord,
    ) -> EvolutionRecord:
        """Execute evolution using an existing record (created by API).

        Args:
            request: Evolution run request
            record: Pre-created record (usually with status="running")

        Returns:
            Updated record with final status
        """
        self._current_record = record
        self._tool_execution_log = []
        self._structured_records = []
        self._full_output = ""
        self._processed_message_ids = set()

        # Snapshot files before evolution
        await self._snapshot_before()

        # Create or update evolution chat
        await self._ensure_evolution_chat()

        # Build evolution prompt (using SOUL.md content)
        evolution_prompt = await self._build_evolution_prompt(
            request,
            record.generation - 1,  # Current generation is record.generation - 1
        )

        # Use unified session_id for all evolutions
        evolution_session_id = f"evolution:{self.workspace.agent_id}"

        try:
            start_time = datetime.now()

            # Execute agent reasoning
            agent_request = {
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": evolution_prompt}],
                    },
                ],
                "session_id": evolution_session_id,
                "user_id": "evolution_system",
            }

            async for event in self.workspace.runner.stream_query(agent_request):
                await self._process_event(event)

            # Finalize evolution
            await self._finalize_evolution(start_time)

        except asyncio.TimeoutError:
            self._current_record.status = "failed"
            self._current_record.error_message = "Execution timeout"
            logger.error(
                f"Evolution timeout: {self.workspace.agent_id} gen {record.generation}"
            )

        except Exception as e:
            self._current_record.status = "failed"
            self._current_record.error_message = str(e)
            logger.error(f"Evolution failed: {e}", exc_info=True)

        finally:
            # Update record (not save new one)
            await self.repo.save_record(self._current_record)
            if self.workspace.config.evolution.archive_enabled:
                await self._create_archive()

        return self._current_record

    async def execute(self, request: EvolutionRunRequest) -> EvolutionRecord:
        """Execute one evolution cycle."""
        agent_id = self.workspace.agent_id
        generation = await self.repo.get_current_generation()
        next_generation = generation + 1

        # Check max_generations limit
        max_gen = self.workspace.config.evolution.max_generations
        if max_gen is not None and max_gen > 0 and next_generation > max_gen:
            logger.warning(
                f"Evolution blocked: reached max generation {max_gen}, "
                f"current={generation}"
            )
            # Create a failed record
            record = EvolutionRecord(
                generation=next_generation,
                agent_id=agent_id,
                agent_name=self.workspace.config.name,
                timestamp=datetime.now(),
                trigger_type=request.trigger_type,
                status="failed",
                error_message=f"已达到最大代数限制 ({max_gen})",
            )
            await self.repo.save_record(record)
            return record

        # Create record
        self._current_record = EvolutionRecord(
            generation=next_generation,
            agent_id=agent_id,
            agent_name=self.workspace.config.name,
            timestamp=datetime.now(),
            trigger_type=request.trigger_type,
            status="running",
        )
        self._tool_execution_log = []
        self._structured_records = []
        self._full_output = ""
        self._processed_message_ids = set()

        # Snapshot files before evolution
        await self._snapshot_before()

        # Create or update evolution chat
        await self._ensure_evolution_chat()

        # Build evolution prompt (using SOUL.md content)
        evolution_prompt = await self._build_evolution_prompt(request, generation)

        # Use unified session_id for all evolutions
        evolution_session_id = f"evolution:{self.workspace.agent_id}"

        try:
            start_time = datetime.now()

            # Execute agent reasoning
            agent_request = {
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": evolution_prompt}],
                    },
                ],
                "session_id": evolution_session_id,
                "user_id": "evolution_system",
            }

            async for event in self.workspace.runner.stream_query(agent_request):
                await self._process_event(event)

            # Finalize evolution
            await self._finalize_evolution(start_time)

        except asyncio.TimeoutError:
            self._current_record.status = "failed"
            self._current_record.error_message = "Execution timeout"
            logger.error(f"Evolution timeout: {agent_id} gen {generation}")

        except Exception as e:
            self._current_record.status = "failed"
            self._current_record.error_message = str(e)
            logger.error(f"Evolution failed: {e}", exc_info=True)

        finally:
            # Save record and archive
            await self.repo.save_record(self._current_record)
            if self.workspace.config.evolution.archive_enabled:
                await self._create_archive()

        return self._current_record

    async def _build_evolution_prompt(
        self,
        request: EvolutionRunRequest,
        current_generation: int,
    ) -> str:
        """Build evolution prompt - using SOUL.md content."""
        # If custom prompt provided, use it
        if request.custom_prompt:
            base_prompt = request.custom_prompt
        else:
            # Read SOUL.md as base prompt
            soul_path = self.workspace.workspace_dir / "SOUL.md"
            if soul_path.exists():
                try:
                    base_prompt = soul_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Failed to read SOUL.md: {e}")
                    base_prompt = "你是进化的智能体。请自主探索、学习并更新自己的配置文件。"
            else:
                base_prompt = "你是进化的智能体。请自主探索、学习并更新自己的配置文件。"

        # Add evolution context
        evolution_context = f"""

---

# 进化任务

你是第 {current_generation + 1} 代智能体。现在开始你的进化过程。

## 你的能力
1. 你可以使用 `read_file` 工具查看任何文件
2. 你可以使用 `write_file` 工具修改文件（但不能修改受保护的系统文件）
3. 你可以使用 `glob_search` 和 `grep_search` 探索代码

## 你可以更新的文件
- **SOUL.md**: 你的核心信念、价值观、行为准则
- **PROFILE.md**: 你的能力描述、专长、限制
- **PLAN.md**: 你的学习计划、目标、待办事项
- **EVOLUTION.md**: 你的进化历史、发现、成长记录

## 进化流程
1. **自我认知**: 读取 SOUL.md、PROFILE.md，了解自己
2. **环境探索**: 探索项目结构，了解自己的工具和知识库
3. **反思改进**: 思考如何优化自己的配置
4. **执行更新**: 使用 write_file 更新文件
5. **记录成长**: 在 EVOLUTION.md 中记录本次进化的发现和改变

## 更新原则
- 保持核心信念的一致性
- 基于实际发现进行改进
- 记录改变的原因和预期效果
- 不要删除有价值的历史信息

## 开始
请开始你的进化，记录你学到的东西和做出的改变。
"""

        return base_prompt + evolution_context

    async def _snapshot_before(self) -> None:
        """Snapshot files before evolution."""
        workspace_dir = self.workspace.workspace_dir

        self._current_record.soul_before = self._read_file(
            workspace_dir / "SOUL.md"
        )
        self._current_record.profile_before = self._read_file(
            workspace_dir / "PROFILE.md"
        )
        self._current_record.plan_before = self._read_file(
            workspace_dir / "PLAN.md"
        )

    async def _finalize_evolution(self, start_time: datetime) -> None:
        """Finalize evolution after completion."""
        workspace_dir = self.workspace.workspace_dir

        # Snapshot files after evolution
        self._current_record.soul_after = self._read_file(
            workspace_dir / "SOUL.md"
        )
        self._current_record.profile_after = self._read_file(
            workspace_dir / "PROFILE.md"
        )
        self._current_record.plan_after = self._read_file(
            workspace_dir / "PLAN.md"
        )

        # Update status
        self._current_record.status = "success"
        self._current_record.duration_seconds = (
            datetime.now() - start_time
        ).total_seconds()

    def _read_file(self, path: Path) -> str | None:
        """Safely read file content."""
        try:
            if path.exists():
                return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read {path}: {e}")
        return None

    async def _process_event(self, event) -> None:
        """Process completed agent message events only.

        The runtime stream emits both fine-grained deltas and completed
        ``Message`` objects. Recording both causes duplicated text/tool logs.
        Evolution archives therefore only consume completed messages here.
        """
        event_class = type(event).__name__
        logger.debug(f"Processing event: {event_class}")

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
        """Process a completed runtime Message event."""
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
            else:
                logger.debug(f"Non-dict content block: {type(block)}")

    def _process_block_dict(
        self,
        block: dict,
        *,
        message_type: str | None = None,
        role: str | None = None,
    ) -> None:
        """Process a content block dict (from Message.content)."""
        block_type = block.get("type")

        # Tool use block (tool call)
        if block_type == "tool_use":
            tool_name = block.get("name", "")
            tool_input = block.get("input", {})
            self._append_tool_call(
                tool_name=tool_name,
                tool_input=tool_input,
                call_id=block.get("id"),
            )

        # Tool result block
        elif block_type == "tool_result":
            output = block.get("output", None)
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

        # Thinking block
        elif block_type == "thinking":
            thinking = block.get("thinking", "")
            self._append_output_text(thinking, prefix="[思考]", inline_prefix=True)
            logger.debug(f"Thinking: {len(thinking)} chars")

        # Text block
        elif block_type == "text":
            text = block.get("text", "")
            if message_type == "reasoning":
                self._append_output_text(text, prefix="[思考]", inline_prefix=True)
            elif role != "user":
                self._append_output_text(text)
            if (
                role in (None, "assistant")
                and message_type != "reasoning"
                and len(self._current_record.output_summary) < 500
            ):
                self._current_record.output_summary += text[:200]

            logger.debug(f"✓ Text: {len(text)} chars")

        elif block_type == "data":
            self._process_data_payload(
                block.get("data"),
                message_type=message_type,
            )

        else:
            logger.debug(f"Unknown block type: {block_type}")

    def _process_data_payload(
        self,
        payload: Any,
        *,
        message_type: str | None = None,
    ) -> None:
        """Process runtime DataContent payloads."""
        payload = self._deserialize_json_like(payload)
        if payload in (None, "", {}, []):
            return

        if isinstance(payload, dict):
            call_id = payload.get("call_id") or payload.get("id")
            tool_name = payload.get("name") or payload.get("tool")

            if message_type in {
                "plugin_call",
                "function_call",
                "mcp_call",
            } or (tool_name and ("input" in payload or "arguments" in payload)):
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
        """Record a single tool call without duplicating completed messages."""
        normalized_tool_name = tool_name or "unknown_tool"
        logger.info(f"✓ Tool use: {normalized_tool_name}")

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
        """Attach a tool result to the most relevant tool call record."""
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
        """Find the best matching tool log entry."""
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
        """Persist structured metadata emitted by the model/runtime."""
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
        """Append one structured record for later inspection."""
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
        """Best-effort JSON parsing for string payload fields."""
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
        """Flatten tool outputs that only contain text blocks."""
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
        """Render structured runtime output into readable text."""
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
        """Append one output segment while avoiding consecutive duplicates."""
        rendered = self._stringify_output_text(text)
        if not rendered:
            return

        if prefix:
            rendered = (
                f"{prefix}{rendered}"
                if inline_prefix
                else f"{prefix}\n{rendered}"
            )

        rendered = rendered.rstrip()
        if not rendered:
            return

        next_segment = f"{rendered}\n"
        if self._full_output.endswith(next_segment):
            return
        self._full_output += next_segment

    def _serialize_value(self, value: Any) -> Any:
        """Convert pydantic/runtime models into plain Python data."""
        if hasattr(value, "model_dump"):
            try:
                return value.model_dump()
            except Exception:
                logger.debug("model_dump failed for %s", type(value), exc_info=True)
                return value
        return value

    def _normalize_message_type(self, message_type: Any) -> str | None:
        """Normalize runtime enum-like message types into plain strings."""
        if hasattr(message_type, "value"):
            return message_type.value
        if isinstance(message_type, str):
            return message_type
        return None

    async def _ensure_evolution_chat(self) -> None:
        """Ensure evolution chat exists in the chat list."""
        from ..runner.models import ChatSpec
        from ..runner.manager import ChatManager

        # Use a fixed session ID for all evolutions
        evolution_session_id = f"evolution:{self.workspace.agent_id}"
        evolution_user_id = "evolution_system"

        # Check if evolution chat already exists
        mgr = self.workspace.chat_manager
        existing_chats = await mgr.list_chats(
            user_id=evolution_user_id,
            channel="console",
        )

        evolution_chat = None
        for chat in existing_chats:
            if chat.meta.get("is_evolution"):
                evolution_chat = chat
                break

        if evolution_chat:
            # Update existing evolution chat
            evolution_chat.updated_at = datetime.now()
            # Update name to reflect latest generation
            evolution_chat.name = f"进化记录 (第{self._current_record.generation}代)"
            await mgr.update_chat(evolution_chat)
        else:
            # Create new evolution chat
            from uuid import uuid4

            new_chat = ChatSpec(
                id=str(uuid4()),
                name=f"进化记录 (第{self._current_record.generation}代)",
                session_id=evolution_session_id,
                user_id=evolution_user_id,
                channel="console",
                meta={
                    "is_evolution": True,
                    "agent_id": self.workspace.agent_id,
                },
            )
            await mgr.create_chat(new_chat)

    async def _create_archive(self) -> None:
        """Create complete archive."""
        archive = EvolutionArchive(
            evolution_id=self._current_record.id,
            generation=self._current_record.generation,
            timestamp=datetime.now(),
            tool_execution_log=self._tool_execution_log,
            structured_records=self._structured_records,
            full_output=self._full_output,
        )

        # Save file snapshots
        workspace_dir = self.workspace.workspace_dir
        for filename in ["SOUL.md", "PROFILE.md", "PLAN.md", "EVOLUTION.md"]:
            file_path = workspace_dir / filename
            if file_path.exists():
                try:
                    archive.files[filename] = file_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Failed to archive {filename}: {e}")

        # Save to repository
        await self.repo.save_archive(archive)
