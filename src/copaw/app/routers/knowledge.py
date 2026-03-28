# -*- coding: utf-8 -*-
"""Knowledge base API routes."""

import json
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from openai import OpenAI
from pydantic import BaseModel, Field

from ...agents.knowledge.chunk_strategies import chunk_text
from ...agents.knowledge.knowledge_manager import (
    ChunkConfig,
    Document,
    KnowledgeBase,
)
from ...agents.utils import get_copaw_token_counter
from ...config.config import load_agent_config
from ..agent_context import get_agent_for_request

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
logger = logging.getLogger(__name__)


class KnowledgeBaseCreate(BaseModel):
    """Knowledge base creation request."""

    name: str = Field(..., description="Knowledge base name")
    description: str = Field(default="", description="Knowledge base description")
    storage_type: str = Field(default="chroma", description="Storage type")


def _normalize_document_meta(doc_path: Path, doc_meta: dict[str, Any]) -> dict[str, Any]:
    """Return a stable document payload for mixed legacy/current metadata shapes."""
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
        "uploaded_at": (
            doc_meta.get("uploaded_at")
            or doc_meta.get("created_at")
            or doc_meta.get("converted_at")
        ),
        "chunk_count": chunk_count,
        "indexing_status": doc_meta.get("indexing_status"),
        "indexing_error": doc_meta.get("indexing_error"),
    }


@router.get("/list")
async def list_knowledge_bases(request: Request) -> dict:
    """List all knowledge bases."""
    try:
        workspace = await get_agent_for_request(request)
        kb_dir = workspace.workspace_dir / "knowledge"

        knowledge_bases = []
        if kb_dir.exists():
            for kb_path in kb_dir.iterdir():
                if kb_path.is_dir():
                    meta_file = kb_path / "meta.json"
                    if meta_file.exists():
                        with open(meta_file, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            knowledge_bases.append(
                                {
                                    "id": kb_path.name,
                                    "name": meta.get("name", kb_path.name),
                                    "description": meta.get("description", ""),
                                    "storage_type": meta.get("storage_type", "chroma"),
                                    "created_at": meta.get("created_at", ""),
                                    "document_count": len(
                                        list((kb_path / "documents").iterdir())
                                        if (kb_path / "documents").exists()
                                        else []
                                    ),
                                }
                            )

        return {"knowledge_bases": knowledge_bases}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/create")
async def create_knowledge_base(
    request: Request,
    data: KnowledgeBaseCreate,
) -> dict:
    """Create a new knowledge base."""
    try:
        workspace = await get_agent_for_request(request)
        kb_id = str(uuid.uuid4())
        kb_dir = workspace.workspace_dir / "knowledge" / kb_id
        kb_dir.mkdir(parents=True, exist_ok=True)

        # Save metadata with default chunk config
        meta = {
            "id": kb_id,
            "name": data.name,
            "description": data.description,
            "storage_type": data.storage_type,
            "created_at": str(os.path.getctime(kb_dir)),
            "chunk_config": {
                "chunk_type": "length",
                "max_length": 500,
                "overlap": 50,
                "separators": [
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
                ],
            },
        }

        meta_file = kb_dir / "meta.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        return {"id": kb_id, "name": data.name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{kb_id}")
async def delete_knowledge_base(request: Request, kb_id: str) -> dict:
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
async def get_knowledge_base_detail(request: Request, kb_id: str) -> dict:
    """Get knowledge base detail."""
    try:
        workspace = await get_agent_for_request(request)
        kb_dir = workspace.workspace_dir / "knowledge" / kb_id

        if not kb_dir.exists():
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        meta_file = kb_dir / "meta.json"
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        # Get documents (lightweight - without chunks for better performance)
        documents = []
        doc_dir = kb_dir / "documents"
        if doc_dir.exists():
            for doc_path in doc_dir.iterdir():
                if doc_path.is_dir():
                    doc_meta_file = doc_path / "meta.json"
                    if doc_meta_file.exists():
                        with open(doc_meta_file, "r", encoding="utf-8") as f:
                            doc_meta = json.load(f)
                            documents.append(_normalize_document_meta(doc_path, doc_meta))

        return {
            "id": kb_id,
            "name": meta.get("name", ""),
            "description": meta.get("description", ""),
            "storage_type": meta.get("storage_type", "chroma"),
            "chunk_config": meta.get("chunk_config", {}),
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
    chunk_type: str | None = Body(None, embed=True),
    max_length: int | None = Body(None, embed=True),
    overlap: int | None = Body(None, embed=True),
    separators: str | None = Body(None, embed=True),
) -> dict:
    """Upload a document to knowledge base.

    The document is saved immediately, and chunking/indexing happens in the background.
    """
    try:
        logger.info(f"Upload request for kb_id: {kb_id}, filename: {file.filename}")

        workspace = await get_agent_for_request(request)
        kb_dir = workspace.workspace_dir / "knowledge" / kb_id

        if not kb_dir.exists():
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        # Read file content with size limit
        content = await file.read()
        file_size = len(content)

        # Limit file size to 10MB
        MAX_FILE_SIZE = 10 * 1024 * 1024
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
            )

        logger.info(f"File size: {file_size} bytes")

        # Get chunk config from request or KB metadata
        meta_file = kb_dir / "meta.json"
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        kb_chunk_config = meta.get("chunk_config", {})

        # Parse separators from JSON string if provided
        separators_list = kb_chunk_config.get("separators", [])
        if separators:
            try:
                separators_list = json.loads(separators)
            except json.JSONDecodeError:
                logger.warning(f"Invalid separators JSON: {separators}, using KB default")
                separators_list = kb_chunk_config.get("separators", [])

        # Use request params if provided, otherwise use KB default
        chunk_config = {
            "chunk_type": chunk_type if chunk_type else kb_chunk_config.get("chunk_type", "length"),
            "max_length": max_length if max_length else kb_chunk_config.get("max_length", 500),
            "overlap": overlap if overlap is not None else kb_chunk_config.get("overlap", 50),
            "separators": separators_list,
        }

        # Save file
        doc_id = str(uuid.uuid4())
        doc_dir = kb_dir / "documents" / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)

        file_path = doc_dir / file.filename
        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"File saved: {file_path}")

        # Initialize document metadata with indexing status
        file_type = Path(file.filename).suffix.lower()
        doc_meta = {
            "doc_id": doc_id,
            "filename": file.filename,
            "file_type": file_type,
            "size": len(content),
            "uploaded_at": str(os.path.getctime(file_path)),
            "chunk_count": 0,
            "chunks": [],
            "indexing_status": "pending",  # pending, processing, completed, failed
            "indexing_error": None,
        }

        # Save initial metadata immediately
        doc_meta_file = doc_dir / "meta.json"
        with open(doc_meta_file, "w", encoding="utf-8") as f:
            json.dump(doc_meta, f, ensure_ascii=False, indent=2)

        # Start background indexing task
        embedding_config = workspace.config.running.embedding_config
        background_tasks.add_task(
            _index_documentInBackground,
            workspace_dir=workspace.workspace_dir,
            kb_id=kb_id,
            doc_id=doc_id,
            file_path=str(file_path),
            file_type=file_type,
            chunk_config=chunk_config,
            embedding_config=embedding_config,
        )

        logger.info(f"Document uploaded successfully: {doc_id}, indexing in background")
        return {
            "doc_id": doc_id,
            "filename": file.filename,
            "chunk_count": 0,
            "indexing_status": "pending"
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Upload failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _index_documentInBackground(
    workspace_dir: str,
    kb_id: str,
    doc_id: str,
    file_path: str,
    file_type: str,
    chunk_config: dict,
    embedding_config: Any,
) -> None:
    """Background task to index a document."""
    import asyncio
    from pathlib import Path

    logger.info(f"[Background] Starting indexing for document {doc_id}")

    doc_dir = Path(workspace_dir) / "knowledge" / kb_id / "documents" / doc_id
    doc_meta_file = doc_dir / "meta.json"

    try:
        # Update status to processing
        with open(doc_meta_file, "r", encoding="utf-8") as f:
            doc_meta = json.load(f)

        doc_meta["indexing_status"] = "processing"
        with open(doc_meta_file, "w", encoding="utf-8") as f:
            json.dump(doc_meta, f, ensure_ascii=False, indent=2)

        # For text files, read and chunk
        if file_type in [".txt", ".md", ".json", ".csv"]:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()

                logger.info(f"[Background] File content length: {len(file_content)} characters")

                # Chunk content
                from ...agents.knowledge.chunk_strategies import chunk_text

                chunks = chunk_text(
                    text=file_content,
                    doc_id=doc_id,
                    chunk_type=chunk_config["chunk_type"],
                    max_length=chunk_config["max_length"],
                    overlap=chunk_config["overlap"],
                    separators=chunk_config["separators"],
                )

                logger.info(f"[Background] Created {len(chunks)} chunks")

                # Generate embeddings
                if embedding_config and embedding_config.api_key and len(chunks) > 0:
                    logger.info(f"[Background] Starting embedding generation for {len(chunks)} chunks")

                    try:
                        chunks = await _generate_embeddings(chunks, embedding_config)
                        logger.info(f"[Background] Embeddings generated successfully")
                    except Exception as e:
                        logger.warning(f"[Background] Embedding generation failed: {e}")
                        # Save chunks without embeddings
                else:
                    logger.info(f"[Background] No embedding config, saving chunks without embeddings")

                # Update metadata with results
                doc_meta["chunk_count"] = len(chunks)
                doc_meta["chunks"] = chunks
                doc_meta["indexing_status"] = "completed"
                doc_meta["indexing_error"] = None

                with open(doc_meta_file, "w", encoding="utf-8") as f:
                    json.dump(doc_meta, f, ensure_ascii=False, indent=2)

                logger.info(f"[Background] Document indexing completed: {doc_id}")

            except Exception as e:
                logger.error(f"[Background] Error processing file content: {e}", exc_info=True)

                # Update status to failed
                doc_meta["indexing_status"] = "failed"
                doc_meta["indexing_error"] = str(e)

                with open(doc_meta_file, "w", encoding="utf-8") as f:
                    json.dump(doc_meta, f, ensure_ascii=False, indent=2)
        else:
            logger.info(f"[Background] File type {file_type} not supported for chunking")
            doc_meta["indexing_status"] = "completed"
            doc_meta["indexing_error"] = f"File type {file_type} not supported for chunking"

            with open(doc_meta_file, "w", encoding="utf-8") as f:
                json.dump(doc_meta, f, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[Background] Indexing failed for document {doc_id}: {e}", exc_info=True)

        try:
            with open(doc_meta_file, "r", encoding="utf-8") as f:
                doc_meta = json.load(f)

            doc_meta["indexing_status"] = "failed"
            doc_meta["indexing_error"] = str(e)

            with open(doc_meta_file, "w", encoding="utf-8") as f:
                json.dump(doc_meta, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


@router.post("/{kb_id}/documents/{doc_id}/reindex")
async def reindex_document(request: Request, kb_id: str, doc_id: str, background_tasks: BackgroundTasks) -> dict:
    """Reindex a document (re-chunk and regenerate embeddings)."""
    try:
        logger.info(f"Reindex request for kb_id: {kb_id}, doc_id: {doc_id}")

        workspace = await get_agent_for_request(request)
        kb_dir = workspace.workspace_dir / "knowledge" / kb_id
        doc_dir = kb_dir / "documents" / doc_id

        if not doc_dir.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        # Load KB metadata
        meta_file = kb_dir / "meta.json"
        with open(meta_file, "r", encoding="utf-8") as f:
            kb_meta = json.load(f)

        chunk_config = kb_meta.get("chunk_config", {})

        # Find content file
        content_files = [f for f in doc_dir.glob("*.*") if f.name != "meta.json"]
        if not content_files:
            raise HTTPException(status_code=400, detail="No content file found")

        content_file = content_files[0]
        file_type = content_file.suffix.lower()

        # Update metadata status to processing
        doc_meta_file = doc_dir / "meta.json"
        with open(doc_meta_file, "r", encoding="utf-8") as f:
            doc_meta = json.load(f)

        doc_meta["indexing_status"] = "processing"
        with open(doc_meta_file, "w", encoding="utf-8") as f:
            json.dump(doc_meta, f, ensure_ascii=False, indent=2)

        # Start background reindexing task
        embedding_config = workspace.config.running.embedding_config
        background_tasks.add_task(
            _reindex_documentInBackground,
            workspace_dir=str(workspace.workspace_dir),
            kb_id=kb_id,
            doc_id=doc_id,
            file_path=str(content_file),
            file_type=file_type,
            chunk_config=chunk_config,
            embedding_config=embedding_config,
        )

        logger.info(f"Document reindexing started: {doc_id}")
        return {
            "doc_id": doc_id,
            "filename": doc_meta.get("filename", ""),
            "indexing_status": "processing"
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Reindex failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(request: Request, kb_id: str, doc_id: str) -> dict:
    """Delete a document from knowledge base."""
    try:
        workspace = await get_agent_for_request(request)
        doc_dir = workspace.workspace_dir / "knowledge" / kb_id / "documents" / doc_id

        if not doc_dir.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        shutil.rmtree(doc_dir)
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{kb_id}/documents/{doc_id}/chunks")
async def get_document_chunks(request: Request, kb_id: str, doc_id: str) -> dict:
    """Get document chunks."""
    try:
        workspace = await get_agent_for_request(request)
        doc_meta_file = (
            workspace.workspace_dir / "knowledge" / kb_id / "documents" / doc_id / "meta.json"
        )

        if not doc_meta_file.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        with open(doc_meta_file, "r", encoding="utf-8") as f:
            doc_meta = json.load(f)

        return {"chunks": doc_meta.get("chunks", [])}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{kb_id}/documents/{doc_id}/status")
async def get_document_indexing_status(
    request: Request,
    kb_id: str,
    doc_id: str,
) -> dict:
    """Get document indexing status."""
    try:
        workspace = await get_agent_for_request(request)
        doc_meta_file = (
            workspace.workspace_dir / "knowledge" / kb_id / "documents" / doc_id / "meta.json"
        )

        if not doc_meta_file.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        with open(doc_meta_file, "r", encoding="utf-8") as f:
            doc_meta = json.load(f)

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
) -> dict:
    """Update a chunk."""
    try:
        workspace = await get_agent_for_request(request)
        doc_meta_file = (
            workspace.workspace_dir / "knowledge" / kb_id / "documents" / doc_id / "meta.json"
        )

        if not doc_meta_file.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        with open(doc_meta_file, "r", encoding="utf-8") as f:
            doc_meta = json.load(f)

        # Find and update chunk
        for chunk in doc_meta.get("chunks", []):
            if chunk["chunk_id"] == chunk_id:
                chunk["content"] = content
                # Remove old embedding if exists
                if "embedding" in chunk:
                    del chunk["embedding"]
                break

        # Save updated metadata
        with open(doc_meta_file, "w", encoding="utf-8") as f:
            json.dump(doc_meta, f, ensure_ascii=False, indent=2)

        return {"updated": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{kb_id}/documents/{doc_id}/chunks/save")
async def save_chunks_and_reindex(
    request: Request,
    kb_id: str,
    doc_id: str,
) -> dict:
    """Save edited chunks and regenerate embeddings for all chunks."""
    try:
        import asyncio

        workspace = await get_agent_for_request(request)
        doc_dir = workspace.workspace_dir / "knowledge" / kb_id / "documents" / doc_id

        if not doc_dir.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        doc_meta_file = doc_dir / "meta.json"
        with open(doc_meta_file, "r", encoding="utf-8") as f:
            doc_meta = json.load(f)

        chunks = doc_meta.get("chunks", [])
        if not chunks:
            return {"updated": True, "embedding_count": 0}

        # Get embedding config
        embedding_config = workspace.config.running.embedding_config

        # Regenerate embeddings for all chunks
        if embedding_config and embedding_config.api_key:
            try:
                chunks = await asyncio.wait_for(
                    _generate_embeddings(chunks, embedding_config),
                    timeout=30.0
                )
                logger.info(f"Regenerated embeddings for {len(chunks)} chunks")
            except asyncio.TimeoutError:
                logger.warning("Embedding generation timed out")
            except Exception as e:
                logger.warning(f"Embedding generation failed: {e}")

        # Save updated metadata
        doc_meta["chunks"] = chunks
        doc_meta["chunk_count"] = len(chunks)

        with open(doc_meta_file, "w", encoding="utf-8") as f:
            json.dump(doc_meta, f, ensure_ascii=False, indent=2)

        embedding_count = sum(1 for c in chunks if c.get("embedding"))
        return {"updated": True, "embedding_count": embedding_count}
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
) -> dict:
    """Add a new chunk to document."""
    try:
        workspace = await get_agent_for_request(request)
        doc_meta_file = (
            workspace.workspace_dir / "knowledge" / kb_id / "documents" / doc_id / "meta.json"
        )

        if not doc_meta_file.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        with open(doc_meta_file, "r", encoding="utf-8") as f:
            doc_meta = json.load(f)

        chunks = doc_meta.get("chunks", [])
        new_chunk_id = f"{doc_id}_chunk_{len(chunks)}"

        new_chunk = {
            "chunk_id": new_chunk_id,
            "content": content,
            "chunk_index": len(chunks),
        }

        chunks.append(new_chunk)
        doc_meta["chunk_count"] = len(chunks)

        # Save updated metadata
        with open(doc_meta_file, "w", encoding="utf-8") as f:
            json.dump(doc_meta, f, ensure_ascii=False, indent=2)

        return {"added": True, "chunk_id": new_chunk_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{kb_id}/documents/{doc_id}/chunks/{chunk_id}")
async def delete_chunk(
    request: Request,
    kb_id: str,
    doc_id: str,
    chunk_id: str,
) -> dict:
    """Delete a chunk from document."""
    try:
        workspace = await get_agent_for_request(request)
        doc_meta_file = (
            workspace.workspace_dir / "knowledge" / kb_id / "documents" / doc_id / "meta.json"
        )

        if not doc_meta_file.exists():
            raise HTTPException(status_code=404, detail="Document not found")

        with open(doc_meta_file, "r", encoding="utf-8") as f:
            doc_meta = json.load(f)

        chunks = doc_meta.get("chunks", [])
        original_length = len(chunks)

        # Remove chunk
        chunks = [c for c in chunks if c["chunk_id"] != chunk_id]

        if len(chunks) == original_length:
            raise HTTPException(status_code=404, detail="Chunk not found")

        # Reindex chunks
        for idx, chunk in enumerate(chunks):
            chunk["chunk_index"] = idx

        doc_meta["chunks"] = chunks
        doc_meta["chunk_count"] = len(chunks)

        # Save updated metadata
        with open(doc_meta_file, "w", encoding="utf-8") as f:
            json.dump(doc_meta, f, ensure_ascii=False, indent=2)

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
) -> dict:
    """Search knowledge base."""
    try:
        workspace = await get_agent_for_request(request)
        kb_dir = workspace.workspace_dir / "knowledge" / kb_id

        if not kb_dir.exists():
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        embedding_config = workspace.config.running.embedding_config

        # Get all documents and chunks
        all_chunks = []
        doc_dir = kb_dir / "documents"
        if doc_dir.exists():
            for doc_path in doc_dir.iterdir():
                if not doc_path.is_dir():
                    continue
                doc_meta_file = doc_path / "meta.json"
                if not doc_meta_file.exists():
                    continue
                with open(doc_meta_file, "r", encoding="utf-8") as f:
                    doc_meta = json.load(f)
                for chunk in doc_meta.get("chunks", []):
                    chunk["filename"] = doc_meta.get("filename", "")
                    all_chunks.append(chunk)

        # If embeddings available, use vector search
        if embedding_config and embedding_config.api_key and all(c.get("embedding") for c in all_chunks if c.get("embedding")):
            results = await _vector_search(query, all_chunks, embedding_config, top_k)
        else:
            # Fallback to keyword search
            results = _keyword_search(query, all_chunks, top_k)

        return {"results": results, "query": query}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Search failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _generate_embeddings(chunks: list[dict], embedding_config) -> list[dict]:
    """Generate embeddings for chunks using the configured embedding model."""
    try:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        def _generate_sync():
            try:
                client = OpenAI(
                    api_key=embedding_config.api_key,
                    base_url=embedding_config.base_url,
                    timeout=10.0,  # 10 second timeout for each API call
                )

                # Prepare texts for batch embedding
                texts = [chunk["content"] for chunk in chunks]

                # Batch embedding
                max_batch_size = embedding_config.max_batch_size
                all_embeddings = []

                for i in range(0, len(texts), max_batch_size):
                    batch_texts = texts[i:i + max_batch_size]
                    try:
                        response = client.embeddings.create(
                            input=batch_texts,
                            model=embedding_config.model_name,
                        )
                        all_embeddings.extend([e.embedding for e in response.data])
                    except Exception as e:
                        logger.error(f"Failed to generate embeddings for batch {i}: {e}")
                        # Add zero vectors for failed batches
                        all_embeddings.extend([[0.0] * 1024 for _ in batch_texts])

                return all_embeddings
            except Exception as e:
                logger.error(f"Embedding generation error: {e}")
                raise

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            all_embeddings = await loop.run_in_executor(pool, _generate_sync)

        # Add embeddings to chunks
        for chunk, embedding in zip(chunks, all_embeddings):
            chunk["embedding"] = embedding

        return chunks

    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}", exc_info=True)
        # Return chunks without embeddings
        return chunks


async def _vector_search(
    query: str,
    chunks: list[dict],
    embedding_config,
    top_k: int,
) -> list[dict]:
    """Perform vector similarity search."""
    try:
        import asyncio
        import numpy as np
        from concurrent.futures import ThreadPoolExecutor

        def _generate_query_embedding():
            client = OpenAI(
                api_key=embedding_config.api_key,
                base_url=embedding_config.base_url,
            )

            response = client.embeddings.create(
                input=[query],
                model=embedding_config.model_name,
            )
            return np.array(response.data[0].embedding)

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            query_embedding = await loop.run_in_executor(pool, _generate_query_embedding)

        # Calculate similarities
        results = []
        for chunk in chunks:
            if not chunk.get("embedding"):
                continue

            chunk_embedding = np.array(chunk["embedding"])

            # Cosine similarity
            similarity = np.dot(query_embedding, chunk_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embedding)
            )

            results.append(
                {
                    "doc_id": chunk.get("doc_id", ""),
                    "filename": chunk.get("filename", ""),
                    "chunk_id": chunk.get("chunk_id", ""),
                    "content": chunk.get("content", ""),
                    "score": float(similarity),
                }
            )

        # Sort by similarity and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    except Exception as e:
        logger.error(f"Vector search failed: {e}", exc_info=True)
        return _keyword_search(query, chunks, top_k)


def _keyword_search(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    """Perform keyword-based search."""
    query_lower = query.lower()
    query_terms = query_lower.split()

    results = []
    for chunk in chunks:
        content = chunk.get("content", "")
        content_lower = content.lower()

        # Calculate relevance score
        score = 0.0
        for term in query_terms:
            if term in content_lower:
                score += 1.0

        # Bonus for exact phrase match
        if query_lower in content_lower:
            score += 0.5

        if score > 0:
            results.append(
                {
                    "doc_id": chunk.get("doc_id", ""),
                    "filename": chunk.get("filename", ""),
                    "chunk_id": chunk.get("chunk_id", ""),
                    "content": content,
                    "score": score,
                }
            )

    # Sort by score and return top_k
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


async def _reindex_documentInBackground(
    workspace_dir: str,
    kb_id: str,
    doc_id: str,
    file_path: str,
    file_type: str,
    chunk_config: dict,
    embedding_config: dict,
) -> None:
    """Background task to reindex a document."""
    try:
        logger.info(f"[Background Reindex] Starting for document: {doc_id}")

        doc_dir = Path(workspace_dir) / "knowledge" / kb_id / "documents" / doc_id
        doc_meta_file = doc_dir / "meta.json"

        # Read content
        if file_type in [".txt", ".md", ".json", ".csv"]:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()

            logger.info(f"[Background Reindex] File content length: {len(file_content)} chars")

            # Chunk content
            from ...agents.knowledge.chunk_strategies import chunk_text

            chunks = chunk_text(
                text=file_content,
                doc_id=doc_id,
                chunk_type=chunk_config["chunk_type"],
                max_length=chunk_config["max_length"],
                overlap=chunk_config["overlap"],
                separators=chunk_config["separators"],
            )

            logger.info(f"[Background Reindex] Created {len(chunks)} chunks")

            # Generate embeddings
            if embedding_config and embedding_config.get("api_key") and len(chunks) > 0:
                logger.info(f"[Background Reindex] Generating embeddings for {len(chunks)} chunks")
                try:
                    chunks = await _generate_embeddings(chunks, embedding_config)
                    logger.info(f"[Background Reindex] Embeddings generated successfully")
                except Exception as e:
                    logger.warning(f"[Background Reindex] Embedding generation failed: {e}")
            else:
                logger.info(f"[Background Reindex] No embedding config, skipping embeddings")

            # Update metadata
            with open(doc_meta_file, "r", encoding="utf-8") as f:
                doc_meta = json.load(f)

            doc_meta["chunk_count"] = len(chunks)
            doc_meta["chunks"] = chunks
            doc_meta["indexing_status"] = "completed"
            doc_meta["indexing_error"] = None

            with open(doc_meta_file, "w", encoding="utf-8") as f:
                json.dump(doc_meta, f, ensure_ascii=False, indent=2)

            logger.info(f"[Background Reindex] Document reindexing completed: {doc_id}")
        else:
            logger.info(f"[Background Reindex] File type {file_type} not supported for chunking")

    except Exception as e:
        logger.error(f"[Background Reindex] Error processing document {doc_id}: {e}", exc_info=True)

        try:
            with open(doc_meta_file, "r", encoding="utf-8") as f:
                doc_meta = json.load(f)

            doc_meta["indexing_status"] = "failed"
            doc_meta["indexing_error"] = str(e)

            with open(doc_meta_file, "w", encoding="utf-8") as f:
                json.dump(doc_meta, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
