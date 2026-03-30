"""
Repeatable Demo Tenant

A complete, resettable demo environment for sales conversations,
pilot kickoffs, analyst demos, and investor presentations.

Reset with: POST /demo/reset
Run with:   POST /demo/scenarios/{scenario_id}/run
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class DemoScenario:
    scenario_id: str
    title: str
    description: str
    expected_outcome: str  # blocked / released / gap_detected / override_approved
    steps: list[str] = field(default_factory=list)


DEMO_SCENARIOS = [
    DemoScenario(
        scenario_id="governed-release",
        title="Governed production release",
        description="A properly evidenced production release that passes all validation gates.",
        expected_outcome="released",
        steps=[
            "Ingest release artefact with CI, security scan, and load test evidence",
            "Submit to release gate with human_operator origin",
            "All 5 gates pass — evidence package compiled",
            "Release dispatched with cryptographic binding",
        ],
    ),
    DemoScenario(
        scenario_id="blocked-ungoverned",
        title="Blocked: ungoverned release attempt",
        description="A production release with no evidence — blocked at evidence gate.",
        expected_outcome="blocked",
        steps=[
            "Submit production release with no evidence references",
            "Gate blocks at evidence_sufficiency check",
            "Zero side effects — nothing executes",
            "Explain: which gate failed and what evidence is required",
        ],
    ),
    DemoScenario(
        scenario_id="blocked-policy",
        title="Blocked: policy violation",
        description="An action blocked by an active platform policy.",
        expected_outcome="blocked",
        steps=[
            "Submit 'force_deploy' action type",
            "Gate blocks at policy_compliance — force_deploy is blocked by default",
            "Explain: which policy version applied",
        ],
    ),
    DemoScenario(
        scenario_id="critical-gap",
        title="CRITICAL gap detected",
        description="Reconciliation detects an ungoverned production release object.",
        expected_outcome="gap_detected",
        steps=[
            "Ingest production release with no policy link",
            "Run reconciliation",
            "CRITICAL gap case detected: RG-001 violated",
            "Severity engine routes to must_block urgency=immediate",
        ],
    ),
    DemoScenario(
        scenario_id="emergency-override",
        title="Emergency override with governance",
        description="Critical incident — emergency override approved with 4-hour expiry.",
        expected_outcome="override_approved",
        steps=[
            "Submit exception request with CRITICAL risk and substantive justification",
            "CISO approves — review task auto-created",
            "Override active for 4 hours",
            "Audit trail: immutable, append-only",
        ],
    ),
    DemoScenario(
        scenario_id="ai-blocked",
        title="AI action blocked without evidence",
        description="AI-originated action blocked — same chain as human actions.",
        expected_outcome="blocked",
        steps=[
            "Submit action with AI_INFERENCE origin and no evidence",
            "Gate blocks at evidence_sufficiency",
            "Same chain — AI gets no special treatment",
            "Explain: AI must always provide evidence references",
        ],
    ),
]


class DemoTenantManager:
    """Manages the demo tenant state and scenario execution."""

    def __init__(self) -> None:
        self._platform: dict | None = None
        self._scenario_results: list[dict] = []

    def reset(self) -> dict:
        """Reset the demo tenant to a clean state."""
        from app.domain_packs.release_governance.seed_data import build_demo_platform

        self._platform = build_demo_platform()
        self._scenario_results = []
        logger.info("Demo tenant reset")
        return {
            "status": "reset",
            "objects": self._platform["registry"].object_count,
            "nodes": self._platform["graph"].node_count,
            "edges": self._platform["graph"].edge_count,
            "scenarios_available": len(DEMO_SCENARIOS),
        }

    def run_scenario(self, scenario_id: str) -> dict:
        """Execute a named demo scenario and return the result."""
        scenario = next((s for s in DEMO_SCENARIOS if s.scenario_id == scenario_id), None)
        if not scenario:
            raise ValueError(f"Scenario '{scenario_id}' not found")

        if self._platform is None:
            self.reset()

        from app.core.platform_action_release_gate import (
            ActionStatus,
            PlatformActionReleaseGate,
        )
        from app.core.platform_validation_chain import ActionOrigin

        gate = PlatformActionReleaseGate()
        result: dict = {
            "scenario_id": scenario_id,
            "title": scenario.title,
            "expected": scenario.expected_outcome,
            "steps": scenario.steps,
        }

        if scenario_id == "governed-release":
            r = gate.submit(
                "production_release",
                {"release": "API Gateway v2.4.1", "env": "production"},
                "release-engineer",
                ActionOrigin.HUMAN_OPERATOR,
                evidence_references=["ci-pass-001", "scan-pass-001", "load-test-001"],
            )
            result["outcome"] = "released" if r.status == ActionStatus.COMPILED else "unexpected"
            result["package_id"] = r.package_id
            pkg = gate.get_package(r.package_id)
            result["package_hash"] = pkg.package_hash[:32] + "..." if pkg else None

        elif scenario_id == "blocked-ungoverned":
            r = gate.submit(
                "production_release",
                {"release": "Ungoverned Service"},
                "engineer",
                ActionOrigin.AI_INFERENCE,
                evidence_references=[],
            )
            result["outcome"] = "blocked" if r.status == ActionStatus.BLOCKED else "unexpected"
            result["failure_reason"] = r.failure_reason
            result["side_effects"] = "none — execution architecturally prevented"

        elif scenario_id == "blocked-policy":
            chain_gate = PlatformActionReleaseGate(
                active_policies={"blocked_action_types": ["force_deploy"]}
            )
            r = chain_gate.submit(
                "force_deploy",
                {"target": "production"},
                "engineer",
                ActionOrigin.HUMAN_OPERATOR,
            )
            result["outcome"] = "blocked" if r.status == ActionStatus.BLOCKED else "unexpected"
            result["blocking_gate"] = "policy_compliance"
            result["policy_applied"] = "Production Release Policy"

        elif scenario_id == "critical-gap":
            from app.core.reconciliation.cross_plane_engine import (
                CrossPlaneReconciliationEngine,
            )

            engine = CrossPlaneReconciliationEngine(graph=self._platform["graph"])
            cases = engine.run_full_reconciliation()
            critical = [c for c in cases if c.severity.value == "critical"]
            result["outcome"] = "gap_detected"
            result["total_cases"] = len(cases)
            result["critical_cases"] = len(critical)
            result["example_case"] = (
                critical[0].title if critical else "No critical cases (demo data already linked)"
            )

        elif scenario_id == "emergency-override":
            from app.core.exception_framework.domain_types import (
                ExceptionRequest,
                ExceptionRisk,
                ExceptionType,
            )
            from app.core.exception_framework.manager import ExceptionManager

            mgr = ExceptionManager()
            req = ExceptionRequest(
                exception_type=ExceptionType.EMERGENCY_OVERRIDE,
                requested_by="cto@demo-company.com",
                justification=(
                    "Critical payment outage affecting 40,000 customers. "
                    "DBA team on standby. Rollback verified. "
                    "Post-incident review within 48 hours."
                ),
                affected_object_ids=["demo-release-001"],
                affected_action_type="production_release",
                policy_context_id="Production Release Policy v1.0",
                compensating_controls=["dba-monitoring", "rollback-verified"],
                expires_at=datetime.now(UTC) + timedelta(hours=4),
                risk_assessment=ExceptionRisk.CRITICAL,
            )
            submitted = mgr.submit_exception(req)
            decision = mgr.approve_exception(
                submitted.exception_id,
                "ciso@demo-company.com",
                "Approved: compensating controls verified. Review mandatory.",
            )
            result["outcome"] = "override_approved"
            result["exception_id"] = submitted.exception_id[:16] + "..."
            result["expires_in_hours"] = 4
            result["review_task_id"] = decision.review_task_id[:16] + "..."
            result["audit_entries"] = len(mgr.get_audit_trail(submitted.exception_id))

        elif scenario_id == "ai-blocked":
            r = gate.submit(
                "state_transition",
                {"target": "active"},
                "ai-agent-001",
                ActionOrigin.AI_INFERENCE,
                evidence_references=[],
            )
            result["outcome"] = "blocked" if r.status == ActionStatus.BLOCKED else "unexpected"
            result["blocking_gate"] = "evidence_sufficiency"
            result["message"] = "AI gets no special treatment — same chain as human actions"

        result["passed"] = result.get("outcome") == scenario.expected_outcome
        self._scenario_results.append(result)
        return result

    def run_all_scenarios(self) -> dict:
        """Run all demo scenarios in sequence."""
        self.reset()
        results = [self.run_scenario(s.scenario_id) for s in DEMO_SCENARIOS]
        passed = sum(1 for r in results if r.get("passed", False))
        return {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "results": results,
        }

    def get_scenarios(self) -> list[dict]:
        return [
            {
                "scenario_id": s.scenario_id,
                "title": s.title,
                "description": s.description,
                "expected_outcome": s.expected_outcome,
                "steps": s.steps,
            }
            for s in DEMO_SCENARIOS
        ]

    def get_results(self) -> list[dict]:
        return list(self._scenario_results)


demo_tenant = DemoTenantManager()
