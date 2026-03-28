# -*- coding: utf-8 -*-
"""SQLite FTS5 store helpers for knowledge base indexing and retrieval."""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import jieba

    _JIEBA_AVAILABLE = True
except ImportError:  # pragma: no cover - fallback for environments without deps refreshed
    jieba = None
    _JIEBA_AVAILABLE = False

logger = logging.getLogger(__name__)

DEFAULT_STORAGE_TYPE = "sqlite"
DEFAULT_CHUNK_TYPE = "length"
DEFAULT_CHUNK_MAX_LENGTH = 500
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_CHUNK_SEPARATORS = [
    "\n\n",
    "\n",
    "。",
    ".",
    "!",
    "?",
    ";",
    "，",
    ",",
    " ",
    "",
]


def build_default_chunk_config() -> dict[str, Any]:
    """Return the default chunk configuration."""
    return {
        "chunk_type": DEFAULT_CHUNK_TYPE,
        "max_length": DEFAULT_CHUNK_MAX_LENGTH,
        "overlap": DEFAULT_CHUNK_OVERLAP,
        "separators": list(DEFAULT_CHUNK_SEPARATORS),
    }


def build_default_kb_meta(kb_id: str, name: str, description: str = "") -> dict[str, Any]:
    """Build the default metadata payload for a knowledge base."""
    return {
        "id": kb_id,
        "name": name,
        "description": description,
        "storage_type": DEFAULT_STORAGE_TYPE,
        "search_backend": "sqlite_fts5_bm25",
        "tokenizer": "jieba",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "chunk_config": build_default_chunk_config(),
    }


def get_index_db_path(kb_dir: Path | str) -> Path:
    """Return the SQLite database path for a knowledge base."""
    return Path(kb_dir) / "knowledge.sqlite3"


def _connect(db_path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_store(kb_dir: Path | str) -> Path:
    """Ensure the SQLite store exists and return its path."""
    db_path = get_index_db_path(kb_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with _connect(db_path) as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS indexed_documents (
                doc_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_type TEXT,
                size INTEGER NOT NULL DEFAULT 0,
                uploaded_at TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS indexed_chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                tokenized_content TEXT NOT NULL,
                tokenized_filename TEXT NOT NULL,
                FOREIGN KEY (doc_id) REFERENCES indexed_documents(doc_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_indexed_chunks_doc_id
            ON indexed_chunks(doc_id);

            CREATE VIRTUAL TABLE IF NOT EXISTS indexed_chunks_fts USING fts5(
                tokenized_filename,
                tokenized_content,
                chunk_id UNINDEXED,
                doc_id UNINDEXED,
                tokenize='unicode61 remove_diacritics 0'
            );
            """
        )
        conn.commit()

    return db_path


def tokenize_text(text: str) -> str:
    """Tokenize text for FTS indexing using jieba when available."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return ""

    if _JIEBA_AVAILABLE and jieba is not None:
        tokens = [token.strip().lower() for token in jieba.cut_for_search(cleaned) if token.strip()]
        return " ".join(tokens)

    logger.warning("jieba is not installed, falling back to regex tokenizer for knowledge search")
    tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", cleaned.lower())
    return " ".join(tokens)


def build_match_query(query: str) -> str:
    """Build a safe FTS5 MATCH query from raw user input."""
    tokenized_query = tokenize_text(query)
    terms = []
    seen = set()
    for term in tokenized_query.split():
        escaped = term.replace('"', '""').strip()
        if not escaped or escaped in seen:
            continue
        seen.add(escaped)
        terms.append(f'"{escaped}"')

    if not terms:
        return ""

    return " OR ".join(terms[:24])


def replace_document_index(
    kb_dir: Path | str,
    *,
    doc_id: str,
    filename: str,
    file_type: str,
    size: int,
    uploaded_at: str,
    chunks: list[dict[str, Any]],
) -> int:
    """Replace the indexed chunks for a document."""
    db_path = ensure_store(kb_dir)
    tokenized_filename = tokenize_text(filename)
    updated_at = datetime.now(timezone.utc).isoformat()

    with _connect(db_path) as conn:
        conn.execute("DELETE FROM indexed_chunks_fts WHERE doc_id = ?", (doc_id,))
        conn.execute("DELETE FROM indexed_chunks WHERE doc_id = ?", (doc_id,))
        conn.execute(
            """
            INSERT INTO indexed_documents (
                doc_id, filename, file_type, size, uploaded_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
                filename = excluded.filename,
                file_type = excluded.file_type,
                size = excluded.size,
                uploaded_at = excluded.uploaded_at,
                updated_at = excluded.updated_at
            """,
            (doc_id, filename, file_type, size, uploaded_at, updated_at),
        )

        indexed_count = 0
        for chunk in chunks:
            content = (chunk.get("content") or "").strip()
            chunk_id = chunk.get("chunk_id")
            if not content or not chunk_id:
                continue

            tokenized_content = tokenize_text(content)
            conn.execute(
                """
                INSERT OR REPLACE INTO indexed_chunks (
                    chunk_id, doc_id, chunk_index, content, tokenized_content, tokenized_filename
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    doc_id,
                    int(chunk.get("chunk_index", indexed_count)),
                    content,
                    tokenized_content,
                    tokenized_filename,
                ),
            )
            conn.execute(
                """
                INSERT INTO indexed_chunks_fts (
                    tokenized_filename, tokenized_content, chunk_id, doc_id
                ) VALUES (?, ?, ?, ?)
                """,
                (tokenized_filename, tokenized_content, chunk_id, doc_id),
            )
            indexed_count += 1

        conn.commit()

    return indexed_count


def delete_document_index(kb_dir: Path | str, doc_id: str) -> None:
    """Delete a document and all indexed chunks from the SQLite store."""
    db_path = ensure_store(kb_dir)
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM indexed_chunks_fts WHERE doc_id = ?", (doc_id,))
        conn.execute("DELETE FROM indexed_chunks WHERE doc_id = ?", (doc_id,))
        conn.execute("DELETE FROM indexed_documents WHERE doc_id = ?", (doc_id,))
        conn.commit()


def rebuild_index_from_metadata(kb_dir: Path | str) -> int:
    """Rebuild the SQLite store from document metadata on disk."""
    kb_path = Path(kb_dir)
    doc_dir = kb_path / "documents"
    if not doc_dir.exists():
        ensure_store(kb_path)
        return 0

    indexed_docs = 0
    for doc_path in doc_dir.iterdir():
        if not doc_path.is_dir():
            continue
        doc_meta_file = doc_path / "meta.json"
        if not doc_meta_file.exists():
            continue

        try:
            import json

            with open(doc_meta_file, "r", encoding="utf-8") as file:
                doc_meta = json.load(file)

            replace_document_index(
                kb_path,
                doc_id=doc_meta.get("doc_id") or doc_path.name,
                filename=doc_meta.get("filename") or doc_path.name,
                file_type=doc_meta.get("file_type") or "",
                size=int(doc_meta.get("size") or 0),
                uploaded_at=doc_meta.get("uploaded_at") or "",
                chunks=doc_meta.get("chunks") or [],
            )
            indexed_docs += 1
        except Exception as exc:  # pragma: no cover - defensive per-document recovery
            logger.warning("failed to rebuild document index for %s: %s", doc_path, exc)

    return indexed_docs


def search_index(kb_dir: Path | str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Search indexed chunks using SQLite FTS5 + BM25."""
    if top_k <= 0:
        return []

    match_query = build_match_query(query)
    if not match_query:
        return []

    db_path = ensure_store(kb_dir)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                c.doc_id,
                d.filename,
                c.chunk_id,
                c.content,
                bm25(indexed_chunks_fts, 3.0, 1.0) AS rank
            FROM indexed_chunks_fts
            JOIN indexed_chunks AS c ON c.chunk_id = indexed_chunks_fts.chunk_id
            JOIN indexed_documents AS d ON d.doc_id = c.doc_id
            WHERE indexed_chunks_fts MATCH ?
            ORDER BY rank ASC
            LIMIT ?
            """,
            (match_query, int(top_k)),
        ).fetchall()

    query_lower = (query or "").strip().lower()
    results = []
    for row in rows:
        rank = float(row["rank"])
        score = -rank if rank < 0 else 1.0 / (1.0 + rank)
        content = str(row["content"])
        filename = str(row["filename"])

        if query_lower and query_lower in content.lower():
            score += 0.4
        if query_lower and query_lower in filename.lower():
            score += 0.2

        results.append(
            {
                "doc_id": str(row["doc_id"]),
                "filename": filename,
                "chunk_id": str(row["chunk_id"]),
                "content": content,
                "score": round(score, 6),
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]
