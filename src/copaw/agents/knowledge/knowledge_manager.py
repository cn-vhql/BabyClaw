# -*- coding: utf-8 -*-
"""Knowledge base manager backed by SQLite FTS5."""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...config.knowledge_config import ChunkConfig, KnowledgeBaseConfig
from .chunk_strategies import chunk_text
from .sqlite_store import (
    DEFAULT_STORAGE_TYPE,
    ensure_store,
    replace_document_index,
    search_index,
    delete_document_index,
)

logger = logging.getLogger(__name__)


class DocumentChunk:
    """Document chunk representation."""

    def __init__(
        self,
        content: str,
        doc_id: str,
        chunk_id: str,
        metadata: dict[str, Any] | None = None,
    ):
        self.content = content
        self.doc_id = doc_id
        self.chunk_id = chunk_id
        self.metadata = metadata or {}


class Document:
    """Document representation."""

    def __init__(
        self,
        doc_id: str,
        filename: str,
        file_type: str,
        chunks: list[DocumentChunk] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.doc_id = doc_id
        self.filename = filename
        self.file_type = file_type
        self.chunks = chunks or []
        self.metadata = metadata or {}


class KnowledgeBase:
    """Knowledge base implementation backed by SQLite FTS5."""

    def __init__(
        self,
        kb_id: str,
        config: KnowledgeBaseConfig,
        working_dir: str,
        embedding_config: dict[str, Any],
    ):
        self.kb_id = kb_id
        self.config = config
        self.working_dir = Path(working_dir)
        self.embedding_config = embedding_config
        self.kb_dir = self.working_dir / "knowledge" / kb_id
        self.kb_dir.mkdir(parents=True, exist_ok=True)
        ensure_store(self.kb_dir)

        self.documents: dict[str, Document] = {}
        self._load_documents()

    def _load_documents(self) -> None:
        doc_dir = self.kb_dir / "documents"
        if not doc_dir.exists():
            return

        for meta_file in doc_dir.glob("*/meta.json"):
            try:
                with open(meta_file, "r", encoding="utf-8") as file:
                    doc_meta = json.load(file)
                doc_id = doc_meta.get("doc_id") or meta_file.parent.name
                chunks = [
                    DocumentChunk(
                        content=chunk.get("content", ""),
                        doc_id=doc_id,
                        chunk_id=chunk.get("chunk_id", ""),
                        metadata={
                            key: value
                            for key, value in chunk.items()
                            if key not in {"content", "chunk_id"}
                        },
                    )
                    for chunk in doc_meta.get("chunks", [])
                ]
                self.documents[doc_id] = Document(
                    doc_id=doc_id,
                    filename=doc_meta.get("filename", meta_file.parent.name),
                    file_type=doc_meta.get("file_type", ""),
                    chunks=chunks,
                    metadata=doc_meta,
                )
            except Exception as exc:
                logger.warning("failed to load knowledge document metadata from %s: %s", meta_file, exc)

    def add_document(
        self,
        file_path: str,
        filename: str,
        chunk_config: ChunkConfig | None = None,
    ) -> Document:
        doc_id = str(uuid.uuid4())
        file_type = Path(filename).suffix.lower()

        doc_dir = self.kb_dir / "documents" / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        target_path = doc_dir / filename
        shutil.copy2(file_path, target_path)

        doc = Document(
            doc_id=doc_id,
            filename=filename,
            file_type=file_type,
            metadata={"file_path": str(target_path)},
        )

        config = chunk_config or self.config.chunk_config
        content = self._read_file(target_path)
        chunk_payloads = chunk_text(
            text=content,
            doc_id=doc_id,
            chunk_type=config.chunk_type,
            max_length=config.max_length,
            overlap=config.overlap,
            separators=config.separators,
        )

        doc.chunks = [
            DocumentChunk(
                content=chunk.get("content", ""),
                doc_id=doc_id,
                chunk_id=chunk.get("chunk_id", ""),
                metadata={key: value for key, value in chunk.items() if key not in {"content", "chunk_id"}},
            )
            for chunk in chunk_payloads
        ]

        doc_meta = {
            "doc_id": doc_id,
            "filename": filename,
            "file_type": file_type or ".txt",
            "size": target_path.stat().st_size,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "chunk_count": len(chunk_payloads),
            "chunks": chunk_payloads,
            "indexing_status": "completed",
            "indexing_error": None,
        }
        with open(doc_dir / "meta.json", "w", encoding="utf-8") as file:
            json.dump(doc_meta, file, ensure_ascii=False, indent=2)

        replace_document_index(
            self.kb_dir,
            doc_id=doc_id,
            filename=filename,
            file_type=file_type or ".txt",
            size=target_path.stat().st_size,
            uploaded_at=str(doc_meta["uploaded_at"]),
            chunks=chunk_payloads,
        )

        self.documents[doc_id] = doc
        return doc

    def _read_file(self, file_path: Path) -> str:
        file_type = file_path.suffix.lower()
        if file_type in [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt"]:
            raise NotImplementedError(f"{file_type} reading not implemented yet")
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()

    def delete_document(self, doc_id: str) -> bool:
        if doc_id not in self.documents:
            return False

        doc_dir = self.kb_dir / "documents" / doc_id
        if doc_dir.exists():
            shutil.rmtree(doc_dir)

        delete_document_index(self.kb_dir, doc_id)
        del self.documents[doc_id]
        return True

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if self.config.storage_type != DEFAULT_STORAGE_TYPE:
            logger.warning("unsupported storage type %s, forcing sqlite", self.config.storage_type)
        return search_index(self.kb_dir, query=query, top_k=top_k)

    def get_chunks(self, doc_id: str) -> list[DocumentChunk]:
        doc = self.documents.get(doc_id)
        if not doc:
            return []
        return doc.chunks

    def update_chunk(self, doc_id: str, chunk_id: str, new_content: str) -> bool:
        doc = self.documents.get(doc_id)
        if not doc:
            return False

        for chunk in doc.chunks:
            if chunk.chunk_id == chunk_id:
                chunk.content = new_content
                return True
        return False
