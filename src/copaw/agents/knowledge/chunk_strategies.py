# -*- coding: utf-8 -*-
"""Text chunking strategies for knowledge base."""

import re
import logging
from typing import Any
from collections import Counter

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


class ChunkStrategy:
    """Base class for chunking strategies."""

    def chunk(
        self,
        text: str,
        doc_id: str,
        max_length: int = 500,
        overlap: int = 50,
        **kwargs
    ) -> list[dict]:
        """Chunk text into pieces.

        Args:
            text: Text to chunk
            doc_id: Document ID
            max_length: Maximum chunk length
            overlap: Overlap between chunks
            **kwargs: Additional strategy-specific parameters

        Returns:
            List of chunk dictionaries
        """
        raise NotImplementedError


class LengthChunkStrategy(ChunkStrategy):
    """Fixed-length chunking with overlap."""

    def chunk(
        self,
        text: str,
        doc_id: str,
        max_length: int = 500,
        overlap: int = 50,
        **kwargs
    ) -> list[dict]:
        """Chunk by fixed length with overlap."""
        chunks = []
        start = 0
        chunk_idx = 0

        while start < len(text):
            end = min(start + max_length, len(text))
            chunk_content = text[start:end]

            chunks.append({
                "chunk_id": f"{doc_id}_chunk_{chunk_idx}",
                "content": chunk_content,
                "chunk_index": chunk_idx,
                "start": start,
                "end": end,
                "strategy": "length",
            })

            start = end - overlap if end < len(text) else len(text)
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
        **kwargs
    ) -> list[dict]:
        """Chunk by separators.

        Tries each separator in order, using the first one that produces
        chunks of reasonable size.
        """
        if separators is None:
            separators = ["\n\n", "\n", "。", ".", "!", "?", ";", "，", ",", " ", ""]

        chunks = []

        for sep in separators:
            if sep not in text:
                continue

            # Split by separator
            if sep:
                parts = re.split(f"({re.escape(sep)})", text)
            else:
                parts = [text]

            # Rebuild chunks with separators
            current_chunk = ""
            chunk_idx = 0

            for i, part in enumerate(parts):
                current_chunk += part

                # If this is a separator and we have content
                if sep and part == sep and len(current_chunk.strip()) > 0:
                    # Check if chunk is large enough or we're at the end
                    if len(current_chunk) >= max_length * 0.5 or i == len(parts) - 1:
                        chunks.append({
                            "chunk_id": f"{doc_id}_chunk_{chunk_idx}",
                            "content": current_chunk,
                            "chunk_index": chunk_idx,
                            "strategy": "separator",
                            "separator": sep,
                        })
                        chunk_idx += 1
                        current_chunk = ""

            # If we got chunks, use this separator
            if chunks:
                # Add any remaining content
                if current_chunk.strip():
                    chunks.append({
                        "chunk_id": f"{doc_id}_chunk_{chunk_idx}",
                        "content": current_chunk,
                        "chunk_index": chunk_idx,
                        "strategy": "separator",
                        "separator": sep,
                    })
                return chunks

        # Fallback to length-based if no separator worked
        logger.warning(f"No separator produced chunks, falling back to length-based")
        return LengthChunkStrategy().chunk(text, doc_id, max_length, overlap)


class TfidfChunkStrategy(ChunkStrategy):
    """TF-IDF based intelligent chunking.

    Uses TF-IDF similarity to group semantically related sentences/paragraphs
    into chunks of appropriate size.
    """

    def __init__(self):
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available, TF-IDF chunking will fall back to separator-based")

    def chunk(
        self,
        text: str,
        doc_id: str,
        max_length: int = 500,
        overlap: int = 50,
        separators: list[str] | None = None,
        min_similarity: float = 0.2,
        **kwargs
    ) -> list[dict]:
        """Chunk using TF-IDF similarity.

        Args:
            text: Text to chunk
            doc_id: Document ID
            max_length: Maximum chunk length in characters
            overlap: Overlap between chunks
            separators: Separators to split text into segments
            min_similarity: Minimum similarity threshold for merging segments
                (lower values = more aggressive merging)
        """
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not installed, falling back to separator-based chunking")
            return SeparatorChunkStrategy().chunk(text, doc_id, max_length, overlap, separators)

        if separators is None:
            separators = ["\n\n", "\n", "。", ".", "!", "?"]

        # Step 1: Split text into segments using separators
        segments = self._split_into_segments(text, separators)

        if len(segments) <= 1:
            # Not enough segments to use TF-IDF
            logger.info("Not enough segments for TF-IDF chunking, using separator-based")
            return SeparatorChunkStrategy().chunk(text, doc_id, max_length, overlap, separators)

        # Step 2: Calculate TF-IDF similarities between adjacent segments
        similarities = self._calculate_similarities(segments)

        # Step 3: Group segments into chunks based on similarity and length
        chunks = self._group_by_similarity(
            segments,
            similarities,
            doc_id,
            max_length,
            overlap,
            min_similarity
        )

        logger.info(f"TF-IDF chunking: {len(segments)} segments -> {len(chunks)} chunks")
        return chunks

    def _split_into_segments(self, text: str, separators: list[str]) -> list[str]:
        """Split text into segments using separators.

        Uses the first separator that produces multiple segments.
        """
        for sep in separators:
            if sep in text:
                parts = text.split(sep)
                # Filter out empty segments but preserve separators
                segments = [p + sep for p in parts[:-1] if p.strip()] + [parts[-1]]
                segments = [s for s in segments if s.strip()]

                if len(segments) > 1:
                    logger.info(f"Split into {len(segments)} segments using separator: {repr(sep[:20])}")
                    return segments

        # If no separator worked, split by paragraph/sentence
        logger.info("No effective separator found, using regex split")
        segments = re.split(r'([。！？\n]{1,2})', text)
        result = []
        current = ""

        for i, part in enumerate(segments):
            current += part
            if re.match(r'[。！？\n]{1,2}$', part) and current.strip():
                result.append(current)
                current = ""

        if current.strip():
            result.append(current)

        return result if result else [text]

    def _calculate_similarities(self, segments: list[str]) -> list[float]:
        """Calculate TF-IDF cosine similarities between adjacent segments.

        Returns:
            List of similarities where similarities[i] is the similarity between
            segments[i] and segments[i+1]
        """
        try:
            # Use TF-IDF to vectorize segments
            vectorizer = TfidfVectorizer(
                max_features=1000,
                min_df=1,
                max_df=0.95,
                ngram_range=(1, 2),  # Use unigrams and bigrams
                token_pattern=r'(?u)\b\w+\b'  # Better Chinese tokenization
            )

            # Fit and transform
            tfidf_matrix = vectorizer.fit_transform(segments)

            # Calculate cosine similarities between adjacent segments
            similarities = []
            for i in range(len(segments) - 1):
                vec1 = tfidf_matrix[i:i+1]
                vec2 = tfidf_matrix[i+1:i+2]
                sim = cosine_similarity(vec1, vec2)[0][0]
                similarities.append(float(sim))

            logger.info(f"Calculated {len(similarities)} similarities, "
                       f"min={min(similarities):.3f}, max={max(similarities):.3f}, "
                       f"mean={sum(similarities)/len(similarities):.3f}")

            return similarities

        except Exception as e:
            logger.warning(f"Failed to calculate TF-IDF similarities: {e}, using default similarities")
            # Return neutral similarities if calculation fails
            return [0.5] * (len(segments) - 1)

    def _group_by_similarity(
        self,
        segments: list[str],
        similarities: list[float],
        doc_id: str,
        max_length: int,
        overlap: int,
        min_similarity: float
    ) -> list[dict]:
        """Group segments into chunks based on similarity and length constraints.

        Strategy:
        1. Start a new chunk with the first segment
        2. For each subsequent segment:
           - If adding it would exceed max_length, start new chunk
           - If similarity to previous segment is below threshold, start new chunk
           - Otherwise, add to current chunk
        3. Handle overlap by keeping some segments from previous chunk
        """
        chunks = []
        current_chunk_segments = []
        current_length = 0
        chunk_idx = 0

        for i, segment in enumerate(segments):
            segment_length = len(segment)

            # Check if we should start a new chunk
            should_split = False

            # Condition 1: Would exceed max_length
            if current_length + segment_length > max_length and current_chunk_segments:
                should_split = True
                logger.debug(f"Splitting due to length: current={current_length}, segment={segment_length}, max={max_length}")

            # Condition 2: Similarity too low (semantic boundary)
            elif i > 0 and current_chunk_segments:
                similarity = similarities[i - 1]
                if similarity < min_similarity:
                    # Only split if we have some content already
                    if len(current_chunk_segments) >= 1:
                        should_split = True
                        logger.debug(f"Splitting due to low similarity: {similarity:.3f} < {min_similarity}")

            # Save current chunk if needed
            if should_split and current_chunk_segments:
                chunk_content = "".join(current_chunk_segments)
                chunks.append({
                    "chunk_id": f"{doc_id}_chunk_{chunk_idx}",
                    "content": chunk_content,
                    "chunk_index": chunk_idx,
                    "strategy": "tfidf",
                    "segment_count": len(current_chunk_segments),
                })
                chunk_idx += 1

                # Start new chunk with overlap
                if overlap > 0 and len(current_chunk_segments) > 1:
                    # Keep last few segments for overlap
                    overlap_length = 0
                    overlap_segments = []
                    for seg in reversed(current_chunk_segments):
                        if overlap_length + len(seg) <= overlap:
                            overlap_segments.insert(0, seg)
                            overlap_length += len(seg)
                        else:
                            break
                    current_chunk_segments = overlap_segments
                    current_length = overlap_length
                    logger.debug(f"Overlap: kept {len(overlap_segments)} segments ({overlap_length} chars)")
                else:
                    current_chunk_segments = []
                    current_length = 0

            # Add current segment
            current_chunk_segments.append(segment)
            current_length += segment_length

        # Add final chunk
        if current_chunk_segments:
            chunk_content = "".join(current_chunk_segments)
            chunks.append({
                "chunk_id": f"{doc_id}_chunk_{chunk_idx}",
                "content": chunk_content,
                "chunk_index": chunk_idx,
                "strategy": "tfidf",
                "segment_count": len(current_chunk_segments),
            })

        return chunks


def get_strategy(strategy_type: str) -> ChunkStrategy:
    """Get chunking strategy by type.

    Args:
        strategy_type: Strategy type ("length", "separator", "tfidf")

    Returns:
        ChunkStrategy instance
    """
    strategies = {
        "length": LengthChunkStrategy,
        "separator": SeparatorChunkStrategy,
        "tfidf": TfidfChunkStrategy,
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
    **kwargs
) -> list[dict]:
    """Chunk text using specified strategy.

    Args:
        text: Text to chunk
        doc_id: Document ID
        chunk_type: Chunking strategy ("length", "separator", "tfidf")
        max_length: Maximum chunk length
        overlap: Overlap between chunks
        separators: Separators for separator-based chunking
        **kwargs: Additional strategy-specific parameters

    Returns:
        List of chunk dictionaries
    """
    if separators is None:
        separators = ["\n\n", "\n", "。", ".", "!", "?", ";", "，", ",", " ", ""]

    strategy = get_strategy(chunk_type)
    chunks = strategy.chunk(
        text=text,
        doc_id=doc_id,
        max_length=max_length,
        overlap=overlap,
        separators=separators,
        **kwargs
    )

    logger.info(f"Chunked {len(text)} chars into {len(chunks)} chunks using {chunk_type} strategy")
    return chunks
