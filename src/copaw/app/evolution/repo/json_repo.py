# -*- coding: utf-8 -*-
"""JSON file repository for evolution data."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

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
        """Save evolution record."""
        # Read existing data
        if self.index_file.exists():
            try:
                data = json.loads(self.index_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Failed to read index file, creating new: {e}")
                data = {"version": 1, "records": []}
        else:
            data = {"version": 1, "records": []}

        # Insert record at the beginning
        data["records"].insert(0, record.model_dump(mode="json"))

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
