"""
Control Fabric Platform — Canonical Vocabulary

This module freezes the exact terms used across the platform.
No drift. No alternate phrasing. These terms are used in:
  - Code comments
  - API documentation
  - Patent claims
  - Patent counsel briefings
  - PR descriptions
  - Investor materials

Any variation from these terms weakens the patent claim.

Author: Control Fabric Platform
Date: March 2026
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Platform name — never vary this
# ---------------------------------------------------------------------------

PLATFORM_NAME = "Control-Native Decision Platform"

# NOT: "AI governance platform"
# NOT: "AI platform with governance"
# NOT: "governance AI platform"


# ---------------------------------------------------------------------------
# Output taxonomy — strictly ordered, never blur these classes
# ---------------------------------------------------------------------------


class OutputClass:
    """
    The strict taxonomy of platform outputs.

    Patent Claim: The platform enforces this taxonomy structurally.
    Observations and findings never trigger actions.
    Hypotheses never bypass the validation chain.
    Proposed actions never execute without an evidence package.
    Released actions always carry a cryptographic evidence package.
    """

    OBSERVATION = "observation"  # Raw data point — no governance weight
    FINDING = "finding"  # Validated observation — no action authority
    HYPOTHESIS = "hypothesis"  # AI-generated structured proposal — never executable
    PROPOSED_ACTION = "proposed_action"  # Validated hypothesis → candidate for release
    RELEASED_ACTION = "released_action"  # Evidence-packaged, gate-cleared, dispatched


# ---------------------------------------------------------------------------
# Core architectural terms — use exactly these, always
# ---------------------------------------------------------------------------

CANONICAL_TERMS = {
    "control_object": "A typed, versioned, lifecycle-managed enterprise governance primitive",
    "control_graph": "A semantic graph of typed relationships between control objects",
    "cross_plane_reconciliation": (
        "Continuous detection of semantic gaps, conflicts, and orphans across operational planes"
    ),
    "bounded_reasoning": (
        "Policy-gated, scope-bounded AI inference constrained to producing hypotheses only"
    ),
    "deterministic_validation_chain": (
        "A sequential boolean pipeline governing ALL platform outputs regardless of origin"
    ),
    "evidence_gated_release": (
        "Cryptographic binding of an action to its complete evidence chain before dispatch"
    ),
    "domain_pack": (
        "A runtime extension that injects new schemas and rules without modifying core architecture"
    ),
    "evidence_package": (
        "An inseparable bundle of action + validation certificate + evidence chain + provenance"
    ),
    "control_fabric": (
        "The unified substrate connecting all control objects, relationships, and governance rules"
    ),
}


# ---------------------------------------------------------------------------
# The one sentence that describes this platform
# ---------------------------------------------------------------------------

PLATFORM_DESCRIPTION = (
    "A control-native decision platform in which all candidate outputs, "
    "regardless of origin, must pass through a shared deterministic validation "
    "chain and an evidence-gated release mechanism before they can affect "
    "platform state or produce governed output."
)


# ---------------------------------------------------------------------------
# What this platform is NOT
# ---------------------------------------------------------------------------

ANTI_PATTERNS = [
    "AI governance platform",
    "AI platform with controls",
    "AI compliance tool",
    "LLM governance layer",
    "prompt safety system",
    "AI guardrails platform",
]
