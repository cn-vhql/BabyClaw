# -*- coding: utf-8 -*-
"""Knowledge base manager for CoPaw agents."""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from ...config.knowledge_config import (
    AgentKnowledgeConfig,
    ChunkConfig,
    KnowledgeBaseConfig,
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
    """Knowledge base implementation."""

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

        # Initialize storage
        self.collection = self._init_storage()

        # Load documents
        self.documents: dict[str, Document] = {}
        self._load_documents()

    def _init_storage(self):
        """Initialize storage backend."""
        if self.config.storage_type == "chroma":
            persist_dir = self.kb_dir / "chroma"
            persist_dir.mkdir(exist_ok=True)

            client = chromadb.PersistentClient(
                path=str(persist_dir),
                settings=Settings(anonymized_telemetry=False),
            )

            return client.get_or_create_collection(
                name=self.kb_id,
                metadata={"hnsw:space": "cosine"},
            )
        else:
            # TODO: Implement SQLite storage
            raise NotImplementedError("SQLite storage not implemented yet")

    def _load_documents(self):
        """Load documents from storage."""
        meta_file = self.kb_dir / "documents.json"
        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for doc_data in data.get("documents", []):
                    doc = Document(
                        doc_id=doc_data["doc_id"],
                        filename=doc_data["filename"],
                        file_type=doc_data["file_type"],
                        metadata=doc_data.get("metadata", {}),
                    )
                    self.documents[doc.doc_id] = doc

    def _save_documents(self):
        """Save documents metadata."""
        meta_file = self.kb_dir / "documents.json"
        data = {
            "documents": [
                {
                    "doc_id": doc.doc_id,
                    "filename": doc.filename,
                    "file_type": doc.file_type,
                    "metadata": doc.metadata,
                }
                for doc in self.documents.values()
            ]
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_document(
        self,
        file_path: str,
        filename: str,
        chunk_config: ChunkConfig | None = None,
    ) -> Document:
        """Add and process a document."""
        import uuid

        doc_id = str(uuid.uuid4())
        file_type = Path(filename).suffix.lower()

        # Copy file to knowledge base
        doc_dir = self.kb_dir / "documents" / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        target_path = doc_dir / filename
        shutil.copy2(file_path, target_path)

        # Create document
        doc = Document(
            doc_id=doc_id,
            filename=filename,
            file_type=file_type,
            metadata={"file_path": str(target_path)},
        )

        # Chunk document
        chunk_config = chunk_config or self.config.chunk_config
        doc.chunks = self._chunk_document(target_path, doc_id, chunk_config)

        # Index chunks
        self._index_chunks(doc)

        # Save document
        self.documents[doc_id] = doc
        self._save_documents()

        return doc

    def _chunk_document(
        self,
        file_path: Path,
        doc_id: str,
        config: ChunkConfig,
    ) -> list[DocumentChunk]:
        """Chunk document based on configuration."""
        # Read file content
        content = self._read_file(file_path)

        chunks = []

        if config.chunk_type == "length":
            chunks = self._chunk_by_length(content, doc_id, config)
        else:  # separator
            chunks = self._chunk_by_separator(content, doc_id, config)

        return chunks

    def _read_file(self, file_path: Path) -> str:
        """Read file content based on type."""
        file_type = file_path.suffix.lower()

        if file_type == ".pdf":
            # TODO: Implement PDF reading
            raise NotImplementedError("PDF reading not implemented yet")
        elif file_type in [".docx", ".doc"]:
            # TODO: Implement DOCX reading
            raise NotImplementedError("DOCX reading not implemented yet")
        elif file_type in [".xlsx", ".xls"]:
            # TODO: Implement XLSX reading
            raise NotImplementedError("XLSX reading not implemented yet")
        elif file_type in [".pptx", ".ppt"]:
            # TODO: Implement PPTX reading
            raise NotImplementedError("PPTX reading not implemented yet")
        else:  # Text files
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()

    def _chunk_by_length(
        self,
        content: str,
        doc_id: str,
        config: ChunkConfig,
    ) -> list[DocumentChunk]:
        """Chunk by max length."""
        chunks = []
        start = 0
        chunk_idx = 0

        while start < len(content):
            end = start + config.max_length
            chunk_content = content[start:end]

            chunk = DocumentChunk(
                content=chunk_content,
                doc_id=doc_id,
                chunk_id=f"{doc_id}_chunk_{chunk_idx}",
                metadata={"chunk_index": chunk_idx, "start": start, "end": end},
            )
            chunks.append(chunk)

            start = end - config.overlap
            chunk_idx += 1

        return chunks

    def _chunk_by_separator(
        self,
        content: str,
        doc_id: str,
        config: ChunkConfig,
    ) -> list[DocumentChunk]:
        """Chunk by separators."""
        import re

        chunks = []
        chunk_idx = 0

        # Try separators in order
        for sep in config.separators:
            if sep in content:
                parts = re.split(f"({re.escape(sep)})", content)
                current_chunk = ""

                for i, part in enumerate(parts):
                    current_chunk += part

                    # Check if we hit a separator and have enough content
                    if part == sep and len(current_chunk) > 0:
                        if len(current_chunk) >= config.max_length * 0.5:
                            chunk = DocumentChunk(
                                content=current_chunk,
                                doc_id=doc_id,
                                chunk_id=f"{doc_id}_chunk_{chunk_idx}",
                                metadata={"chunk_index": chunk_idx, "separator": sep},
                            )
                            chunks.append(chunk)
                            chunk_idx += 1
                            current_chunk = ""

                # Add remaining content
                if current_chunk:
                    chunk = DocumentChunk(
                        content=current_chunk,
                        doc_id=doc_id,
                        chunk_id=f"{doc_id}_chunk_{chunk_idx}",
                        metadata={"chunk_index": chunk_idx},
                    )
                    chunks.append(chunk)

                break

        # Fallback to length chunking if no separator found
        if not chunks:
            return self._chunk_by_length(content, doc_id, config)

        return chunks

    def _index_chunks(self, doc: Document):
        """Index chunks in vector database."""
        if not self.embedding_config.get("api_key"):
            logger.warning("Embedding not configured, skipping vector indexing")
            return

        # TODO: Implement embedding and indexing
        # This would call the embedding API and add to ChromaDB
        pass

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document."""
        if doc_id not in self.documents:
            return False

        doc = self.documents[doc_id]

        # Delete from storage
        if self.config.storage_type == "chroma":
            # Delete chunks from collection
            try:
                self.collection.delete(where={"doc_id": doc_id})
            except Exception as e:
                logger.error(f"Failed to delete chunks from ChromaDB: {e}")

        # Delete file
        doc_dir = self.kb_dir / "documents" / doc_id
        if doc_dir.exists():
            shutil.rmtree(doc_dir)

        # Remove from documents
        del self.documents[doc_id]
        self._save_documents()

        return True

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search knowledge base."""
        results = []

        if self.config.storage_type == "chroma":
            # Vector search
            if self.embedding_config.get("api_key"):
                try:
                    # TODO: Implement embedding query
                    # results = self.collection.query(...)
                    pass
                except Exception as e:
                    logger.error(f"Vector search failed: {e}")

        # TODO: Implement BM25 search
        # Merge vector and BM25 results

        return results

    def get_chunks(self, doc_id: str) -> list[DocumentChunk]:
        """Get chunks for a document."""
        doc = self.documents.get(doc_id)
        if not doc:
            return []
        return doc.chunks

    def update_chunk(self, doc_id: str, chunk_id: str, new_content: str) -> bool:
        """Update a chunk's content."""
        doc = self.documents.get(doc_id)
        if not doc:
            return False

        for chunk in doc.chunks:
            if chunk.chunk_id == chunk_id:
                chunk.content = new_content

                # Re-index in storage
                # TODO: Update in ChromaDB

                return True

        return False
