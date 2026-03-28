# -*- coding: utf-8 -*-
"""Knowledge base tools backed by SQLite FTS5."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ...agents.knowledge.chunk_strategies import chunk_text
from ...agents.knowledge.sqlite_store import (
    build_default_kb_meta,
    get_index_db_path,
    replace_document_index,
    rebuild_index_from_metadata,
    search_index,
)

logger = logging.getLogger(__name__)


def _text_response(text: str) -> ToolResponse:
    return ToolResponse(content=[TextBlock(type="text", text=text)])


def knowledge_search(
    query: str,
    kb_id: str | None = None,
    top_k: int = 5,
) -> ToolResponse:
    """Search knowledge base for relevant information."""
    try:
        from ...app.agent_context import get_current_agent_id
        from ...config.config import load_agent_config

        agent_id = get_current_agent_id()
        config = load_agent_config(agent_id)
        workspace_dir = Path(config.workspace_dir)

        if kb_id:
            kb_ids = [kb_id]
        else:
            kb_root = workspace_dir / "knowledge"
            if not kb_root.exists():
                return _text_response("No knowledge bases found. Please create a knowledge base first.")
            kb_ids = [item.name for item in kb_root.iterdir() if item.is_dir()]

        all_results = []
        for current_kb_id in kb_ids:
            kb_dir = workspace_dir / "knowledge" / current_kb_id
            meta_file = kb_dir / "meta.json"
            if not kb_dir.exists() or not meta_file.exists():
                continue

            with open(meta_file, "r", encoding="utf-8") as file:
                meta = json.load(file)

            kb_name = meta.get("name", current_kb_id)
            if not get_index_db_path(kb_dir).exists():
                rebuild_index_from_metadata(kb_dir)
            for result in search_index(kb_dir, query=query, top_k=top_k):
                all_results.append(
                    {
                        "kb_name": kb_name,
                        **result,
                    }
                )

        all_results.sort(key=lambda item: item["score"], reverse=True)
        top_results = all_results[:top_k]
        if not top_results:
            return _text_response(f"No results found for query: {query}")

        result_text = (
            f"Found {len(top_results)} result(s) for query: {query} "
            "(using SQLite FTS5 + BM25)\n\n"
        )
        for index, result in enumerate(top_results, start=1):
            result_text += f"--- Result {index} ---\n"
            result_text += f"Knowledge Base: {result['kb_name']}\n"
            result_text += f"Document: {result['filename']}\n"
            result_text += f"Score: {result['score']:.4f}\n"
            result_text += f"Content:\n{result['content']}\n\n"

        return _text_response(result_text)
    except Exception as exc:
        logger.error("knowledge search failed: %s", exc, exc_info=True)
        return _text_response(f"Knowledge search failed: {exc}")


def list_knowledge_bases() -> ToolResponse:
    """List all available knowledge bases."""
    try:
        from ...app.agent_context import get_current_agent_id
        from ...config.config import load_agent_config

        agent_id = get_current_agent_id()
        config = load_agent_config(agent_id)
        workspace_dir = Path(config.workspace_dir)

        kb_dir = workspace_dir / "knowledge"
        if not kb_dir.exists():
            return _text_response("No knowledge bases found. Please create a knowledge base first.")

        kb_list = []
        for kb_path in kb_dir.iterdir():
            if not kb_path.is_dir():
                continue

            meta_file = kb_path / "meta.json"
            if not meta_file.exists():
                continue

            with open(meta_file, "r", encoding="utf-8") as file:
                meta = json.load(file)

            doc_dir = kb_path / "documents"
            doc_count = len([item for item in doc_dir.iterdir() if item.is_dir()]) if doc_dir.exists() else 0
            kb_list.append(
                {
                    "id": kb_path.name,
                    "name": meta.get("name", kb_path.name),
                    "description": meta.get("description", ""),
                    "document_count": doc_count,
                }
            )

        if not kb_list:
            return _text_response("No knowledge bases found. Please create a knowledge base first.")

        result_text = f"Found {len(kb_list)} knowledge base(s):\n\n"
        for kb in kb_list:
            result_text += f"Name: {kb['name']}\n"
            result_text += f"ID: {kb['id']}\n"
            result_text += f"Description: {kb['description']}\n"
            result_text += f"Document Count: {kb['document_count']}\n\n"

        return _text_response(result_text)
    except Exception as exc:
        logger.error("list knowledge bases failed: %s", exc, exc_info=True)
        return _text_response(f"List knowledge bases failed: {exc}")


def knowledge_write(
    content: str,
    filename: str | None = None,
    kb_id: str | None = None,
) -> ToolResponse:
    """Write text content to a knowledge base."""
    try:
        from ...app.agent_context import get_current_agent_id
        from ...config.config import load_agent_config

        agent_id = get_current_agent_id()
        config = load_agent_config(agent_id)
        workspace_dir = Path(config.workspace_dir)

        kb_root = workspace_dir / "knowledge"
        kb_root.mkdir(parents=True, exist_ok=True)

        if kb_id:
            target_kb_id = kb_id
            target_kb_dir = kb_root / kb_id
            if not target_kb_dir.exists():
                return _text_response(
                    f"Knowledge base '{kb_id}' not found. Please create it first or omit kb_id to use default."
                )
        else:
            existing_kb_ids = [item.name for item in kb_root.iterdir() if item.is_dir()]
            if existing_kb_ids:
                target_kb_id = existing_kb_ids[0]
                target_kb_dir = kb_root / target_kb_id
            else:
                target_kb_id = str(uuid.uuid4())
                target_kb_dir = kb_root / target_kb_id
                target_kb_dir.mkdir(parents=True, exist_ok=True)
                with open(target_kb_dir / "meta.json", "w", encoding="utf-8") as file:
                    json.dump(
                        build_default_kb_meta(
                            kb_id=target_kb_id,
                            name="Agent Notes",
                            description="Default knowledge base for agent-created notes",
                        ),
                        file,
                        ensure_ascii=False,
                        indent=2,
                    )

        meta_file = target_kb_dir / "meta.json"
        with open(meta_file, "r", encoding="utf-8") as file:
            kb_meta = json.load(file)

        if not filename:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"agent_note_{timestamp}.txt"

        doc_id = str(uuid.uuid4())
        doc_dir = target_kb_dir / "documents" / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        file_path = doc_dir / filename
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)

        chunk_config = kb_meta.get("chunk_config") or {
            "chunk_type": "length",
            "max_length": 500,
            "overlap": 50,
            "separators": ["\n\n", "\n", "。", ".", "!", "?", ";", "，", ",", " ", ""],
        }
        chunk_type = chunk_config.get("chunk_type", "length")
        if chunk_type not in {"length", "separator"}:
            chunk_type = "length"

        chunks = chunk_text(
            text=content,
            doc_id=doc_id,
            chunk_type=chunk_type,
            max_length=int(chunk_config.get("max_length", 500)),
            overlap=int(chunk_config.get("overlap", 50)),
            separators=chunk_config.get("separators") or ["\n\n", "\n", "。", ".", "!", "?", ";", "，", ",", " ", ""],
        )

        replace_document_index(
            target_kb_dir,
            doc_id=doc_id,
            filename=filename,
            file_type=Path(filename).suffix.lower() or ".txt",
            size=len(content.encode("utf-8")),
            uploaded_at=datetime.now(timezone.utc).isoformat(),
            chunks=chunks,
        )

        doc_meta = {
            "doc_id": doc_id,
            "filename": filename,
            "file_type": Path(filename).suffix.lower() or ".txt",
            "size": len(content.encode("utf-8")),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "chunk_count": len(chunks),
            "chunks": chunks,
            "indexing_status": "completed",
            "indexing_error": None,
        }
        with open(doc_dir / "meta.json", "w", encoding="utf-8") as file:
            json.dump(doc_meta, file, ensure_ascii=False, indent=2)

        kb_name = kb_meta.get("name", target_kb_id)
        return _text_response(
            "Content successfully saved to knowledge base "
            f"'{kb_name}' with SQLite FTS5 retrieval ready.\n"
            f"Document ID: {doc_id}\n"
            f"Filename: {filename}\n"
            f"Chunks created: {len(chunks)}\n"
            "You can search for this content later using knowledge_search."
        )
    except Exception as exc:
        logger.error("knowledge write failed: %s", exc, exc_info=True)
        return _text_response(f"Failed to save content to knowledge base: {exc}")
