# -*- coding: utf-8 -*-
"""Knowledge base search tools for CoPaw agents."""

import asyncio
import json
import logging
import os
from pathlib import Path

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse
from openai import OpenAI

logger = logging.getLogger(__name__)


def knowledge_search(
    query: str,
    kb_id: str | None = None,
    top_k: int = 5,
) -> ToolResponse:
    """Search knowledge base for relevant information.

    Args:
        query: Search query string
        kb_id: Knowledge base ID (optional, searches all if not specified)
        top_k: Maximum number of results to return (default: 5)

    Returns:
        ToolResponse with search results including document name, content, and score
    """
    try:
        # Lazy import to avoid circular dependency
        from ...app.agent_context import get_current_agent_id
        from ...config.config import load_agent_config

        # Get current agent ID automatically
        agent_id = get_current_agent_id()
        config = load_agent_config(agent_id)
        workspace_dir = Path(config.workspace_dir)  # Fixed: workspace_dir not workspace_path
        embedding_config = config.running.embedding_config

        if kb_id:
            kb_ids = [kb_id]
        else:
            # Get all knowledge bases
            kb_dir = workspace_dir / "knowledge"
            if not kb_dir.exists():
                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text="No knowledge bases found. Please create a knowledge base first.",
                        ),
                    ],
                )
            kb_ids = [d.name for d in kb_dir.iterdir() if d.is_dir()]

        all_results = []

        for kb_id in kb_ids:
            kb_dir = workspace_dir / "knowledge" / kb_id
            if not kb_dir.exists():
                continue

            # Load metadata
            meta_file = kb_dir / "meta.json"
            if not meta_file.exists():
                continue

            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

            kb_name = meta.get("name", kb_id)

            # Search through documents
            doc_dir = kb_dir / "documents"
            if not doc_dir.exists():
                continue

            for doc_path in doc_dir.iterdir():
                if not doc_path.is_dir():
                    continue

                doc_meta_file = doc_path / "meta.json"
                if not doc_meta_file.exists():
                    continue

                with open(doc_meta_file, "r", encoding="utf-8") as f:
                    doc_meta = json.load(f)

                filename = doc_meta.get("filename", "")
                chunks = doc_meta.get("chunks", [])

                # Use vector search if embeddings available
                if embedding_config and embedding_config.api_key and any(c.get("embedding") for c in chunks if c.get("embedding")):
                    chunk_results = _vector_search_chunks(query, chunks, embedding_config)
                else:
                    # Fallback to keyword matching
                    chunk_results = []
                    for chunk in chunks:
                        content = chunk.get("content", "")
                        if not content:
                            continue

                        score = _calculate_score(query, content)

                        if score > 0:
                            chunk_results.append(
                                {
                                    "kb_name": kb_name,
                                    "filename": filename,
                                    "chunk_id": chunk.get("chunk_id", ""),
                                    "content": content,
                                    "score": score,
                                }
                            )

                all_results.extend(chunk_results)

        # Sort by score and return top_k
        all_results.sort(key=lambda x: x["score"], reverse=True)
        top_results = all_results[:top_k]

        if not top_results:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"No results found for query: {query}",
                    ),
                ],
            )

        # Determine search mode for user feedback
        has_embeddings = embedding_config and embedding_config.api_key
        search_mode = "semantic search" if has_embeddings else "keyword search"

        # Format results
        result_text = f"Found {len(top_results)} result(s) for query: {query} (using {search_mode})\n\n"
        for i, result in enumerate(top_results, 1):
            result_text += f"--- Result {i} ---\n"
            result_text += f"Knowledge Base: {result['kb_name']}\n"
            result_text += f"Document: {result['filename']}\n"
            result_text += f"Score: {result['score']:.4f}\n"
            result_text += f"Content:\n{result['content']}\n\n"

        return ToolResponse(
            content=[TextBlock(type="text", text=result_text)],
        )

    except Exception as e:
        logger.error(f"Knowledge search failed: {e}", exc_info=True)
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Knowledge search failed: {str(e)}",
                ),
            ],
        )


def list_knowledge_bases() -> ToolResponse:
    """List all available knowledge bases.

    Returns:
        ToolResponse with list of knowledge bases including name, description, and document count
    """
    try:
        # Lazy import to avoid circular dependency
        from ...app.agent_context import get_current_agent_id
        from ...config.config import load_agent_config

        # Get current agent ID automatically
        agent_id = get_current_agent_id()
        config = load_agent_config(agent_id)
        workspace_dir = Path(config.workspace_dir)  # Fixed: workspace_dir not workspace_path

        kb_dir = workspace_dir / "knowledge"
        if not kb_dir.exists():
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text="No knowledge bases found. Please create a knowledge base first.",
                    ),
                ],
            )

        kb_list = []
        for kb_path in kb_dir.iterdir():
            if not kb_path.is_dir():
                continue

            meta_file = kb_path / "meta.json"
            if not meta_file.exists():
                continue

            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

            # Count documents
            doc_dir = kb_path / "documents"
            doc_count = (
                len([d for d in doc_dir.iterdir() if d.is_dir()])
                if doc_dir.exists()
                else 0
            )

            kb_list.append(
                {
                    "id": kb_path.name,
                    "name": meta.get("name", kb_path.name),
                    "description": meta.get("description", ""),
                    "document_count": doc_count,
                }
            )

        if not kb_list:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text="No knowledge bases found. Please create a knowledge base first.",
                    ),
                ],
            )

        # Format results
        result_text = f"Found {len(kb_list)} knowledge base(s):\n\n"
        for kb in kb_list:
            result_text += f"Name: {kb['name']}\n"
            result_text += f"ID: {kb['id']}\n"
            result_text += f"Description: {kb['description']}\n"
            result_text += f"Document Count: {kb['document_count']}\n\n"

        return ToolResponse(
            content=[TextBlock(type="text", text=result_text)],
        )

    except Exception as e:
        logger.error(f"List knowledge bases failed: {e}")
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"List knowledge bases failed: {str(e)}",
                ),
            ],
        )


def _vector_search_chunks(
    query: str,
    chunks: list[dict],
    embedding_config,
) -> list[dict]:
    """Perform vector similarity search on chunks."""
    try:
        import numpy as np

        client = OpenAI(
            api_key=embedding_config.api_key,
            base_url=embedding_config.base_url,
        )

        # Generate query embedding
        response = client.embeddings.create(
            input=[query],
            model=embedding_config.model_name,
        )
        query_embedding = np.array(response.data[0].embedding)

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

            if similarity > 0:
                results.append(
                    {
                        "kb_name": "",  # Will be filled by caller
                        "filename": "",  # Will be filled by caller
                        "chunk_id": chunk.get("chunk_id", ""),
                        "content": chunk.get("content", ""),
                        "score": float(similarity),
                    }
                )

        # Sort by similarity
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    except Exception as e:
        logger.error(f"Vector search failed: {e}, falling back to keyword search")
        # Fallback to keyword search
        results = []
        for chunk in chunks:
            content = chunk.get("content", "")
            if not content:
                continue

            score = _calculate_score(query, content)

            if score > 0:
                results.append(
                    {
                        "kb_name": "",
                        "filename": "",
                        "chunk_id": chunk.get("chunk_id", ""),
                        "content": content,
                        "score": score,
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results


def _calculate_score(query: str, content: str) -> float:
    """Calculate relevance score between query and content.

    Simple BM25-like scoring based on keyword matches.
    """
    query_lower = query.lower()
    content_lower = content.lower()

    query_terms = query_lower.split()
    if not query_terms:
        return 0.0

    matches = sum(1 for term in query_terms if term in content_lower)
    if matches == 0:
        return 0.0

    # Base score: ratio of matched terms
    base_score = matches / len(query_terms)

    # Bonus for exact phrase match
    if query_lower in content_lower:
        base_score += 0.3

    # Bonus for multiple matches
    if matches > 1:
        base_score += min(0.2, matches * 0.05)

    return min(1.0, base_score)


def knowledge_write(
    content: str,
    filename: str | None = None,
    kb_id: str | None = None,
) -> ToolResponse:
    """Write text content to a knowledge base.

    This tool allows the agent to save text or file content to a knowledge base
    for future retrieval. The content will be automatically chunked and indexed.

    Args:
        content: The text content to write to the knowledge base
        filename: Optional filename for the content (default: "agent_note.txt")
        kb_id: Optional knowledge base ID. If not specified, uses the first available KB
               or creates a default "Agent Notes" knowledge base

    Returns:
        ToolResponse with status message including knowledge base name and document ID

    Examples:
        >>> knowledge_write("Meeting notes: Discussed Q1 roadmap...", filename="meeting.txt")
        >>> knowledge_write("Important fact: Python 3.10 released in 2021")
    """
    try:
        import uuid
        from ...app.agent_context import get_current_agent_id
        from ...config.config import load_agent_config
        from ...agents.knowledge.chunk_strategies import chunk_text

        # Get current agent ID automatically
        agent_id = get_current_agent_id()
        config = load_agent_config(agent_id)
        workspace_dir = Path(config.workspace_dir)
        embedding_config = config.running.embedding_config

        # Determine which knowledge base to use
        if kb_id:
            kb_ids = [kb_id]
            # Validate KB exists
            kb_dir = workspace_dir / "knowledge" / kb_id
            if not kb_dir.exists():
                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text=f"Knowledge base '{kb_id}' not found. Please create it first or omit kb_id to use default.",
                        ),
                    ],
                )
        else:
            # Get all knowledge bases
            kb_dir = workspace_dir / "knowledge"
            if not kb_dir.exists():
                kb_dir.mkdir(parents=True, exist_ok=True)

            kb_ids = [d.name for d in kb_dir.iterdir() if d.is_dir()]

            # If no KB exists, create a default one
            if not kb_ids:
                default_kb_id = str(uuid.uuid4())
                default_kb_dir = kb_dir / default_kb_id
                default_kb_dir.mkdir(parents=True, exist_ok=True)

                # Create default KB metadata
                default_meta = {
                    "id": default_kb_id,
                    "name": "Agent Notes",
                    "description": "Default knowledge base for agent-created notes",
                    "storage_type": "chroma",
                    "created_at": str(os.path.getctime(default_kb_dir)),
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

                meta_file = default_kb_dir / "meta.json"
                with open(meta_file, "w", encoding="utf-8") as f:
                    json.dump(default_meta, f, ensure_ascii=False, indent=2)

                kb_ids = [default_kb_id]
                logger.info(f"Created default knowledge base: {default_kb_id}")

        # Use the first available KB
        target_kb_id = kb_ids[0]
        kb_dir = workspace_dir / "knowledge" / target_kb_id

        # Load KB metadata
        meta_file = kb_dir / "meta.json"
        with open(meta_file, "r", encoding="utf-8") as f:
            kb_meta = json.load(f)

        kb_name = kb_meta.get("name", target_kb_id)

        # Create document
        doc_id = str(uuid.uuid4())
        doc_dir = kb_dir / "documents" / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)

        # Use provided filename or generate default
        if not filename:
            timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"agent_note_{timestamp}.txt"

        # Save content as file
        file_path = doc_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Get chunk config
        chunk_config = kb_meta.get("chunk_config", {})
        chunk_type = chunk_config.get("chunk_type", "length")
        max_length = chunk_config.get("max_length", 500)
        overlap = chunk_config.get("overlap", 50)
        separators = chunk_config.get("separators", [
            "\n\n", "\n", "。", ".", "!", "?", ";", "，", ",", " ", "",
        ])

        # Chunk the content
        chunks = chunk_text(
            text=content,
            doc_id=doc_id,
            chunk_type=chunk_type,
            max_length=max_length,
            overlap=overlap,
            separators=separators,
        )

        # Generate embeddings if configured
        if embedding_config and embedding_config.api_key:
            try:
                chunks = _generate_embeddings_sync(chunks, embedding_config)
            except Exception as e:
                logger.warning(f"Failed to generate embeddings: {e}")
                # Continue without embeddings

        # Save document metadata
        doc_meta = {
            "doc_id": doc_id,
            "filename": filename,
            "file_type": Path(filename).suffix.lower() or ".txt",
            "size": len(content.encode("utf-8")),
            "uploaded_at": str(os.path.getctime(file_path)),
            "chunk_count": len(chunks),
            "chunks": chunks,
            "indexing_status": "completed",
            "indexing_error": None,
        }

        doc_meta_file = doc_dir / "meta.json"
        with open(doc_meta_file, "w", encoding="utf-8") as f:
            json.dump(doc_meta, f, ensure_ascii=False, indent=2)

        logger.info(f"Content written to knowledge base '{kb_name}', doc_id: {doc_id}")

        # Check if embeddings were generated
        has_embeddings = any(c.get("embedding") for c in chunks)
        embedding_status = "with semantic search enabled" if has_embeddings else "with keyword search"

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Content successfully saved to knowledge base '{kb_name}' {embedding_status}.\n"
                         f"Document ID: {doc_id}\n"
                         f"Filename: {filename}\n"
                         f"Chunks created: {len(chunks)}\n"
                         f"You can search for this content later using knowledge_search.",
                ),
            ],
        )

    except Exception as e:
        logger.error(f"Knowledge write failed: {e}", exc_info=True)
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Failed to save content to knowledge base: {str(e)}",
                ),
            ],
        )


def _generate_embeddings_sync(
    chunks: list[dict],
    embedding_config,
) -> list[dict]:
    """Generate embeddings for chunks synchronously.

    This is a simplified version for use in the agent tool context.
    """
    try:
        client = OpenAI(
            api_key=embedding_config.api_key,
            base_url=embedding_config.base_url,
            timeout=10.0,
        )

        # Prepare texts
        texts = [chunk["content"] for chunk in chunks]

        # Batch processing
        all_embeddings = []
        max_batch_size = embedding_config.max_batch_size if hasattr(embedding_config, 'max_batch_size') else 10

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

        # Add embeddings to chunks
        for chunk, embedding in zip(chunks, all_embeddings):
            chunk["embedding"] = embedding

        return chunks

    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
        # Return chunks without embeddings
        return chunks
