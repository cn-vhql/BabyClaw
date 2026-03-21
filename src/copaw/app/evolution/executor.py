# -*- coding: utf-8 -*-
"""Evolution executor for running digital life evolution."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

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
        self._full_output: str = ""

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
        self._full_output = ""

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
        self._full_output = ""

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
        """Process agent output event.

        Args:
            event: Can be AgentResponse, Message, TextContent, ToolCallContent, etc.
        """
        event_class = type(event).__name__
        logger.debug(f"Processing event: {event_class}")

        # TextContent - direct text content (delta streaming)
        if event_class == "TextContent":
            text = getattr(event, "text", "")
            if text:
                self._full_output += text
                if len(self._current_record.output_summary) < 500:
                    self._current_record.output_summary += text[:200]
                logger.debug(f"TextContent: {len(text)} chars")
            return

        # Message - contains content blocks
        if event_class == "Message":
            content = getattr(event, "content", None)
            if not content:
                return

            # content can be a list of blocks
            if isinstance(content, list):
                for block in content:
                    # Block can be dict or object (with model_dump method)
                    if isinstance(block, dict):
                        self._process_block_dict(block)
                    elif hasattr(block, "model_dump"):
                        # Convert Pydantic model to dict
                        block_dict = block.model_dump()
                        if isinstance(block_dict, dict):
                            self._process_block_dict(block_dict)
                        else:
                            logger.debug(f"model_dump returned non-dict: {type(block_dict)}")
                    else:
                        logger.debug(f"Non-dict content block: {type(block)}")
            return

        # AgentResponse - contains output with messages
        if event_class == "AgentResponse":
            if not hasattr(event, "output") or not event.output:
                return

            for msg in event.output:
                content = getattr(msg, "content", None)
                if content and isinstance(content, list):
                    for block in content:
                        # Block can be dict or object (with model_dump method)
                        if isinstance(block, dict):
                            self._process_block_dict(block)
                        elif hasattr(block, "model_dump"):
                            # Convert Pydantic model to dict
                            block_dict = block.model_dump()
                            if isinstance(block_dict, dict):
                                self._process_block_dict(block_dict)
                            else:
                                logger.debug(f"model_dump returned non-dict: {type(block_dict)}")
                        else:
                            logger.debug(f"Non-dict content block in AgentResponse: {type(block)}")
            return

        logger.debug(f"Unhandled event type: {event_class}")

    def _process_block_dict(self, block: dict) -> None:
        """Process a content block dict (from Message.content)."""
        block_type = block.get("type")

        # Tool use block (tool call)
        if block_type == "tool_use":
            self._current_record.tool_calls_count += 1
            tool_name = block.get("name", "")
            tool_input = block.get("input", {})

            logger.info(f"✓ Tool use: {tool_name}")

            if tool_name and tool_name not in self._current_record.tools_used:
                self._current_record.tools_used.append(tool_name)

            # Record to tool log
            self._tool_execution_log.append({
                "tool": tool_name,
                "args": tool_input,
                "timestamp": datetime.now().isoformat(),
            })

        # Tool result block
        elif block_type == "tool_result":
            tool_name = block.get("name", "")
            output = block.get("output", None)

            logger.debug(f"✓ Tool result: {tool_name}")

            # Find the most recent tool call log for this tool and add the result
            if tool_name and self._tool_execution_log:
                for log in reversed(self._tool_execution_log):
                    if log["tool"] == tool_name and "result" not in log:
                        log["result"] = output
                        break

        # Thinking block
        elif block_type == "thinking":
            thinking = block.get("thinking", "")
            self._full_output += f"[思考]{thinking}\n"
            logger.debug(f"Thinking: {len(thinking)} chars")

        # Text block
        elif block_type == "text":
            text = block.get("text", "")
            self._full_output += text + "\n"
            if len(self._current_record.output_summary) < 500:
                self._current_record.output_summary += text[:200]

            logger.debug(f"✓ Text: {len(text)} chars")

        else:
            logger.debug(f"Unknown block type: {block_type}")

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
