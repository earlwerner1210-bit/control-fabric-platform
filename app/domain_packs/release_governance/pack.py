"""
Release Governance Pack — Wedge Solution

The first named use case for the Control-Native Decision Platform.

One-sentence pitch:
  Detect every ungoverned release decision in your control environment
  and enforce evidence-gated approval before anything ships.

Packaged contents:
  - Typed control object schemas for release artefacts
  - Relationship types for release dependency chains
  - Reconciliation rules for release governance gaps
  - Validation policies for release evidence requirements
  - Severity model for release risk classification
  - Default evidence requirements per release type

Target buyer: Head of Engineering, VP Release, CISO in regulated industries.
Target pain: "We cannot prove what was approved, by whom, with what evidence,
              before it went to production."

Author: Control Fabric Platform
Date: March 2026
"""

from __future__ import annotations

from app.core.domain_pack_loader import DomainPack
from app.core.graph.domain_types import ControlObjectType, RelationshipType
from app.core.reconciliation.cross_plane_engine import (
    ReconciliationCaseSeverity,
    ReconciliationRule,
)
from app.core.registry.domain_types import SchemaNamespace

RELEASE_GOVERNANCE_PACK = DomainPack(
    pack_id="release-governance-v1",
    name="release-governance",
    version="1.0.0",
    description=(
        "Release Governance Pack: detect and govern every release decision. "
        "Enforces evidence-gated approval chains for software, configuration, "
        "and policy releases across regulated environments."
    ),
    namespaces=[
        SchemaNamespace(
            name="release-governance",
            version="1.0.0",
            domain_pack="release-governance",
            object_type=ControlObjectType.DOMAIN_PACK_EXTENSION,
            required_attributes=["release_type", "target_environment", "risk_tier"],
            optional_attributes=[
                "approver_id",
                "ticket_ref",
                "rollback_plan",
                "blast_radius",
                "deployment_window",
                "evidence_package_id",
            ],
            description="Release governance control objects",
        ),
        SchemaNamespace(
            name="release-policy",
            version="1.0.0",
            domain_pack="release-governance",
            object_type=ControlObjectType.OPERATIONAL_POLICY,
            required_attributes=["policy_type", "applies_to_environment"],
            optional_attributes=[
                "min_approvers",
                "required_evidence_types",
                "embargo_windows",
            ],
            description="Release policy objects",
        ),
        SchemaNamespace(
            name="release-evidence",
            version="1.0.0",
            domain_pack="release-governance",
            object_type=ControlObjectType.ASSET,
            required_attributes=["evidence_type", "source_system", "freshness_ttl_hours"],
            optional_attributes=["test_coverage_pct", "scan_result", "approval_token"],
            description="Release evidence objects — test results, scan reports, approvals",
        ),
    ],
    reconciliation_rules=[
        ReconciliationRule(
            rule_id="RG-001",
            domain_pack="release-governance",
            rule_name="release_must_satisfy_policy",
            description=(
                "Every active release object must satisfy at least one release policy. "
                "A release with no governing policy is an ungoverned release."
            ),
            source_plane="operations",
            target_plane="operations",
            source_object_type=ControlObjectType.DOMAIN_PACK_EXTENSION,
            target_object_type=ControlObjectType.OPERATIONAL_POLICY,
            required_relationship=RelationshipType.SATISFIES,
            severity=ReconciliationCaseSeverity.CRITICAL,
        ),
        ReconciliationRule(
            rule_id="RG-002",
            domain_pack="release-governance",
            rule_name="release_policy_must_implement_compliance_requirement",
            description=(
                "Every release policy must implement at least one compliance requirement. "
                "Policies with no compliance backing are unverifiable."
            ),
            source_plane="operations",
            target_plane="compliance",
            source_object_type=ControlObjectType.OPERATIONAL_POLICY,
            target_object_type=ControlObjectType.COMPLIANCE_REQUIREMENT,
            required_relationship=RelationshipType.IMPLEMENTS,
            severity=ReconciliationCaseSeverity.HIGH,
        ),
        ReconciliationRule(
            rule_id="RG-003",
            domain_pack="release-governance",
            rule_name="release_evidence_must_mitigate_risk",
            description=(
                "Every release evidence object must mitigate at least one identified risk. "
                "Evidence that mitigates no risk provides no governance value."
            ),
            source_plane="operations",
            target_plane="risk",
            source_object_type=ControlObjectType.ASSET,
            target_object_type=ControlObjectType.RISK_CONTROL,
            required_relationship=RelationshipType.MITIGATES,
            severity=ReconciliationCaseSeverity.HIGH,
        ),
    ],
    metadata={
        "target_industries": [
            "financial_services",
            "healthcare",
            "telecom",
            "government",
        ],
        "target_roles": ["head_of_engineering", "vp_release", "ciso", "cto"],
        "one_liner": "Detect and govern every release decision before it ships.",
        "value_proposition": (
            "Prove to auditors, regulators, and the board exactly what was approved, "
            "by whom, with what evidence, before every production release."
        ),
    },
)
