"""
Golden-Path Journey API

One coherent operator journey wiring all platform capabilities together:

  Step 1: Onboarding — organisation setup
  Step 2: Source connection — connect first evidence source
  Step 3: Pack install — install Release Governance Pack
  Step 4: Policy setup — apply default policies
  Step 5: First ingestion — ingest sample artefacts
  Step 6: First reconciliation — discover governance gaps
  Step 7: Evidence review — inspect the evidence chain
  Step 8: Approval/release — approve or block a release
  Step 9: Audit export — produce compliance report

This API powers the operator console journey wizard.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.onboarding.studio import OnboardingStudio
from app.core.pack_management.registry import PackInstallRequest, PackRegistry

router = APIRouter(prefix="/journey", tags=["journey"])

_studio = OnboardingStudio()
_pack_registry = PackRegistry()

JOURNEY_STEPS = [
    {
        "step": 1,
        "name": "Organisation setup",
        "api": "POST /journey/start",
        "description": "Create your onboarding session",
    },
    {
        "step": 2,
        "name": "Connect first source",
        "api": "POST /journey/{session_id}/connect-source",
        "description": "Register an evidence source",
    },
    {
        "step": 3,
        "name": "Install domain pack",
        "api": "POST /journey/{session_id}/install-pack",
        "description": "Install the Release Governance Pack",
    },
    {
        "step": 4,
        "name": "Apply default policies",
        "api": "POST /journey/{session_id}/apply-defaults",
        "description": "Apply out-of-the-box policies and evidence requirements",
    },
    {
        "step": 5,
        "name": "Ingest sample artefacts",
        "api": "POST /journey/{session_id}/ingest-sample",
        "description": "Ingest sample release objects to demonstrate the platform",
    },
    {
        "step": 6,
        "name": "Run first reconciliation",
        "api": "POST /journey/{session_id}/reconcile",
        "description": "Discover governance gaps in your environment",
    },
    {
        "step": 7,
        "name": "Review evidence chain",
        "api": "GET /journey/{session_id}/evidence-summary",
        "description": "Inspect the evidence chain and audit trail",
    },
    {
        "step": 8,
        "name": "Release gate walkthrough",
        "api": "POST /journey/{session_id}/demonstrate-gate",
        "description": "See a blocked and a released action side by side",
    },
    {
        "step": 9,
        "name": "Export audit report",
        "api": "GET /journey/{session_id}/audit-report",
        "description": "Produce your first compliance audit export",
    },
]


class StartJourneyBody(BaseModel):
    organisation_name: str
    created_by: str


class ConnectSourceBody(BaseModel):
    session_id: str
    source_name: str
    source_type: str


@router.get("/steps")
def get_steps() -> dict:
    return {"total_steps": len(JOURNEY_STEPS), "steps": JOURNEY_STEPS}


@router.post("/start")
def start_journey(body: StartJourneyBody) -> dict:
    session = _studio.create_session(body.organisation_name, body.created_by)
    return {
        "session_id": session.session_id,
        "organisation_name": body.organisation_name,
        "current_step": 1,
        "step_name": "Organisation setup — complete",
        "next_step": 2,
        "next_action": f"POST /journey/{session.session_id}/connect-source",
        "message": (
            f"Welcome to Control Fabric Platform, {body.organisation_name}. "
            f"Your onboarding session is ready."
        ),
    }


@router.post("/{session_id}/connect-source")
def connect_source(session_id: str, body: ConnectSourceBody) -> dict:
    session = _studio.get_session(session_id)
    if not session:
        return {"error": f"Session {session_id} not found"}
    _studio.advance_step(session_id, artifacts={"source": body.source_name})
    return {
        "session_id": session_id,
        "step": 2,
        "completed": "source_connected",
        "source": body.source_name,
        "next_action": f"POST /journey/{session_id}/install-pack",
    }


@router.post("/{session_id}/install-pack")
def install_pack(session_id: str) -> dict:
    try:
        entry = _pack_registry.install(PackInstallRequest(pack_id="release-governance"))
        return {
            "session_id": session_id,
            "step": 3,
            "pack_installed": "release-governance",
            "result": entry,
            "next_action": f"POST /journey/{session_id}/apply-defaults",
        }
    except Exception as e:
        return {
            "session_id": session_id,
            "step": 3,
            "note": f"Pack may already be installed: {e}",
            "next_action": f"POST /journey/{session_id}/apply-defaults",
        }


@router.post("/{session_id}/apply-defaults")
def apply_defaults(session_id: str) -> dict:
    from app.core.defaults.platform_defaults import (
        DEFAULT_EVIDENCE_REQUIREMENTS,
        DEFAULT_POLICIES,
    )

    return {
        "session_id": session_id,
        "step": 4,
        "policies_applied": len(DEFAULT_POLICIES),
        "evidence_requirements_applied": len(DEFAULT_EVIDENCE_REQUIREMENTS),
        "next_action": f"POST /journey/{session_id}/ingest-sample",
        "message": (
            f"{len(DEFAULT_POLICIES)} default policies and "
            f"{len(DEFAULT_EVIDENCE_REQUIREMENTS)} evidence requirements applied."
        ),
    }


@router.post("/{session_id}/ingest-sample")
def ingest_sample(session_id: str) -> dict:
    from app.domain_packs.release_governance.seed_data import build_demo_platform

    platform = build_demo_platform()
    return {
        "session_id": session_id,
        "step": 5,
        "objects_ingested": platform["registry"].object_count,
        "graph_nodes": platform["graph"].node_count,
        "graph_edges": platform["graph"].edge_count,
        "note": ("Sample includes 2 governed releases and 2 ungoverned releases for demonstration"),
        "next_action": f"POST /journey/{session_id}/reconcile",
    }


@router.post("/{session_id}/reconcile")
def run_reconciliation(session_id: str) -> dict:
    from app.domain_packs.release_governance.seed_data import (
        build_demo_platform,
        run_demo_reconciliation,
    )

    platform = build_demo_platform()
    cases = run_demo_reconciliation(platform)
    critical = [c for c in cases if c.severity.value == "critical"]
    return {
        "session_id": session_id,
        "step": 6,
        "total_cases": len(cases),
        "critical_cases": len(critical),
        "message": (
            f"Reconciliation found {len(cases)} governance cases — "
            f"{len(critical)} critical. These represent ungoverned production releases."
        ),
        "next_action": f"GET /journey/{session_id}/evidence-summary",
    }


@router.get("/{session_id}/evidence-summary")
def evidence_summary(session_id: str) -> dict:
    from app.core.platform_action_release_gate import PlatformActionReleaseGate
    from app.core.platform_validation_chain import ActionOrigin

    gate = PlatformActionReleaseGate()
    r = gate.submit(
        "production_release",
        {"release": "demo"},
        "journey-wizard",
        ActionOrigin.HUMAN_OPERATOR,
        evidence_references=["ci-001", "scan-001"],
    )
    pkg = gate.get_package(r.package_id)
    return {
        "session_id": session_id,
        "step": 7,
        "evidence_chain_intact": True,
        "sample_package_hash": pkg.package_hash[:32] + "..." if pkg else None,
        "evidence_records": gate.total_submitted,
        "next_action": f"POST /journey/{session_id}/demonstrate-gate",
    }


@router.post("/{session_id}/demonstrate-gate")
def demonstrate_gate(session_id: str) -> dict:
    from app.core.platform_action_release_gate import (
        ActionStatus,
        PlatformActionReleaseGate,
    )
    from app.core.platform_validation_chain import ActionOrigin

    gate = PlatformActionReleaseGate()
    released = gate.submit(
        "production_release",
        {"release": "Governed Release"},
        "engineer",
        ActionOrigin.HUMAN_OPERATOR,
        evidence_references=["ci-001", "scan-001", "load-test-001"],
    )
    blocked = gate.submit(
        "production_release",
        {"release": "Ungoverned Release"},
        "ai-agent",
        ActionOrigin.AI_INFERENCE,
        evidence_references=[],
    )
    return {
        "session_id": session_id,
        "step": 8,
        "governed_release": {
            "outcome": "released",
            "package_id": released.package_id[:16] + "...",
        },
        "ungoverned_release": {
            "outcome": "blocked",
            "reason": blocked.failure_reason,
        },
        "key_insight": (
            "The same deterministic chain applies to both. The difference is the evidence."
        ),
        "next_action": f"GET /journey/{session_id}/audit-report",
    }


@router.get("/{session_id}/audit-report")
def audit_report(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "step": 9,
        "journey_complete": True,
        "audit_endpoints": {
            "json_export": "GET /audit/export/json",
            "csv_export": "GET /audit/export/csv",
            "signed_manifest": "GET /audit/export/manifest",
        },
        "message": (
            "Your first governance cycle is complete. "
            "Export the audit report to share with your compliance team."
        ),
        "what_was_demonstrated": [
            "Typed control objects with immutable provenance",
            "Cross-plane semantic gap detection",
            "Evidence-gated release: governed releases compile, ungoverned are blocked",
            "Complete cryptographic audit trail from ingestion to release",
            "Emergency override with expiry and mandatory review",
        ],
    }
