#!/usr/bin/env python3
"""Seed the database with sample tenant, user, and domain pack versions.

This script is designed to be idempotent -- it skips rows that already exist.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Hard-coded seed IDs for deterministic test references
SEED_TENANT_ID = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
SEED_USER_ID = uuid.UUID("b2c3d4e5-f6a7-8901-bcde-f12345678901")
SEED_ADMIN_ROLE_ID = uuid.UUID("c3d4e5f6-a7b8-9012-cdef-123456789012")

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/control_fabric"


async def seed(session: AsyncSession) -> None:
    """Insert sample records if they do not already exist."""

    now = datetime.now(timezone.utc)

    # ── Tenant ────────────────────────────────────────────────────────────
    exists = await session.execute(
        text("SELECT 1 FROM tenants WHERE id = :id"), {"id": SEED_TENANT_ID}
    )
    if exists.scalar() is None:
        await session.execute(
            text(
                "INSERT INTO tenants (id, name, slug, is_active, created_at, updated_at) "
                "VALUES (:id, :name, :slug, true, :now, :now)"
            ),
            {
                "id": SEED_TENANT_ID,
                "name": "Acme Field Services",
                "slug": "acme",
                "now": now,
            },
        )
        print(f"  Inserted tenant: Acme Field Services ({SEED_TENANT_ID})")
    else:
        print("  Tenant already exists, skipping.")

    # ── Role ──────────────────────────────────────────────────────────────
    exists = await session.execute(
        text("SELECT 1 FROM roles WHERE id = :id"), {"id": SEED_ADMIN_ROLE_ID}
    )
    if exists.scalar() is None:
        await session.execute(
            text(
                "INSERT INTO roles (id, name, description, created_at, updated_at) "
                "VALUES (:id, :name, :desc, :now, :now)"
            ),
            {
                "id": SEED_ADMIN_ROLE_ID,
                "name": "admin",
                "desc": "Platform administrator",
                "now": now,
            },
        )
        print(f"  Inserted role: admin ({SEED_ADMIN_ROLE_ID})")

    # ── User ──────────────────────────────────────────────────────────────
    exists = await session.execute(
        text("SELECT 1 FROM users WHERE id = :id"), {"id": SEED_USER_ID}
    )
    if exists.scalar() is None:
        # bcrypt hash of "password123"
        hashed = "$2b$12$LJ3m4ys2gOPveC0gN2kn1.Y9bJm7P1pWqF6Lb/nGg7nRzDmS0qS3e"
        await session.execute(
            text(
                "INSERT INTO users (id, tenant_id, email, hashed_password, full_name, is_active, created_at, updated_at) "
                "VALUES (:id, :tid, :email, :pw, :name, true, :now, :now)"
            ),
            {
                "id": SEED_USER_ID,
                "tid": SEED_TENANT_ID,
                "email": "admin@acme-field.example.com",
                "pw": hashed,
                "name": "Admin User",
                "now": now,
            },
        )
        print(f"  Inserted user: admin@acme-field.example.com ({SEED_USER_ID})")

        # Link user -> role
        await session.execute(
            text(
                "INSERT INTO user_roles (user_id, role_id) VALUES (:uid, :rid)"
            ),
            {"uid": SEED_USER_ID, "rid": SEED_ADMIN_ROLE_ID},
        )
        print("  Linked user -> admin role")
    else:
        print("  User already exists, skipping.")

    # ── Domain Pack Versions ──────────────────────────────────────────────
    packs = [
        ("contract-margin", "1.0.0", "Contract margin assurance rules and prompts"),
        ("utilities-field", "1.0.0", "Utilities field operations readiness rules"),
        ("telco-ops", "1.0.0", "Telecom incident and SLA management rules"),
    ]
    for pack_name, version, description in packs:
        exists = await session.execute(
            text(
                "SELECT 1 FROM domain_pack_versions WHERE pack_name = :pn AND version = :v"
            ),
            {"pn": pack_name, "v": version},
        )
        if exists.scalar() is None:
            await session.execute(
                text(
                    "INSERT INTO domain_pack_versions (id, pack_name, version, description, is_active, created_at, updated_at) "
                    "VALUES (:id, :pn, :v, :desc, true, :now, :now)"
                ),
                {
                    "id": uuid.uuid4(),
                    "pn": pack_name,
                    "v": version,
                    "desc": description,
                    "now": now,
                },
            )
            print(f"  Inserted domain pack: {pack_name} v{version}")
        else:
            print(f"  Domain pack {pack_name} v{version} already exists, skipping.")

    await session.commit()
    print("\nSeed complete.")


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
