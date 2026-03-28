# -*- coding: utf-8 -*-
from __future__ import annotations

import os


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_online_only_mode() -> bool:
    """Whether CoPaw should run in online-model-only mode.

    Default is enabled for this self-hosted console build to avoid loading
    unused local-model providers, routes, and scans. Set
    ``COPAW_ONLINE_ONLY=0`` to restore the full local-model stack.
    """

    return _env_flag("COPAW_ONLINE_ONLY", default=True)
