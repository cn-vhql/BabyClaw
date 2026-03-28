# -*- coding: utf-8 -*-
"""JSON index + markdown archive repository for evolution data."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import (
    CORE_EVOLUTION_FILES,
    EvolutionArchive,
    EvolutionArchiveMeta,
    EvolutionIndexFile,
    EvolutionRecord,
)

logger = logging.getLogger(__name__)


class JsonEvolutionRepository:
    """Evolution storage and runtime coordination."""

    def __init__(self, workspace_dir: Path) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.index_file = self.workspace_dir / "evolution.json"
        self.archives_dir = self.workspace_dir / "evolution_archives"
        self._lock = asyncio.Lock()
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._ensure_storage_layout()

    def _ensure_storage_layout(self) -> None:
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        if self._is_legacy_storage():
            self._backup_legacy_storage()

        self.archives_dir.mkdir(exist_ok=True)
        if not self.index_file.exists():
            self._write_index(EvolutionIndexFile())

    def _is_legacy_storage(self) -> bool:
        if self.index_file.exists():
            try:
                raw = json.loads(self.index_file.read_text(encoding="utf-8"))
            except Exception:
                return True
            if raw.get("version") != 2:
                return True
            if "generation_counter" not in raw:
                return True
            try:
                EvolutionIndexFile(**raw)
            except Exception:
                return True

        if self.archives_dir.exists():
            for entry in self.archives_dir.iterdir():
                if entry.is_dir() and entry.name.startswith("gen_"):
                    return True
        return False

    def _backup_legacy_storage(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if self.index_file.exists():
            backup_file = self.workspace_dir / f"evolution.legacy.{timestamp}.json"
            try:
                self.index_file.rename(backup_file)
            except Exception:
                logger.warning("Failed to back up legacy evolution index", exc_info=True)

        if self.archives_dir.exists() and any(self.archives_dir.iterdir()):
            backup_dir = self.workspace_dir / f"evolution_archives_legacy_{timestamp}"
            try:
                self.archives_dir.rename(backup_dir)
            except Exception:
                logger.warning("Failed to back up legacy evolution archives", exc_info=True)

    def _read_index(self) -> EvolutionIndexFile:
        if not self.index_file.exists():
            return EvolutionIndexFile()
        raw = json.loads(self.index_file.read_text(encoding="utf-8"))
        index = EvolutionIndexFile(**raw)
        return self._normalize_index(index)

    def _write_index(self, index: EvolutionIndexFile) -> None:
        normalized = self._normalize_index(index)
        self.index_file.write_text(
            json.dumps(normalized.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _normalize_index(self, index: EvolutionIndexFile) -> EvolutionIndexFile:
        records = sorted(
            index.records,
            key=lambda item: (item.generation, item.timestamp),
            reverse=True,
        )
        index.records = records

        running = self._find_record_in_index(index, index.running_record_id)
        if running is None or running.status != "running":
            index.running_record_id = None

        active = self._find_record_in_index(index, index.active_record_id)
        if active is None or active.status != "success":
            active = next(
                (record for record in records if record.is_active and record.status == "success"),
                None,
            )
            index.active_record_id = active.id if active else None

        for record in records:
            record.is_active = record.id == index.active_record_id

        return index

    def _find_record_in_index(
        self,
        index: EvolutionIndexFile,
        record_id: str | None,
    ) -> EvolutionRecord | None:
        if not record_id:
            return None
        for record in index.records:
            if record.id == record_id:
                return record
        return None

    def _upsert_record_in_index(
        self,
        index: EvolutionIndexFile,
        record: EvolutionRecord,
    ) -> EvolutionIndexFile:
        records = [item for item in index.records if item.id != record.id]
        records.append(record)
        index.records = records

        if record.status == "running":
            index.running_record_id = record.id
        elif index.running_record_id == record.id:
            index.running_record_id = None

        if record.is_active:
            index.active_record_id = record.id
        elif index.active_record_id == record.id:
            index.active_record_id = None

        return self._normalize_index(index)

    def register_task(self, record_id: str, task: asyncio.Task) -> None:
        self._running_tasks[record_id] = task

        def _cleanup(_: asyncio.Task) -> None:
            self._running_tasks.pop(record_id, None)

        task.add_done_callback(_cleanup)

    def unregister_task(self, record_id: str) -> None:
        self._running_tasks.pop(record_id, None)

    async def get_current_generation(self) -> int:
        async with self._lock:
            return self._read_index().generation_counter

    async def create_running_record(
        self,
        *,
        agent_id: str,
        agent_name: str,
        trigger_type: str,
    ) -> tuple[EvolutionRecord | None, EvolutionRecord | None]:
        async with self._lock:
            index = self._read_index()
            running = self._find_record_in_index(index, index.running_record_id)
            if running and running.status == "running":
                return None, running

            next_generation = index.generation_counter + 1
            record = EvolutionRecord(
                generation=next_generation,
                agent_id=agent_id,
                agent_name=agent_name,
                timestamp=datetime.now(),
                trigger_type=trigger_type,
                status="running",
            )
            index.generation_counter = next_generation
            index = self._upsert_record_in_index(index, record)
            self._write_index(index)
            return record, None

    async def create_failed_record(
        self,
        *,
        generation: int,
        agent_id: str,
        agent_name: str,
        trigger_type: str,
        error_message: str,
    ) -> EvolutionRecord:
        record = EvolutionRecord(
            generation=generation,
            agent_id=agent_id,
            agent_name=agent_name,
            timestamp=datetime.now(),
            trigger_type=trigger_type,
            status="failed",
            error_message=error_message,
        )
        await self.save_record(record)
        return record

    async def list_records(self, limit: int = 50) -> list[dict]:
        async with self._lock:
            index = self._read_index()
            return [
                record.model_dump(mode="json")
                for record in index.records[:limit]
            ]

    async def get_record(self, record_id: str) -> Optional[EvolutionRecord]:
        async with self._lock:
            index = self._read_index()
            return self._find_record_in_index(index, record_id)

    async def get_running_record(self) -> EvolutionRecord | None:
        async with self._lock:
            index = self._read_index()
            return self._find_record_in_index(index, index.running_record_id)

    async def save_record(self, record: EvolutionRecord) -> None:
        async with self._lock:
            index = self._read_index()
            index = self._upsert_record_in_index(index, record)
            self._write_index(index)

    async def save_archive(self, archive: EvolutionArchive) -> None:
        archive_path = self.archives_dir / archive.archive_id
        before_dir = archive_path / "before"
        after_dir = archive_path / "after"
        before_dir.mkdir(parents=True, exist_ok=True)
        after_dir.mkdir(parents=True, exist_ok=True)

        for filename, content in archive.before_files.items():
            (before_dir / filename).write_text(content, encoding="utf-8")
        for filename, content in archive.after_files.items():
            (after_dir / filename).write_text(content, encoding="utf-8")

        meta = EvolutionArchiveMeta(
            archive_id=archive.archive_id,
            evolution_id=archive.evolution_id,
            generation=archive.generation,
            timestamp=archive.timestamp,
            changed_files=archive.changed_files,
            tool_execution_log=archive.tool_execution_log,
            structured_records=archive.structured_records,
            full_output=archive.full_output,
            memory_snapshot=archive.memory_snapshot,
            reverted_to_record_id=archive.reverted_to_record_id,
        )
        (archive_path / "meta.json").write_text(
            json.dumps(meta.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _load_archive(self, archive_id: str) -> EvolutionArchive | None:
        archive_path = self.archives_dir / archive_id
        meta_file = archive_path / "meta.json"
        if not meta_file.exists():
            return None

        meta = EvolutionArchiveMeta(
            **json.loads(meta_file.read_text(encoding="utf-8"))
        )

        def _read_stage(stage_dir: Path) -> dict[str, str]:
            result: dict[str, str] = {}
            if not stage_dir.exists():
                return result
            for filename in CORE_EVOLUTION_FILES:
                file_path = stage_dir / filename
                if file_path.exists():
                    result[filename] = file_path.read_text(encoding="utf-8")
            return result

        return EvolutionArchive(
            archive_id=meta.archive_id,
            evolution_id=meta.evolution_id,
            generation=meta.generation,
            timestamp=meta.timestamp,
            before_files=_read_stage(archive_path / "before"),
            after_files=_read_stage(archive_path / "after"),
            changed_files=meta.changed_files,
            tool_execution_log=meta.tool_execution_log,
            structured_records=meta.structured_records,
            full_output=meta.full_output,
            memory_snapshot=meta.memory_snapshot,
            reverted_to_record_id=meta.reverted_to_record_id,
        )

    async def get_archive(self, archive_id: str) -> Optional[EvolutionArchive]:
        async with self._lock:
            return self._load_archive(archive_id)

    async def get_archive_by_evolution_id(
        self,
        evolution_id: str,
    ) -> Optional[EvolutionArchive]:
        async with self._lock:
            return self._load_archive(evolution_id)

    async def update_archive_revert(
        self,
        *,
        archive_id: str,
        reverted_to_record_id: str,
    ) -> None:
        async with self._lock:
            archive_path = self.archives_dir / archive_id
            meta_file = archive_path / "meta.json"
            if not meta_file.exists():
                return
            meta = EvolutionArchiveMeta(
                **json.loads(meta_file.read_text(encoding="utf-8"))
            )
            meta.reverted_to_record_id = reverted_to_record_id
            meta_file.write_text(
                json.dumps(meta.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    async def get_archive_file(
        self,
        archive_id: str,
        filename: str,
    ) -> Optional[str]:
        async with self._lock:
            archive_path = self.archives_dir / archive_id
            candidates = [
                archive_path / "after" / filename,
                archive_path / "before" / filename,
            ]
            for candidate in candidates:
                if candidate.exists():
                    return candidate.read_text(encoding="utf-8")
        return None

    async def delete_record(self, record_id: str) -> bool:
        async with self._lock:
            index = self._read_index()
            original_length = len(index.records)
            index.records = [record for record in index.records if record.id != record_id]
            if len(index.records) == original_length:
                return False
            if index.running_record_id == record_id:
                index.running_record_id = None
            if index.active_record_id == record_id:
                index.active_record_id = None
            self._write_index(index)

        archive_path = self.archives_dir / record_id
        if archive_path.exists():
            shutil.rmtree(archive_path, ignore_errors=True)
        return True

    async def cancel_running_record(self, record_id: str) -> EvolutionRecord | None:
        task = self._running_tasks.get(record_id)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.warning("Evolution cancel raised during cleanup", exc_info=True)

        record = await self.get_record(record_id)
        if record and record.status == "running":
            record.status = "cancelled"
            record.error_message = "Execution cancelled"
            await self.save_record(record)
        return await self.get_record(record_id)

    async def rollback_to_previous(self, record_id: str) -> tuple[EvolutionRecord, EvolutionRecord]:
        async with self._lock:
            index = self._read_index()
            if index.running_record_id:
                raise ValueError("There is a running evolution task")

            record = self._find_record_in_index(index, record_id)
            if record is None:
                raise ValueError("Record not found")
            if record.status != "success" or not record.is_active:
                raise ValueError("Only the active latest successful record can be rolled back")

            previous = next(
                (
                    item
                    for item in sorted(index.records, key=lambda rec: rec.generation, reverse=True)
                    if item.status == "success" and item.id != record.id and item.generation < record.generation
                ),
                None,
            )
            if previous is None:
                raise ValueError("No previous successful version available")

            previous_archive = self._load_archive(previous.archive_id or previous.id)
            if previous_archive is None:
                raise ValueError("Previous archive not found")

            for filename in CORE_EVOLUTION_FILES:
                content = previous_archive.after_files.get(filename)
                if content is None:
                    continue
                (self.workspace_dir / filename).write_text(content, encoding="utf-8")

            record.status = "reverted"
            record.is_active = False
            record.reverted_to_record_id = previous.id
            previous.is_active = True
            index = self._upsert_record_in_index(index, record)
            index = self._upsert_record_in_index(index, previous)
            self._write_index(index)

        await self.update_archive_revert(
            archive_id=record.archive_id or record.id,
            reverted_to_record_id=previous.id,
        )
        return record, previous
