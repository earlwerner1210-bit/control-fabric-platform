"""Prompt template registry -- loads from DB or filesystem, supports interpolation."""

from __future__ import annotations

import string
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import PromptTemplate
from shared.telemetry import get_logger

logger = get_logger(__name__)


class PromptRegistry:
    """Load, cache, and render prompt templates.

    Templates are resolved in order:
    1. In-memory cache (populated from prior lookups).
    2. Database (``prompt_templates`` table).
    3. Filesystem fallback (``domain-packs/<pack>/prompts/<name>.txt``).

    Variable interpolation uses Python ``string.Template`` (``$variable``
    or ``${variable}`` syntax).
    """

    def __init__(self, base_prompts_dir: str | Path | None = None) -> None:
        self._cache: dict[str, str] = {}
        self._base_dir = Path(base_prompts_dir) if base_prompts_dir else None

    # ── Public API ─────────────────────────────────────────────────

    async def get(
        self,
        name: str,
        *,
        session: AsyncSession | None = None,
        domain_pack: str | None = None,
        version: int | None = None,
    ) -> str | None:
        """Retrieve a template by name.

        Returns ``None`` if the template cannot be found in any source.
        """
        # 1. Cache
        cache_key = self._cache_key(name, domain_pack, version)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 2. Database
        if session is not None:
            tpl = await self._load_from_db(session, name, domain_pack, version)
            if tpl is not None:
                self._cache[cache_key] = tpl
                return tpl

        # 3. Filesystem
        tpl = self._load_from_filesystem(name, domain_pack)
        if tpl is not None:
            self._cache[cache_key] = tpl
            return tpl

        logger.warning("prompt_template_not_found", name=name, domain_pack=domain_pack)
        return None

    def render(self, template: str, variables: dict[str, Any] | None = None) -> str:
        """Interpolate ``$variable`` placeholders in *template*.

        Missing variables are left as-is (safe substitution).
        """
        if not variables:
            return template
        return string.Template(template).safe_substitute(variables)

    async def get_and_render(
        self,
        name: str,
        variables: dict[str, Any] | None = None,
        *,
        session: AsyncSession | None = None,
        domain_pack: str | None = None,
        version: int | None = None,
    ) -> str | None:
        """Convenience: fetch a template and render it in one call."""
        tpl = await self.get(name, session=session, domain_pack=domain_pack, version=version)
        if tpl is None:
            return None
        return self.render(tpl, variables)

    def invalidate(self, name: str | None = None) -> None:
        """Clear cached templates. If *name* is ``None``, clear everything."""
        if name is None:
            self._cache.clear()
        else:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{name}:")]
            for k in keys_to_remove:
                del self._cache[k]

    # ── Internal helpers ───────────────────────────────────────────

    @staticmethod
    def _cache_key(name: str, domain_pack: str | None, version: int | None) -> str:
        return f"{name}:{domain_pack or '_'}:{version or 'latest'}"

    @staticmethod
    async def _load_from_db(
        session: AsyncSession,
        name: str,
        domain_pack: str | None,
        version: int | None,
    ) -> str | None:
        stmt = select(PromptTemplate.template).where(
            PromptTemplate.name == name, PromptTemplate.is_active.is_(True)
        )
        if domain_pack is not None:
            stmt = stmt.where(PromptTemplate.domain_pack == domain_pack)
        if version is not None:
            stmt = stmt.where(PromptTemplate.version == version)
        else:
            stmt = stmt.order_by(PromptTemplate.version.desc())
        stmt = stmt.limit(1)

        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        return row

    def _load_from_filesystem(self, name: str, domain_pack: str | None) -> str | None:
        if self._base_dir is None:
            return None

        if domain_pack:
            path = self._base_dir / domain_pack / "prompts" / f"{name}.txt"
        else:
            path = self._base_dir / f"{name}.txt"

        if path.is_file():
            return path.read_text(encoding="utf-8")
        return None
