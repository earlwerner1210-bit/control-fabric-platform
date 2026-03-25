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


def run_wave1_demo():
    """Run Wave 1 contract-margin scenario using seed fixtures.

    This function loads the Wave 1 fixtures and demonstrates how to use
    them with the domain-pack parsers and rule engines. It does not
    require a running database.
    """
    import sys as _sys

    # Ensure project root is on path
    _sys.path.insert(0, str(PROJECT_ROOT))

    from app.domain_packs.contract_margin.parsers import ContractParser, SPENRateCardParser
    from app.domain_packs.contract_margin.compiler import ContractCompiler
    from app.domain_packs.contract_margin.rules import (
        BillabilityRuleEngine,
        LeakageRuleEngine,
        RecoveryRecommendationEngine,
    )
    from app.domain_packs.reconciliation import (
        ContractWorkOrderLinker,
        MarginEvidenceAssembler,
    )

    fixtures_dir = DATA_DIR / "fixtures"

    # ---------------------------------------------------------------
    # 1. Load fixtures
    # ---------------------------------------------------------------
    print("=== Wave 1 Demo: Contract-Margin Scenario ===\n")

    contract_margin = _load_json(fixtures_dir / "wave1_contract_margin.json")
    margin_leakage = _load_json(fixtures_dir / "wave1_margin_leakage.json")
    penalty_scenario = _load_json(fixtures_dir / "wave1_penalty_scenario.json")

    print(f"  Loaded scenario: {contract_margin['scenario']}")
    print(f"  Loaded leakage scenario: {margin_leakage['scenario']}")
    print(f"  Loaded penalty scenario: {penalty_scenario['scenario']}")

    # ---------------------------------------------------------------
    # 2. Parse contract
    # ---------------------------------------------------------------
    parser = ContractParser()
    parsed = parser.parse_contract(contract_margin["contract"])
    print(f"\n--- Parsed Contract ---")
    print(f"  Title: {parsed.title}")
    print(f"  Parties: {', '.join(parsed.parties)}")
    print(f"  Clauses: {len(parsed.clauses)}")
    print(f"  Rate card entries: {len(parsed.rate_card)}")
    print(f"  SLA entries: {len(parsed.sla_table)}")

    # ---------------------------------------------------------------
    # 3. Compile contract
    # ---------------------------------------------------------------
    compiler = ContractCompiler()
    compiled = compiler.compile(parsed)
    print(f"\n--- Compiled Control Objects ---")
    print(f"  Clause objects: {len(compiled.clauses)}")
    print(f"  SLA entries: {len(compiled.sla_entries)}")
    print(f"  Rate card entries: {len(compiled.rate_card_entries)}")
    print(f"  Obligations: {len(compiled.obligations)}")
    print(f"  Penalties: {len(compiled.penalties)}")
    print(f"  Total control objects: {len(compiled.control_object_payloads)}")

    # ---------------------------------------------------------------
    # 4. Run billability checks on each work order
    # ---------------------------------------------------------------
    billability_engine = BillabilityRuleEngine()
    obligations = [{"text": c.text, "description": c.text} for c in parsed.clauses]

    print(f"\n--- Billability Checks ---")
    for wo in contract_margin["work_orders"]:
        for item in wo.get("billable_items", []):
            activity = item["description"].lower().replace(" ", "_")
            decision = billability_engine.evaluate(
                activity=activity,
                rate_card=parsed.rate_card,
                obligations=obligations,
            )
            status = "BILLABLE" if decision.billable else "NON-BILLABLE"
            print(f"  {wo['work_order_id']} / {item['description']}: {status} "
                  f"(rate={decision.rate_applied}, confidence={decision.confidence:.2f})")

    # ---------------------------------------------------------------
    # 5. Run leakage detection
    # ---------------------------------------------------------------
    leakage_engine = LeakageRuleEngine()
    triggers = leakage_engine.evaluate(
        [], work_history=margin_leakage["work_history"]
    )
    print(f"\n--- Leakage Detection ---")
    print(f"  Total triggers: {len(triggers)}")
    for t in triggers:
        print(f"  [{t.severity.upper()}] {t.trigger_type}: {t.description}")

    # ---------------------------------------------------------------
    # 6. Generate recovery recommendations
    # ---------------------------------------------------------------
    recovery_engine = RecoveryRecommendationEngine()
    recommendations = recovery_engine.build_recommendations(
        leakage_triggers=triggers,
        contract_objects=[],
        rate_card=[],
    )
    print(f"\n--- Recovery Recommendations ---")
    print(f"  Total recommendations: {len(recommendations)}")
    for r in recommendations:
        print(f"  [{r.priority.value.upper()}] {r.recommendation_type.value}: {r.description}")

    # ---------------------------------------------------------------
    # 7. Cross-pack reconciliation
    # ---------------------------------------------------------------
    contract_objects = [
        {"type": "rate_card", "activity": rc.activity, "rate": rc.rate,
         "unit": rc.unit, "id": rc.activity}
        for rc in parsed.rate_card
    ]
    linker = ContractWorkOrderLinker()

    print(f"\n--- Cross-Pack Reconciliation ---")
    total_links = 0
    for wo in contract_margin["work_orders"]:
        links = linker.link(contract_objects, wo)
        total_links += len(links)
        for link in links:
            print(f"  {link.source_id} -> {link.target_id} ({link.link_type}, "
                  f"confidence={link.confidence:.3f})")
    print(f"  Total cross-pack links: {total_links}")

    # ---------------------------------------------------------------
    # 8. Evidence bundle assembly
    # ---------------------------------------------------------------
    work_history = [
        {"work_order_id": wo["work_order_id"], "description": wo["description"],
         "activity": wo.get("work_category", ""), "status": wo.get("status", "")}
        for wo in contract_margin["work_orders"]
    ]
    trigger_dicts = [t.model_dump() for t in triggers]
    assembler = MarginEvidenceAssembler()
    bundle = assembler.assemble(contract_objects, work_history, trigger_dicts)
    print(f"\n--- Evidence Bundle ---")
    print(f"  Bundle ID: {bundle.bundle_id}")
    print(f"  Domains: {', '.join(bundle.domains)}")
    print(f"  Evidence items: {bundle.total_items}")
    print(f"  Confidence: {bundle.confidence:.3f}")

    # ---------------------------------------------------------------
    # 9. Penalty scenario summary
    # ---------------------------------------------------------------
    print(f"\n--- Penalty Scenario ---")
    breaches = penalty_scenario["breach_events"]
    total_pct = sum(b["penalty_percentage"] for b in breaches if b["breach"])
    cap = penalty_scenario["expected_outcomes"]["cap_percentage"]
    capped_pct = min(total_pct, cap)
    monthly = penalty_scenario["monthly_invoice_value"]
    exposure = monthly * capped_pct / 100
    print(f"  Total breaches: {len(breaches)}")
    print(f"  Uncapped penalty: {total_pct}%")
    print(f"  Cap: {cap}%")
    print(f"  Penalty exposure: £{exposure:,.2f}")
    print(f"  Service improvement plan triggered: {capped_pct >= 20}")

    print(f"\n=== Wave 1 Demo Complete ===")


if __name__ == "__main__":
    import sys as _main_sys

    if len(_main_sys.argv) > 1 and _main_sys.argv[1] == "--demo":
        run_wave1_demo()
    else:
        asyncio.run(main())
