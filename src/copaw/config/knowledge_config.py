# -*- coding: utf-8 -*-
"""Knowledge base configuration for CoPaw agents."""

from pydantic import BaseModel, Field


class ChunkConfig(BaseModel):
    """Document chunking configuration."""

    chunk_type: str = Field(
        default="length",
        description="Chunk type: 'length' for max length, 'separator' for symbol split",
    )
    max_length: int = Field(default=500, description="Maximum chunk length in characters")
    overlap: int = Field(default=50, description="Overlap between chunks")
    separators: list[str] = Field(
        default=["\n\n", "\n", "。", ".", "!", "?", ";", "，", ",", " ", ""],
        description="Separators for chunk splitting",
    )


class KnowledgeBaseConfig(BaseModel):
    """Knowledge base configuration."""

    model_config = {"extra": "ignore"}

    name: str = Field(..., description="Knowledge base name")
    description: str = Field(default="", description="Knowledge base description")
    storage_type: str = Field(
        default="sqlite",
        description="Storage type: 'sqlite'",
    )
    chunk_config: ChunkConfig = Field(
        default_factory=ChunkConfig,
        description="Document chunking configuration",
    )
    enabled: bool = Field(default=True, description="Whether this knowledge base is enabled")


class AgentKnowledgeConfig(BaseModel):
    """Agent knowledge base configuration."""

    model_config = {"extra": "ignore"}

    knowledge_bases: dict[str, bool] = Field(
        default_factory=dict,
        description="Knowledge base ID to enabled mapping",
    )
