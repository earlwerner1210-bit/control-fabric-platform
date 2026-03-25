"""Seed script -- loads sample data into the database for development and testing.

Usage:
    python data/seed/seed_data.py

Requires:
    - PostgreSQL running with the control_fabric database
    - Alembic migrations already applied
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/control_fabric",
)

DATA_DIR = PROJECT_ROOT / "data"
SAMPLE_CONTRACTS_DIR = DATA_DIR / "sample-contracts"
SAMPLE_WORK_ORDERS_DIR = DATA_DIR / "sample-work-orders"
SAMPLE_INCIDENTS_DIR = DATA_DIR / "sample-incidents"
SAMPLE_RUNBOOKS_DIR = DATA_DIR / "sample-runbooks"

# ---------------------------------------------------------------------------
# IDs (deterministic for repeatability)
# ---------------------------------------------------------------------------

TENANT_ID = "00000000-0000-0000-0000-000000000001"
ADMIN_USER_ID = "00000000-0000-0000-0000-000000000010"
OPERATOR_USER_ID = "00000000-0000-0000-0000-000000000011"
ROLE_ADMIN_ID = "00000000-0000-0000-0000-000000000020"
ROLE_OPERATOR_ID = "00000000-0000-0000-0000-000000000021"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    """Load a JSON file from disk."""
    with open(path) as f:
        return json.load(f)


def _hash_password(password: str) -> str:
    """Create a simple password hash for seeding (not for production)."""
    import hashlib
    import secrets

    salt = "seed-salt-do-not-use-in-prod"
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations=100_000)
    return f"{salt}${h.hex()}"


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------


async def seed_tenant(session: AsyncSession) -> None:
    """Create the default tenant."""
    await session.execute(
        text(
            "INSERT INTO tenants (id, name, slug, is_active) "
            "VALUES (:id, :name, :slug, true) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {"id": TENANT_ID, "name": "Default Tenant", "slug": "default"},
    )
    print("  [+] Created default tenant")


async def seed_roles(session: AsyncSession) -> None:
    """Create admin and operator roles."""
    roles = [
        {
            "id": ROLE_ADMIN_ID,
            "name": "admin",
            "description": "Full platform access",
            "permissions": json.dumps({"all": True}),
        },
        {
            "id": ROLE_OPERATOR_ID,
            "name": "operator",
            "description": "Operational access to cases and documents",
            "permissions": json.dumps({"cases": True, "documents": True}),
        },
    ]
    for role in roles:
        await session.execute(
            text(
                "INSERT INTO roles (id, name, description, permissions) "
                "VALUES (:id, :name, :description, :permissions::jsonb) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            role,
        )
    print("  [+] Created roles: admin, operator")


async def seed_users(session: AsyncSession) -> None:
    """Create admin and operator users."""
    users = [
        {
            "id": ADMIN_USER_ID,
            "email": "admin@controlfabric.io",
            "hashed_password": _hash_password("admin123"),
            "full_name": "Admin User",
            "is_active": True,
            "tenant_id": TENANT_ID,
            "role_id": ROLE_ADMIN_ID,
        },
        {
            "id": OPERATOR_USER_ID,
            "email": "operator@controlfabric.io",
            "hashed_password": _hash_password("operator123"),
            "full_name": "Operator User",
            "is_active": True,
            "tenant_id": TENANT_ID,
            "role_id": ROLE_OPERATOR_ID,
        },
    ]
    for user in users:
        await session.execute(
            text(
                "INSERT INTO users (id, email, hashed_password, full_name, is_active, tenant_id, role_id) "
                "VALUES (:id, :email, :hashed_password, :full_name, :is_active, :tenant_id, :role_id) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            user,
        )
    print("  [+] Created users: admin@controlfabric.io, operator@controlfabric.io")


async def seed_documents(session: AsyncSession) -> None:
    """Load sample documents into the database."""
    doc_dirs = [
        (SAMPLE_CONTRACTS_DIR, "contract"),
        (SAMPLE_WORK_ORDERS_DIR, "work_order"),
        (SAMPLE_INCIDENTS_DIR, "incident"),
        (SAMPLE_RUNBOOKS_DIR, "runbook"),
    ]
    count = 0
    for dir_path, doc_type in doc_dirs:
        if not dir_path.is_dir():
            continue
        for json_file in sorted(dir_path.glob("*.json")):
            doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, json_file.name))
            content = _load_json(json_file)
            await session.execute(
                text(
                    "INSERT INTO documents (id, tenant_id, filename, content_type, s3_key, "
                    "size_bytes, checksum, status, metadata) "
                    "VALUES (:id, :tenant_id, :filename, :content_type, :s3_key, "
                    ":size_bytes, :checksum, :status, :metadata::jsonb) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "id": doc_id,
                    "tenant_id": TENANT_ID,
                    "filename": json_file.name,
                    "content_type": "application/json",
                    "s3_key": f"documents/{TENANT_ID}/{doc_id}/{json_file.name}",
                    "size_bytes": json_file.stat().st_size,
                    "checksum": str(uuid.uuid5(uuid.NAMESPACE_DNS, json.dumps(content))),
                    "status": "uploaded",
                    "metadata": json.dumps({"document_type": doc_type, "source": "seed"}),
                },
            )
            count += 1
    print(f"  [+] Loaded {count} sample documents")


async def seed_prompt_templates(session: AsyncSession) -> None:
    """Create prompt templates for each domain pack."""
    templates = [
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "contract-margin/extract_clauses")),
            "name": "extract_clauses",
            "version": 1,
            "domain_pack": "contract-margin",
            "template": (
                "Extract all clauses from the following contract text. "
                "For each clause, identify the type (obligation, penalty, sla, rate, scope), "
                "the section reference, and the full text.\n\n"
                "Contract:\n{contract_text}\n\n"
                "Return a JSON array of clauses."
            ),
            "variables": json.dumps(["contract_text"]),
            "tenant_id": TENANT_ID,
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "contract-margin/assess_billability")),
            "name": "assess_billability",
            "version": 1,
            "domain_pack": "contract-margin",
            "template": (
                "Assess whether the following work event is billable under the given contract terms.\n\n"
                "Work Event:\n{work_event}\n\n"
                "Contract Terms:\n{contract_terms}\n\n"
                "Return a JSON object with 'billable' (bool), 'confidence' (float), and 'reasons' (list)."
            ),
            "variables": json.dumps(["work_event", "contract_terms"]),
            "tenant_id": TENANT_ID,
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "contract-margin/diagnose_leakage")),
            "name": "diagnose_leakage",
            "version": 1,
            "domain_pack": "contract-margin",
            "template": (
                "Analyze the following billing data against contract terms and identify margin leakage.\n\n"
                "Billing Data:\n{billing_data}\n\n"
                "Contract Terms:\n{contract_terms}\n\n"
                "Return a JSON object with 'verdict', 'leakage_drivers', and 'recommendations'."
            ),
            "variables": json.dumps(["billing_data", "contract_terms"]),
            "tenant_id": TENANT_ID,
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "utilities-field/check_readiness")),
            "name": "check_readiness",
            "version": 1,
            "domain_pack": "utilities-field",
            "template": (
                "Evaluate whether the following work order is ready for field dispatch.\n\n"
                "Work Order:\n{work_order}\n\n"
                "Return a JSON object with 'ready' (bool), 'blockers' (list), and 'warnings' (list)."
            ),
            "variables": json.dumps(["work_order"]),
            "tenant_id": TENANT_ID,
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "telco-ops/triage_incident")),
            "name": "triage_incident",
            "version": 1,
            "domain_pack": "telco-ops",
            "template": (
                "Triage the following incident and recommend dispatch and escalation actions.\n\n"
                "Incident:\n{incident}\n\n"
                "Runbook:\n{runbook}\n\n"
                "Return a JSON object with 'assigned_team', 'escalation_level', and 'recommended_actions'."
            ),
            "variables": json.dumps(["incident", "runbook"]),
            "tenant_id": TENANT_ID,
        },
    ]
    for tmpl in templates:
        await session.execute(
            text(
                "INSERT INTO prompt_templates (id, name, version, domain_pack, template, variables, tenant_id) "
                "VALUES (:id, :name, :version, :domain_pack, :template, :variables::jsonb, :tenant_id) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            tmpl,
        )
    print(f"  [+] Created {len(templates)} prompt templates")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    """Run all seed functions."""
    print("=== Seeding Control Fabric Platform ===\n")

    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        try:
            await seed_tenant(session)
            await seed_roles(session)
            await seed_users(session)
            await seed_documents(session)
            await seed_prompt_templates(session)
            await session.commit()
            print("\n=== Seed complete ===")
        except Exception as e:
            await session.rollback()
            print(f"\n[ERROR] Seed failed: {e}")
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
