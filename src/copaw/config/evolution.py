# -*- coding: utf-8 -*-
"""Evolution configuration model."""

from typing import Optional

from pydantic import BaseModel, Field


class EvolutionConfig(BaseModel):
    """Evolution configuration for digital life evolution."""

    enabled: bool = Field(default=False, description="Enable evolution feature")
    auto_evolution: bool = Field(
        default=False,
        description="Enable automatic evolution via cron",
    )
    max_generations: Optional[int] = Field(
        default=None,
        description="Maximum generation limit (None or 0 for unlimited)",
    )
    archive_enabled: bool = Field(
        default=True,
        description="Enable archiving of evolution snapshots",
    )
    model_name: Optional[str] = Field(
        default=None,
        description="Model to use for evolution (None = use active model)",
    )
