# -*- coding: utf-8 -*-
"""JSON file repository for evolution data."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from ..archive_backfill import enrich_archive_from_sessions
from ..models import EvolutionArchive, EvolutionRecord

logger = logging.getLogger(__name__)


class JsonEvolutionRepository:
    """JSON file storage for evolution repository."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize repository with workspace directory."""
        self.workspace_dir = Path(workspace_dir)
        self.index_file = self.workspace_dir / "evolution.json"
        self.archives_dir = self.workspace_dir / "evolution_archives"
        self.archives_dir.mkdir(exist_ok=True)

    async def get_current_generation(self) -> int:
        """Get current generation number."""
        if self.index_file.exists():
            try:
                data = json.loads(self.index_file.read_text(encoding="utf-8"))
                return data.get("current_generation", 0)
            except Exception as e:
                logger.warning(f"Failed to read evolution index: {e}")
        return 0

    async def list_records(self, limit: int = 50) -> list[dict]:
        """List evolution records."""
        if not self.index_file.exists():
            return []

        try:
            data = json.loads(self.index_file.read_text(encoding="utf-8"))
            records = data.get("records", [])
            changed = False
            for record_dict in records[:limit]:
                if await self._repair_record_stats(record_dict):
                    changed = True

            if changed:
                self.index_file.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            return records[:limit]
        except Exception as e:
            logger.error(f"Failed to list records: {e}")
            return []

    async def get_record(self, record_id: str) -> Optional[EvolutionRecord]:
        """Get a single record by ID."""
        records = await self.list_records(limit=1000)
        for record_dict in records:
            if record_dict.get("id") == record_id:
                try:
                    return EvolutionRecord(**record_dict)
                except Exception as e:
                    logger.error(f"Failed to parse record {record_id}: {e}")
        return None

    async def save_record(self, record: EvolutionRecord) -> None:
        """Save evolution record (update if exists, insert if new)."""
        # Read existing data
        if self.index_file.exists():
            try:
                data = json.loads(self.index_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Failed to read index file, creating new: {e}")
                data = {"version": 1, "records": []}
        else:
            data = {"version": 1, "records": []}

        # Check if record already exists
        record_id = record.id
        existing_index = None
        for i, existing_record in enumerate(data.get("records", [])):
            if existing_record.get("id") == record_id:
                existing_index = i
                break

        # Convert record to dict
        record_dict = record.model_dump(mode="json")

        if existing_index is not None:
            # Update existing record
            data["records"][existing_index] = record_dict
            logger.debug(f"Updated existing record: {record_id}")
        else:
            # Insert new record at the beginning
            data["records"].insert(0, record_dict)
            logger.debug(f"Inserted new record: {record_id}")

        # Update generation count if successful
        if record.status == "success":
            data["current_generation"] = record.generation

        # Write back
        try:
            self.index_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Failed to save record: {e}")
            raise

    async def save_archive(self, archive: EvolutionArchive) -> None:
        """Save evolution archive."""
        # Create archive directory
        archive_name = (
            f"gen_{archive.generation:03d}_"
            f'{archive.timestamp.strftime("%Y%m%d_%H%M%S")}'
        )
        archive_path = self.archives_dir / archive_name
        archive_path.mkdir(exist_ok=True)

        # Save file snapshots
        for filename, content in archive.files.items():
            try:
                (archive_path / filename).write_text(content, encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed to save file {filename}: {e}")

        # Save metadata
        meta_file = archive_path / "meta.json"
        try:
            meta_file.write_text(
                json.dumps(archive.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Failed to save archive metadata: {e}")
            raise

        # Manual archive management - no automatic cleanup

    async def _repair_record_stats(self, record_dict: dict) -> bool:
        """Backfill list-friendly record stats from the corresponding archive."""
        if not isinstance(record_dict, dict):
            return False

        try:
            record = EvolutionRecord(**record_dict)
        except Exception as exc:
            logger.warning(
                "Failed to parse record %s during stats repair: %s",
                record_dict.get("id"),
                exc,
            )
            return False

        archive = await self.get_archive_by_evolution_id(record.id)
        if not archive:
            return False

        archive = await self.enrich_archive(archive, record=record)
        tool_logs = archive.tool_execution_log or []
        derived_count = len(tool_logs)
        existing_count = int(record_dict.get("tool_calls_count") or 0)
        next_count = max(existing_count, derived_count)

        existing_tools = [
            tool
            for tool in (record_dict.get("tools_used") or [])
            if isinstance(tool, str) and tool
        ]
        derived_tools: list[str] = []
        for entry in tool_logs:
            if not isinstance(entry, dict):
                continue
            tool_name = entry.get("tool")
            if isinstance(tool_name, str) and tool_name and tool_name not in derived_tools:
                derived_tools.append(tool_name)
        next_tools = list(dict.fromkeys([*existing_tools, *derived_tools]))

        changed = False
        if next_count != existing_count:
            record_dict["tool_calls_count"] = next_count
            changed = True
        if next_tools != existing_tools:
            record_dict["tools_used"] = next_tools
            changed = True

        return changed

    async def get_archive(self, archive_id: str) -> Optional[EvolutionArchive]:
        """Get archive by ID."""
        try:
            for archive_dir in self.archives_dir.iterdir():
                if not archive_dir.is_dir():
                    continue
                meta_file = archive_dir / "meta.json"
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text(encoding="utf-8"))
                        if meta.get("archive_id") == archive_id:
                            return EvolutionArchive(**meta)
                    except Exception as e:
                        logger.warning(f"Failed to parse archive {archive_dir.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to get archive {archive_id}: {e}")
        return None

    async def get_archive_by_evolution_id(
        self,
        evolution_id: str,
    ) -> Optional[EvolutionArchive]:
        """Get archive by evolution record ID."""
        try:
            for archive_dir in self.archives_dir.iterdir():
                if not archive_dir.is_dir():
                    continue
                meta_file = archive_dir / "meta.json"
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text(encoding="utf-8"))
                        if meta.get("evolution_id") == evolution_id:
                            return EvolutionArchive(**meta)
                    except Exception as e:
                        logger.warning(f"Failed to parse archive {archive_dir.name}: {e}")
        except Exception as e:
            logger.error(
                "Failed to get archive by evolution ID %s: %s",
                evolution_id,
                e,
            )
        return None

    async def enrich_archive(
        self,
        archive: EvolutionArchive,
        *,
        record: EvolutionRecord | None = None,
    ) -> EvolutionArchive:
        """Backfill missing archive details from saved evolution sessions."""
        if record is None:
            record = await self.get_record(archive.evolution_id)
        return enrich_archive_from_sessions(
            workspace_dir=self.workspace_dir,
            archive=archive,
            record=record,
        )

    async def get_archive_file(
        self,
        archive_id: str,
        filename: str,
    ) -> Optional[str]:
        """Get file content from archive."""
        try:
            for archive_dir in self.archives_dir.iterdir():
                if not archive_dir.is_dir():
                    continue
                meta_file = archive_dir / "meta.json"
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text(encoding="utf-8"))
                        if meta.get("archive_id") == archive_id:
                            file_path = archive_dir / filename
                            if file_path.exists():
                                return file_path.read_text(encoding="utf-8")
                    except Exception as e:
                        logger.warning(f"Failed to read archive file: {e}")
        except Exception as e:
            logger.error(f"Failed to get archive file {archive_id}/{filename}: {e}")
        return None

    async def delete_record(self, record_id: str) -> bool:
        """Delete a failed evolution record by ID."""
        if not self.index_file.exists():
            return False

        try:
            data = json.loads(self.index_file.read_text(encoding="utf-8"))
            records = data.get("records", [])

            # Find and remove the record
            original_length = len(records)
            records = [r for r in records if r.get("id") != record_id]

            if len(records) == original_length:
                # Record not found
                return False

            # Update and write back
            data["records"] = records
            self.index_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Try to delete associated archive if exists
            self._delete_archive_by_record_id(record_id)

            logger.info(f"Deleted evolution record: {record_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete record {record_id}: {e}")
            return False

    def _delete_archive_by_record_id(self, record_id: str) -> None:
        """Delete archive directory associated with a record ID."""
        try:
            for archive_dir in self.archives_dir.iterdir():
                if not archive_dir.is_dir():
                    continue
                meta_file = archive_dir / "meta.json"
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text(encoding="utf-8"))
                        if meta.get("evolution_id") == record_id:
                            # Delete the entire archive directory
                            import shutil
                            shutil.rmtree(archive_dir)
                            logger.info(f"Deleted archive: {archive_dir.name}")
                    except Exception as e:
                        logger.warning(f"Failed to delete archive {archive_dir.name}: {e}")
        except Exception as e:
            logger.warning(f"Failed to scan archives for deletion: {e}")
