"""Alembic async migration environment.

Reads DATABASE_URL from ``app.core.config`` settings or falls back to the
``sqlalchemy.url`` value in *alembic.ini*.  Supports both **offline**
(SQL-script) and **online** (asyncpg) migration modes.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Importing the models package triggers all per-file model registrations.
import app.db.models  # noqa: F401

# ---------------------------------------------------------------------------
# Target metadata – import the declarative Base used by every ORM model and
# then force-import the model package so that all table definitions are
# registered on ``Base.metadata`` before Alembic inspects it.
# ---------------------------------------------------------------------------
from app.db.base import Base

# ---------------------------------------------------------------------------
# Alembic Config object – provides access to values in alembic.ini.
# ---------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_url() -> str:
    """Return the async database URL.

    Resolution order:
    1. ``DATABASE_URL`` environment variable (allows CI / Docker override).
    2. ``app.core.config.get_settings().DATABASE_URL`` (application settings).
    3. ``sqlalchemy.url`` from *alembic.ini* (local-dev fallback).
    """
    # 1. Direct env-var override
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        # Ensure the URL uses the asyncpg driver even if the env-var was set
        # with the generic ``postgresql://`` scheme.
        return env_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # 2. Application settings
    try:
        from app.core.config import get_settings

        settings = get_settings()
        return settings.DATABASE_URL
    except Exception:
        pass

    # 3. Fallback to alembic.ini
    return config.get_main_option("sqlalchemy.url", "")


# ---------------------------------------------------------------------------
# Offline migrations (emit SQL to stdout)
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.
    Calls to ``context.execute()`` emit the given string to the script
    output.
    """
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online (async) migrations
# ---------------------------------------------------------------------------


def do_run_migrations(connection) -> None:  # noqa: ANN001
    """Synchronous callback executed inside ``run_sync``."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations inside its connection."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry-point for online (async) migrations."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
