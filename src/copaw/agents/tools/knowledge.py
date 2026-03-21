# -*- coding: utf-8 -*-
"""Knowledge base search tools for CoPaw agents."""

import asyncio
import json
import logging
from pathlib import Path

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse
from openai import OpenAI

from ...config.config import load_agent_config

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
        config = load_agent_config()
        workspace_dir = Path(config.workspace_path)
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

        # Format results
        result_text = f"Found {len(top_results)} result(s) for query: {query}\n\n"
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
        config = load_agent_config()
        workspace_dir = Path(config.workspace_path)

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
