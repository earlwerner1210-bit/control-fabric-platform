"""Configuration helpers."""

from __future__ import annotations

from functools import lru_cache

from shared.config.settings import Environment, Settings

__all__ = ["Environment", "Settings", "get_settings"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton ``Settings`` instance."""
    return Settings()
