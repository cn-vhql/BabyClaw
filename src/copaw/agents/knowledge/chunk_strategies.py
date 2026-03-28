# -*- coding: utf-8 -*-
"""Text chunking strategies for knowledge base."""

from __future__ import annotations

import logging
import re

from .sqlite_store import DEFAULT_CHUNK_SEPARATORS

logger = logging.getLogger(__name__)

SMART_LENGTH_BOUNDARIES = [
    "\n\n",
    "\r\n\r\n",
    "\n",
    "\r\n",
    "。",
    "！",
    "？",
    ".",
    "!",
    "?",
    ";",
    "；",
    "，",
    ",",
    "、",
    ":",
    "：",
    " ",
    "\t",
]


class ChunkStrategy:
    """Base class for chunking strategies."""

    def chunk(
        self,
        text: str,
        doc_id: str,
        max_length: int = 500,
        overlap: int = 50,
        **kwargs,
    ) -> list[dict]:
        raise NotImplementedError


class LengthChunkStrategy(ChunkStrategy):
    """Fixed-length chunking with overlap and natural-boundary adjustment."""

    @staticmethod
    def _build_boundary_order(separators: list[str] | None = None) -> list[str]:
        ordered: list[str] = []
        for sep in (separators or []) + SMART_LENGTH_BOUNDARIES:
            if sep and sep not in ordered:
                ordered.append(sep)
        return ordered

    @staticmethod
    def _find_smart_end(
        text: str,
        start: int,
        target_end: int,
        max_length: int,
        separators: list[str] | None = None,
    ) -> int:
        if target_end >= len(text):
            return len(text)

        tolerance = max(1, int(round(max_length * 0.1)))
        window_start = max(start + 1, target_end - tolerance)
        window_end = min(len(text), target_end + tolerance)
        boundary_order = LengthChunkStrategy._build_boundary_order(separators)
        if not boundary_order:
            return target_end

        max_boundary_length = max(len(sep) for sep in boundary_order)
        segment_start = max(start, window_start - max_boundary_length + 1)
        segment = text[segment_start:window_end]

        for sep in boundary_order:
            best_end: int | None = None
            search_from = 0
            while True:
                index = segment.find(sep, search_from)
                if index == -1:
                    break

                candidate_end = segment_start + index + len(sep)
                if window_start <= candidate_end <= window_end and candidate_end > start:
                    if best_end is None or (
                        abs(candidate_end - target_end),
                        candidate_end > target_end,
                    ) < (
                        abs(best_end - target_end),
                        best_end > target_end,
                    ):
                        best_end = candidate_end

                search_from = index + 1

            if best_end is not None:
                return best_end

        return target_end

    def chunk(
        self,
        text: str,
        doc_id: str,
        max_length: int = 500,
        overlap: int = 50,
        separators: list[str] | None = None,
        **kwargs,
    ) -> list[dict]:
        max_length = max(1, int(max_length))
        overlap = max(0, min(int(overlap), max_length - 1))
        chunks = []
        start = 0
        chunk_idx = 0

        while start < len(text):
            target_end = min(start + max_length, len(text))
            end = self._find_smart_end(
                text=text,
                start=start,
                target_end=target_end,
                max_length=max_length,
                separators=separators,
            )
            if end <= start:
                end = target_end
            chunk_content = text[start:end]

            chunks.append(
                {
                    "chunk_id": f"{doc_id}_chunk_{chunk_idx}",
                    "content": chunk_content,
                    "chunk_index": chunk_idx,
                    "start": start,
                    "end": end,
                    "strategy": "length",
                }
            )

            start = end - overlap if end < len(text) else len(text)
            if start <= chunks[-1]["start"]:
                start = end
            chunk_idx += 1

        return chunks


class SeparatorChunkStrategy(ChunkStrategy):
    """Separator-based chunking."""

    def chunk(
        self,
        text: str,
        doc_id: str,
        max_length: int = 500,
        overlap: int = 50,
        separators: list[str] | None = None,
        **kwargs,
    ) -> list[dict]:
        if separators is None:
            separators = list(DEFAULT_CHUNK_SEPARATORS)

        chunks = []
        for sep in separators:
            if sep and sep not in text:
                continue

            parts = re.split(f"({re.escape(sep)})", text) if sep else [text]
            current_chunk = ""
            chunk_idx = 0

            for index, part in enumerate(parts):
                current_chunk += part
                if sep and part == sep and len(current_chunk.strip()) > 0:
                    if len(current_chunk) >= max_length * 0.5 or index == len(parts) - 1:
                        chunks.append(
                            {
                                "chunk_id": f"{doc_id}_chunk_{chunk_idx}",
                                "content": current_chunk,
                                "chunk_index": chunk_idx,
                                "strategy": "separator",
                                "separator": sep,
                            }
                        )
                        chunk_idx += 1
                        current_chunk = ""

            if chunks:
                if current_chunk.strip():
                    chunks.append(
                        {
                            "chunk_id": f"{doc_id}_chunk_{chunk_idx}",
                            "content": current_chunk,
                            "chunk_index": chunk_idx,
                            "strategy": "separator",
                            "separator": sep,
                        }
                    )
                return chunks

        logger.warning("No separator produced chunks, falling back to length-based")
        return LengthChunkStrategy().chunk(text, doc_id, max_length, overlap)


def get_strategy(strategy_type: str) -> ChunkStrategy:
    """Get chunking strategy by type."""
    strategies = {
        "length": LengthChunkStrategy,
        "separator": SeparatorChunkStrategy,
    }
    strategy_class = strategies.get(strategy_type, LengthChunkStrategy)
    return strategy_class()


def chunk_text(
    text: str,
    doc_id: str,
    chunk_type: str = "length",
    max_length: int = 500,
    overlap: int = 50,
    separators: list[str] | None = None,
    **kwargs,
) -> list[dict]:
    """Chunk text using the requested strategy."""
    if separators is None:
        separators = list(DEFAULT_CHUNK_SEPARATORS)

    strategy = get_strategy(chunk_type)
    chunks = strategy.chunk(
        text=text,
        doc_id=doc_id,
        max_length=max_length,
        overlap=overlap,
        separators=separators,
        **kwargs,
    )

    logger.info(
        "Chunked %s chars into %s chunks using %s strategy",
        len(text),
        len(chunks),
        chunk_type,
    )
    return chunks
