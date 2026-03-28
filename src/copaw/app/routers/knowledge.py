# -*- coding: utf-8 -*-
"""Knowledge base API routes backed by SQLite FTS5."""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from ...agents.knowledge.chunk_strategies import chunk_text
from ...agents.knowledge.sqlite_store import (
    DEFAULT_CHUNK_SEPARATORS,
    DEFAULT_STORAGE_TYPE,
    build_default_chunk_config,
    build_default_kb_meta,
    delete_document_index,
    ensure_store,
    get_index_db_path,
    rebuild_index_from_metadata,
    replace_document_index,
    search_index,
)
from ..agent_context import get_agent_for_request

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
logger = logging.getLogger(__name__)

TEXT_FILE_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".csv",
    ".log",
    ".yaml",
    ".yml",
    ".xml",
}


class KnowledgeBaseCreate(BaseModel):
    """Knowledge base creation request."""

    name: str = Field(..., description="Knowledge base name")
    description: str = Field(default="", description="Knowledge base description")


def _now_isoformat() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _normalize_document_meta(doc_path: Path, doc_meta: dict[str, Any]) -> dict[str, Any]:
    """Return a stable document payload for the frontend."""
    files = doc_meta.get("files")
    primary_file = files[0] if isinstance(files, list) and files else {}

    filename = (
        doc_meta.get("filename")
        or primary_file.get("filename")
        or doc_meta.get("title")
        or doc_path.name
    )
    file_type = doc_meta.get("file_type") or primary_file.get("type")
    if not file_type and filename:
        file_type = Path(str(filename)).suffix.lstrip(".").lower() or None

    chunks = doc_meta.get("chunks")
    chunk_count = doc_meta.get("chunk_count")
    if chunk_count is None:
        chunk_count = len(chunks) if isinstance(chunks, list) else 0

    return {
        "doc_id": doc_meta.get("doc_id") or doc_meta.get("id") or doc_path.name,
        "filename": filename,
        "file_type": file_type,
        "size": doc_meta.get("size", 0),
        "uploaded_at": doc_meta.get("uploaded_at") or doc_meta.get("created_at"),
        "chunk_count": chunk_count,
        "indexing_status": doc_meta.get("indexing_status"),
        "indexing_error": doc_meta.get("indexing_error"),
    }


def _load_kb_meta(kb_dir: Path) -> dict[str, Any]:
    meta_file = kb_dir / "meta.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return _load_json(meta_file)


def _load_doc_meta(doc_dir: Path) -> dict[str, Any]:
    doc_meta_file = doc_dir / "meta.json"
    if not doc_meta_file.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    return _load_json(doc_meta_file)


def _find_content_file(doc_dir: Path) -> Path:
    content_files = [candidate for candidate in doc_dir.iterdir() if candidate.name != "meta.json"]
    if not content_files:
        raise HTTPException(status_code=400, detail="No content file found")
    return content_files[0]


def _read_supported_text_file(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix not in TEXT_FILE_SUFFIXES:
        raise ValueError(f"File type {suffix or 'unknown'} is not supported for text indexing")

    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


def _normalize_chunk_config(
    kb_meta: dict[str, Any],
    *,
    chunk_type: str | None = None,
    max_length: int | None = None,
    overlap: int | None = None,
    separators: str | None = None,
) -> dict[str, Any]:
    base_config = kb_meta.get("chunk_config") or build_default_chunk_config()
    chosen_chunk_type = chunk_type or base_config.get("chunk_type", "length")
    if chosen_chunk_type not in {"length", "separator"}:
        chosen_chunk_type = "length"

    separator_list = base_config.get("separators") or list(DEFAULT_CHUNK_SEPARATORS)
    if separators:
        try:
            parsed = json.loads(separators)
            if isinstance(parsed, list) and parsed:
                separator_list = [str(item) for item in parsed]
        except json.JSONDecodeError:
            logger.warning("invalid separators JSON %r, using default separators", separators)

    normalized_max_length = max(1, int(max_length) if max_length is not None else int(base_config.get("max_length", 500)))
    normalized_overlap = overlap if overlap is not None else int(base_config.get("overlap", 50))
    normalized_overlap = max(0, min(int(normalized_overlap), normalized_max_length - 1))

    return {
        "chunk_type": chosen_chunk_type,
        "max_length": normalized_max_length,
        "overlap": normalized_overlap,
        "separators": separator_list,
    }


def _normalize_chunks(chunks: list[dict[str, Any]], doc_id: str) -> list[dict[str, Any]]:
    normalized = []
    for index, chunk in enumerate(chunks):
        content = (chunk.get("content") or "").strip()
        if not content:
            continue
        normalized.append(
            {
                **chunk,
                "chunk_id": chunk.get("chunk_id") or f"{doc_id}_chunk_{index}",
                "chunk_index": index,
                "content": content,
            }
        )
    return normalized


def _build_index_payload(
    *,
    doc_id: str,
    filename: str,
    file_type: str,
    size: int,
    uploaded_at: str,
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "filename": filename,
        "file_type": file_type,
        "size": size,
        "uploaded_at": uploaded_at,
        "chunk_count": len(chunks),
        "chunks": chunks,
        "indexing_status": "completed",
        "indexing_error": None,
    }


def _index_document(
    *,
    kb_dir: Path,
    doc_id: str,
    filename: str,
    file_path: Path,
    chunk_config: dict[str, Any],
    uploaded_at: str,
) -> dict[str, Any]:
    file_content = _read_supported_text_file(file_path)
    chunks = chunk_text(
        text=file_content,
        doc_id=doc_id,
        chunk_type=chunk_config["chunk_type"],
        max_length=chunk_config["max_length"],
        overlap=chunk_config["overlap"],
        separators=chunk_config["separators"],
    )
    normalized_chunks = _normalize_chunks(chunks, doc_id)
    file_type = file_path.suffix.lower() or ".txt"
    size = file_path.stat().st_size

    replace_document_index(
        kb_dir,
        doc_id=doc_id,
        filename=filename,
        file_type=file_type,
        size=size,
        uploaded_at=uploaded_at,
        chunks=normalized_chunks,
    )

    return _build_index_payload(
        doc_id=doc_id,
        filename=filename,
        file_type=file_type,
        size=size,
        uploaded_at=uploaded_at,
        chunks=normalized_chunks,
    )


async def _index_document_in_background(
    *,
    workspace_dir: str,
    kb_id: str,
    doc_id: str,
    file_path: str,
    filename: str,
    chunk_config: dict[str, Any],
) -> None:
    """Background task that chunks and indexes a document."""
    kb_dir = Path(workspace_dir) / "knowledge" / kb_id
    doc_dir = kb_dir / "documents" / doc_id
    doc_meta_file = doc_dir / "meta.json"

    try:
        doc_meta = _load_json(doc_meta_file)
        doc_meta["indexing_status"] = "processing"
        doc_meta["indexing_error"] = None
        _write_json(doc_meta_file, doc_meta)

        indexed_meta = _index_document(
            kb_dir=kb_dir,
            doc_id=doc_id,
            filename=filename,
            file_path=Path(file_path),
            chunk_config=chunk_config,
            uploaded_at=doc_meta.get("uploaded_at") or _now_isoformat(),
        )

        doc_meta.update(indexed_meta)
        _write_json(doc_meta_file, doc_meta)
        logger.info("document indexing completed: %s/%s", kb_id, doc_id)
    except Exception as exc:
        logger.error("document indexing failed for %s/%s: %s", kb_id, doc_id, exc, exc_info=True)
        try:
            doc_meta = _load_json(doc_meta_file)
            doc_meta["indexing_status"] = "failed"
            doc_meta["indexing_error"] = str(exc)
            _write_json(doc_meta_file, doc_meta)
        except Exception:
            logger.exception("failed to mark document indexing error for %s/%s", kb_id, doc_id)


@router.get("/list")
async def list_knowledge_bases(request: Request) -> dict[str, Any]:
    """List all knowledge bases."""
    try:
        workspace = await get_agent_for_request(request)
        kb_dir = workspace.workspace_dir / "knowledge"

        knowledge_bases = []
        if kb_dir.exists():
            for kb_path in kb_dir.iterdir():
                if not kb_path.is_dir():
                    continue
                meta_file = kb_path / "meta.json"
                if not meta_file.exists():
                    continue

                meta = _load_json(meta_file)
                documents_dir = kb_path / "documents"
                document_count = len([item for item in documents_dir.iterdir() if item.is_dir()]) if documents_dir.exists() else 0
                knowledge_bases.append(
                    {
                        "id": kb_path.name,
                        "name": meta.get("name", kb_path.name),
                        "description": meta.get("description", ""),
                        "storage_type": meta.get("storage_type", DEFAULT_STORAGE_TYPE),
                        "created_at": meta.get("created_at", ""),
                        "document_count": document_count,
                    }
                )

        return {"knowledge_bases": knowledge_bases}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/create")
async def create_knowledge_base(request: Request, data: KnowledgeBaseCreate) -> dict[str, Any]:
    """Create a new knowledge base."""
    try:
        workspace = await get_agent_for_request(request)
        kb_id = str(uuid.uuid4())
        kb_dir = workspace.workspace_dir / "knowledge" / kb_id
        kb_dir.mkdir(parents=True, exist_ok=True)

        meta = build_default_kb_meta(kb_id=kb_id, name=data.name, description=data.description)
        _write_json(kb_dir / "meta.json", meta)
        ensure_store(kb_dir)

        return {"id": kb_id, "name": data.name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{kb_id}")
async def delete_knowledge_base(request: Request, kb_id: str) -> dict[str, Any]:
    """Delete a knowledge base."""
    try:
        workspace = await get_agent_for_request(request)
        kb_dir = workspace.workspace_dir / "knowledge" / kb_id
        if not kb_dir.exists():
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        shutil.rmtree(kb_dir)
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{kb_id}/detail")
async def get_knowledge_base_detail(request: Request, kb_id: str) -> dict[str, Any]:
    """Get knowledge base detail."""
    try:
        workspace = await get_agent_for_request(request)
        kb_dir = workspace.workspace_dir / "knowledge" / kb_id
        if not kb_dir.exists():
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        meta = _load_kb_meta(kb_dir)
        documents = []
        doc_dir = kb_dir / "documents"
        if doc_dir.exists():
            for doc_path in doc_dir.iterdir():
                if not doc_path.is_dir():
                    continue
                doc_meta_file = doc_path / "meta.json"
                if not doc_meta_file.exists():
                    continue
                documents.append(_normalize_document_meta(doc_path, _load_json(doc_meta_file)))

        return {
            "id": kb_id,
            "name": meta.get("name", ""),
            "description": meta.get("description", ""),
            "storage_type": meta.get("storage_type", DEFAULT_STORAGE_TYPE),
            "chunk_config": meta.get("chunk_config", build_default_chunk_config()),
            "created_at": meta.get("created_at", ""),
            "documents": documents,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{kb_id}/upload")
async def upload_document(
    request: Request,
    kb_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    chunk_type: str | None = Form(None),
    max_length: int | None = Form(None),
    overlap: int | None = Form(None),
    separators: str | None = Form(None),
) -> dict[str, Any]:
    """Upload a document to the knowledge base and index it in the background."""
    try:
        workspace = await get_agent_for_request(request)
        kb_dir = workspace.workspace_dir / "knowledge" / kb_id
        if not kb_dir.exists():
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        content = await file.read()
        file_size = len(content)
        max_file_size = 10 * 1024 * 1024
        if file_size > max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {max_file_size // (1024 * 1024)}MB",
            )

        kb_meta = _load_kb_meta(kb_dir)
        chunk_config = _normalize_chunk_config(
            kb_meta,
            chunk_type=chunk_type,
            max_length=max_length,
            overlap=overlap,
            separators=separators,
        )

        doc_id = str(uuid.uuid4())
        doc_dir = kb_dir / "documents" / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        file_path = doc_dir / file.filename
        with open(file_path, "wb") as output:
            output.write(content)

        doc_meta = {
            "doc_id": doc_id,
            "filename": file.filename,
            "file_type": file_path.suffix.lower() or ".txt",
            "size": file_size,
            "uploaded_at": _now_isoformat(),
            "chunk_count": 0,
            "chunks": [],
            "indexing_status": "pending",
            "indexing_error": None,
        }
        _write_json(doc_dir / "meta.json", doc_meta)

        background_tasks.add_task(
            _index_document_in_background,
            workspace_dir=str(workspace.workspace_dir),
            kb_id=kb_id,
            doc_id=doc_id,
            file_path=str(file_path),
            filename=file.filename,
            chunk_config=chunk_config,
        )

        return {
            "doc_id": doc_id,
            "filename": file.filename,
            "chunk_count": 0,
            "indexing_status": "pending",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("knowledge upload failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{kb_id}/documents/{doc_id}/reindex")
async def reindex_document(
    request: Request,
    kb_id: str,
    doc_id: str,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Re-chunk and reindex a document."""
    try:
        workspace = await get_agent_for_request(request)
        kb_dir = workspace.workspace_dir / "knowledge" / kb_id
        doc_dir = kb_dir / "documents" / doc_id
        if not doc_dir.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        kb_meta = _load_kb_meta(kb_dir)
        chunk_config = _normalize_chunk_config(kb_meta)
        doc_meta_file = doc_dir / "meta.json"
        doc_meta = _load_doc_meta(doc_dir)
        doc_meta["indexing_status"] = "processing"
        doc_meta["indexing_error"] = None
        _write_json(doc_meta_file, doc_meta)

        content_file = _find_content_file(doc_dir)
        background_tasks.add_task(
            _index_document_in_background,
            workspace_dir=str(workspace.workspace_dir),
            kb_id=kb_id,
            doc_id=doc_id,
            file_path=str(content_file),
            filename=doc_meta.get("filename") or content_file.name,
            chunk_config=chunk_config,
        )

        return {
            "doc_id": doc_id,
            "filename": doc_meta.get("filename", content_file.name),
            "indexing_status": "processing",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("knowledge reindex failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(request: Request, kb_id: str, doc_id: str) -> dict[str, Any]:
    """Delete a document from the knowledge base."""
    try:
        workspace = await get_agent_for_request(request)
        kb_dir = workspace.workspace_dir / "knowledge" / kb_id
        doc_dir = kb_dir / "documents" / doc_id
        if not doc_dir.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        delete_document_index(kb_dir, doc_id)
        shutil.rmtree(doc_dir)
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{kb_id}/documents/{doc_id}/chunks")
async def get_document_chunks(request: Request, kb_id: str, doc_id: str) -> dict[str, Any]:
    """Get document chunks."""
    try:
        workspace = await get_agent_for_request(request)
        doc_dir = workspace.workspace_dir / "knowledge" / kb_id / "documents" / doc_id
        doc_meta = _load_doc_meta(doc_dir)
        return {"chunks": doc_meta.get("chunks", [])}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{kb_id}/documents/{doc_id}/status")
async def get_document_indexing_status(request: Request, kb_id: str, doc_id: str) -> dict[str, Any]:
    """Get document indexing status."""
    try:
        workspace = await get_agent_for_request(request)
        doc_dir = workspace.workspace_dir / "knowledge" / kb_id / "documents" / doc_id
        doc_meta = _load_doc_meta(doc_dir)
        return {
            "doc_id": doc_id,
            "indexing_status": doc_meta.get("indexing_status", "unknown"),
            "chunk_count": doc_meta.get("chunk_count", 0),
            "indexing_error": doc_meta.get("indexing_error"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/{kb_id}/documents/{doc_id}/chunks/{chunk_id}")
async def update_chunk(
    request: Request,
    kb_id: str,
    doc_id: str,
    chunk_id: str,
    content: str = Body(..., embed=True),
) -> dict[str, Any]:
    """Update a chunk without immediately rebuilding the search index."""
    try:
        workspace = await get_agent_for_request(request)
        doc_dir = workspace.workspace_dir / "knowledge" / kb_id / "documents" / doc_id
        doc_meta_file = doc_dir / "meta.json"
        doc_meta = _load_doc_meta(doc_dir)

        updated = False
        for chunk in doc_meta.get("chunks", []):
            if chunk.get("chunk_id") == chunk_id:
                chunk["content"] = content
                updated = True
                break

        if not updated:
            raise HTTPException(status_code=404, detail="Chunk not found")

        doc_meta["indexing_status"] = "pending"
        doc_meta["indexing_error"] = None
        _write_json(doc_meta_file, doc_meta)
        return {"updated": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{kb_id}/documents/{doc_id}/chunks/save")
async def save_chunks_and_reindex(request: Request, kb_id: str, doc_id: str) -> dict[str, Any]:
    """Save edited chunks and rebuild the SQLite FTS index for the document."""
    try:
        workspace = await get_agent_for_request(request)
        kb_dir = workspace.workspace_dir / "knowledge" / kb_id
        doc_dir = kb_dir / "documents" / doc_id
        doc_meta_file = doc_dir / "meta.json"
        doc_meta = _load_doc_meta(doc_dir)

        chunks = _normalize_chunks(doc_meta.get("chunks", []), doc_id)
        doc_meta["chunks"] = chunks
        doc_meta["chunk_count"] = len(chunks)
        doc_meta["indexing_status"] = "completed"
        doc_meta["indexing_error"] = None

        replace_document_index(
            kb_dir,
            doc_id=doc_id,
            filename=doc_meta.get("filename", ""),
            file_type=doc_meta.get("file_type", ""),
            size=int(doc_meta.get("size") or 0),
            uploaded_at=doc_meta.get("uploaded_at") or _now_isoformat(),
            chunks=chunks,
        )
        _write_json(doc_meta_file, doc_meta)

        return {"updated": True, "indexed_chunk_count": len(chunks)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{kb_id}/documents/{doc_id}/chunks")
async def add_chunk(
    request: Request,
    kb_id: str,
    doc_id: str,
    content: str = Body(..., embed=True),
) -> dict[str, Any]:
    """Add a new chunk to a document."""
    try:
        workspace = await get_agent_for_request(request)
        doc_dir = workspace.workspace_dir / "knowledge" / kb_id / "documents" / doc_id
        doc_meta_file = doc_dir / "meta.json"
        doc_meta = _load_doc_meta(doc_dir)

        chunks = doc_meta.get("chunks", [])
        new_chunk = {
            "chunk_id": f"{doc_id}_chunk_{uuid.uuid4().hex[:8]}",
            "content": content,
            "chunk_index": len(chunks),
            "strategy": "manual",
        }
        chunks.append(new_chunk)
        doc_meta["chunks"] = chunks
        doc_meta["chunk_count"] = len(chunks)
        doc_meta["indexing_status"] = "pending"
        doc_meta["indexing_error"] = None
        _write_json(doc_meta_file, doc_meta)

        return {"added": True, "chunk_id": new_chunk["chunk_id"]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{kb_id}/documents/{doc_id}/chunks/{chunk_id}")
async def delete_chunk(request: Request, kb_id: str, doc_id: str, chunk_id: str) -> dict[str, Any]:
    """Delete a chunk from a document."""
    try:
        workspace = await get_agent_for_request(request)
        doc_dir = workspace.workspace_dir / "knowledge" / kb_id / "documents" / doc_id
        doc_meta_file = doc_dir / "meta.json"
        doc_meta = _load_doc_meta(doc_dir)

        original_chunks = doc_meta.get("chunks", [])
        filtered_chunks = [chunk for chunk in original_chunks if chunk.get("chunk_id") != chunk_id]
        if len(filtered_chunks) == len(original_chunks):
            raise HTTPException(status_code=404, detail="Chunk not found")

        doc_meta["chunks"] = _normalize_chunks(filtered_chunks, doc_id)
        doc_meta["chunk_count"] = len(doc_meta["chunks"])
        doc_meta["indexing_status"] = "pending"
        doc_meta["indexing_error"] = None
        _write_json(doc_meta_file, doc_meta)
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{kb_id}/search")
async def search_knowledge_base(
    request: Request,
    kb_id: str,
    query: str = Body(..., embed=True),
    top_k: int = Body(5, embed=True),
) -> dict[str, Any]:
    """Search a knowledge base using SQLite FTS5 + BM25."""
    try:
        workspace = await get_agent_for_request(request)
        kb_dir = workspace.workspace_dir / "knowledge" / kb_id
        if not kb_dir.exists():
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        if not get_index_db_path(kb_dir).exists():
            rebuild_index_from_metadata(kb_dir)
        else:
            ensure_store(kb_dir)

        results = search_index(kb_dir, query=query, top_k=top_k)
        return {"results": results, "query": query}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("knowledge search failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
