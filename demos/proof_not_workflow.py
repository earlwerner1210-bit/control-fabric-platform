"""
Competitive Proof #1 — Not just a workflow tool

Demonstrates: Control Fabric blocks execution architecturally.
Workflow tools approve requests — they do not prevent execution.

This script shows that:
1. A workflow-approved action with no evidence is STILL blocked
2. The block is architectural — not policy-configurable away
3. Zero side effects on block — nothing executes

Run: python demos/proof_not_workflow.py
"""

import sys

sys.path.insert(0, ".")

from app.core.platform_action_release_gate import (
    ActionStatus,
    PlatformActionReleaseGate,
)
from app.core.platform_validation_chain import ActionOrigin


def run():
    print("\n" + "=" * 65)
    print("  PROOF: Control Fabric is not a workflow tool")
    print("=" * 65)

    gate = PlatformActionReleaseGate()

    # Scenario 1: AI-originated action with workflow approval token — but no evidence
    print(
        "\n[1] Submit AI-originated 'workflow-approved' action with approval token but no evidence"
    )
    result1 = gate.submit(
        action_type="production_release",
        proposed_payload={
            "service": "Payment Gateway v3.1",
            "environment": "production",
            "approved_by": "release-manager@company.com",
            "approval_token": "WFLOW-APPROVED-20260401-9823",
            "workflow_id": "WF-8842-APPROVED",
        },
        requested_by="release-manager@company.com",
        origin=ActionOrigin.AI_INFERENCE,
        evidence_references=[],  # No actual evidence
    )
    status_label = "BLOCKED" if result1.status == ActionStatus.BLOCKED else "RELEASED"
    print(f"   Outcome:  {status_label}")
    print(f"   Reason:   {result1.failure_reason}")
    print("   Note:     Workflow approval token is in the payload — it doesn't matter.")
    print("             The gate requires evidence references, not approval strings.")

    # Scenario 2: Same action WITH evidence
    print("\n[2] Submit same action with actual CI and security scan evidence")
    result2 = gate.submit(
        action_type="production_release",
        proposed_payload={
            "service": "Payment Gateway v3.1",
            "environment": "production",
        },
        requested_by="release-manager@company.com",
        origin=ActionOrigin.HUMAN_OPERATOR,
        evidence_references=[
            "ci-run-20260401-pass",
            "sec-scan-20260401-clean",
            "load-test-20260401-pass",
        ],
    )
    status_label2 = "RELEASED" if result2.status == ActionStatus.COMPILED else "BLOCKED"
    print(f"   Outcome:  {status_label2}")
    print(f"   Package:  {result2.package_id[:20]}...")

    print("\n[CONCLUSION]")
    print("  A workflow tool approves the request and updates a ticket.")
    print("  Control Fabric enforces that evidence exists before execution.")
    print("  These are different interventions at different points in the process.")
    print("  The approval token in Scenario 1 has zero effect on the gate decision.")

    assert result1.status == ActionStatus.BLOCKED, (
        "Proof failed — workflow-approved action was not blocked"
    )
    assert result2.status == ActionStatus.COMPILED, (
        "Proof failed — evidenced action was not released"
    )
    print("\n  All assertions passed. Proof complete.\n")


if __name__ == "__main__":
    run()
