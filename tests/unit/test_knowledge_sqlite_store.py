# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from copaw.agents.knowledge.chunk_strategies import chunk_text
from copaw.agents.knowledge.sqlite_store import (
    rebuild_index_from_metadata,
    replace_document_index,
    search_index,
)


class KnowledgeSQLiteStoreTests(unittest.TestCase):
    def test_replace_document_index_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            kb_dir = Path(tmp_dir) / "knowledge" / "kb1"
            kb_dir.mkdir(parents=True, exist_ok=True)

            chunks = chunk_text(
                text="Docker restart policy keeps the service alive during failures.",
                doc_id="doc1",
                chunk_type="length",
                max_length=80,
                overlap=0,
            )

            indexed_count = replace_document_index(
                kb_dir,
                doc_id="doc1",
                filename="ops.md",
                file_type=".md",
                size=128,
                uploaded_at="2026-03-28T00:00:00+00:00",
                chunks=chunks,
            )

            results = search_index(kb_dir, query="docker failures", top_k=5)

        self.assertEqual(indexed_count, 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["doc_id"], "doc1")
        self.assertEqual(results[0]["filename"], "ops.md")

    def test_rebuild_index_from_metadata_bootstraps_existing_documents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            kb_dir = Path(tmp_dir) / "knowledge" / "kb2"
            doc_dir = kb_dir / "documents" / "doc2"
            doc_dir.mkdir(parents=True, exist_ok=True)

            chunks = chunk_text(
                text="Release checklist includes smoke tests and rollback notes.",
                doc_id="doc2",
                chunk_type="separator",
                max_length=80,
                overlap=0,
                separators=[" and ", "."],
            )
            with open(doc_dir / "meta.json", "w", encoding="utf-8") as file:
                json.dump(
                    {
                        "doc_id": "doc2",
                        "filename": "release.txt",
                        "file_type": ".txt",
                        "size": 64,
                        "uploaded_at": "2026-03-28T00:00:00+00:00",
                        "chunk_count": len(chunks),
                        "chunks": chunks,
                        "indexing_status": "completed",
                        "indexing_error": None,
                    },
                    file,
                    ensure_ascii=False,
                    indent=2,
                )

            rebuilt = rebuild_index_from_metadata(kb_dir)
            results = search_index(kb_dir, query="rollback notes", top_k=5)

        self.assertEqual(rebuilt, 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["doc_id"], "doc2")
        self.assertEqual(results[0]["filename"], "release.txt")
