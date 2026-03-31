"""
PostgreSQL Row-Level Security (RLS) setup.

Ensures tenant_id isolation is enforced at the database level,
not just the application layer.

Usage:
    python -m app.db.rls apply
    python -m app.db.rls verify
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from sqlalchemy import text

logger = logging.getLogger(__name__)

TABLES_WITH_TENANT = [
    "control_objects",
    "control_edges",
    "reconciliation_cases",
    "evidence_packages",
    "audit_log",
    "exception_requests",
    "platform_users",
    "alert_configs",
]

RLS_SQL = """
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON {table};
CREATE POLICY tenant_isolation ON {table}
    USING (tenant_id = current_setting('app.current_tenant', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true));
"""

VERIFY_SQL = """
SELECT tablename, rowsecurity, forcerowsecurity
FROM pg_tables
WHERE schemaname = 'public'
AND tablename = ANY(ARRAY[{table_list}])
ORDER BY tablename;
"""


async def apply_rls() -> None:
    """Apply row-level security to all tenant-scoped tables."""
    from sqlalchemy.ext.asyncio import create_async_engine

    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        print("DATABASE_URL not set — skipping RLS setup")
        return

    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        for table in TABLES_WITH_TENANT:
            try:
                await conn.execute(text(RLS_SQL.format(table=table)))
                logger.info("RLS applied: %s", table)
                print(f"  ✓ RLS applied: {table}")
            except Exception as e:
                logger.warning("RLS apply failed for %s: %s", table, e)
                print(f"  ⚠ RLS skipped: {table} — {e}")
    await engine.dispose()
    print("\nRLS setup complete.")


async def verify_rls() -> None:
    """Verify RLS is enabled on all tenant tables."""
    from sqlalchemy.ext.asyncio import create_async_engine

    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        print("DATABASE_URL not set — cannot verify RLS")
        return

    engine = create_async_engine(db_url)
    table_list = ", ".join([f"'{t}'" for t in TABLES_WITH_TENANT])
    async with engine.connect() as conn:
        result = await conn.execute(text(VERIFY_SQL.format(table_list=table_list)))
        rows = result.fetchall()
        print(f"\n{'Table':<30} {'RLS Enabled':<15} {'Forced'}")
        print("─" * 55)
        for row in rows:
            status = "✓" if row[1] else "✗"
            forced = "✓" if row[2] else "✗"
            print(f"  {row[0]:<28} {status:<15} {forced}")
        not_enabled = [r[0] for r in rows if not r[1]]
        if not_enabled:
            print(f"\n⚠ RLS NOT enabled on: {not_enabled}")
        else:
            print(f"\n✓ RLS enabled on all {len(rows)} tenant tables")
    await engine.dispose()


async def set_tenant_context(conn, tenant_id: str) -> None:
    """Set the tenant context for a database connection."""
    await conn.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.db.rls [apply|verify]")
        sys.exit(1)
    command = sys.argv[1]
    if command == "apply":
        asyncio.run(apply_rls())
    elif command == "verify":
        asyncio.run(verify_rls())
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
