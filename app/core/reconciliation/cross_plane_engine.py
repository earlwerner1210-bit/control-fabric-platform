from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.core.graph.domain_types import ControlObject, ControlObjectType, RelationshipType
from app.core.graph.store import ControlGraphStore

logger = logging.getLogger(__name__)


class ReconciliationCaseType(str, Enum):
    GAP = "gap"
    CONFLICT = "conflict"
    DUPLICATE = "duplicate"
    MATCH = "match"
    ORPHAN = "orphan"


class ReconciliationCaseSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReconciliationCaseStatus(str, Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    ACCEPTED_RISK = "accepted_risk"


class ReconciliationCase(BaseModel):
    case_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    case_type: ReconciliationCaseType
    severity: ReconciliationCaseSeverity
    status: ReconciliationCaseStatus = Field(default=ReconciliationCaseStatus.OPEN)
    title: str
    description: str
    affected_object_ids: list[str]
    affected_planes: list[str]
    violated_rule_id: str | None = None
    missing_relationship_type: RelationshipType | None = None
    conflicting_edge_ids: list[str] = Field(default_factory=list)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    severity_score: int = Field(default=0)
    remediation_suggestions: list[str] = Field(default_factory=list)
    case_hash: str = Field(default="")

    @model_validator(mode="after")
    def compute_case_hash(self) -> ReconciliationCase:
        payload = f"{self.case_type}{self.severity}{sorted(self.affected_object_ids)}{sorted(self.affected_planes)}{self.violated_rule_id}{self.detected_at.isoformat()}"
        self.case_hash = hashlib.sha256(payload.encode()).hexdigest()
        return self


class ReconciliationRule(BaseModel):
    rule_id: str
    domain_pack: str
    rule_name: str
    description: str
    source_plane: str
    target_plane: str
    source_object_type: ControlObjectType
    target_object_type: ControlObjectType
    required_relationship: RelationshipType
    severity: ReconciliationCaseSeverity
    enabled: bool = Field(default=True)


def build_core_reconciliation_rules() -> list[ReconciliationRule]:
    return [
        ReconciliationRule(
            rule_id="CORE-001",
            domain_pack="core",
            rule_name="risk_control_must_mitigate_vulnerability",
            description="Every active risk control must mitigate at least one vulnerability",
            source_plane="risk",
            target_plane="risk",
            source_object_type=ControlObjectType.RISK_CONTROL,
            target_object_type=ControlObjectType.VULNERABILITY,
            required_relationship=RelationshipType.MITIGATES,
            severity=ReconciliationCaseSeverity.HIGH,
        ),
        ReconciliationRule(
            rule_id="CORE-002",
            domain_pack="core",
            rule_name="technical_control_must_satisfy_compliance",
            description="Every technical control must satisfy at least one compliance requirement",
            source_plane="security",
            target_plane="compliance",
            source_object_type=ControlObjectType.TECHNICAL_CONTROL,
            target_object_type=ControlObjectType.COMPLIANCE_REQUIREMENT,
            required_relationship=RelationshipType.SATISFIES,
            severity=ReconciliationCaseSeverity.CRITICAL,
        ),
        ReconciliationRule(
            rule_id="CORE-003",
            domain_pack="core",
            rule_name="compliance_requirement_must_satisfy_mandate",
            description="Every compliance requirement must link to a regulatory mandate",
            source_plane="compliance",
            target_plane="compliance",
            source_object_type=ControlObjectType.COMPLIANCE_REQUIREMENT,
            target_object_type=ControlObjectType.REGULATORY_MANDATE,
            required_relationship=RelationshipType.SATISFIES,
            severity=ReconciliationCaseSeverity.CRITICAL,
        ),
        ReconciliationRule(
            rule_id="CORE-004",
            domain_pack="core",
            rule_name="security_control_must_implement_policy",
            description="Every security control must implement an operational policy",
            source_plane="security",
            target_plane="operations",
            source_object_type=ControlObjectType.SECURITY_CONTROL,
            target_object_type=ControlObjectType.OPERATIONAL_POLICY,
            required_relationship=RelationshipType.IMPLEMENTS,
            severity=ReconciliationCaseSeverity.MEDIUM,
        ),
    ]


class CrossPlaneReconciliationEngine:
    def __init__(
        self, graph: ControlGraphStore, rules: list[ReconciliationRule] | None = None
    ) -> None:
        self._graph = graph
        self._rules = rules or build_core_reconciliation_rules()
        self._cases: dict[str, ReconciliationCase] = {}
        self._case_index_by_object: dict[str, list[str]] = {}

    def run_full_reconciliation(self) -> list[ReconciliationCase]:
        new_cases: list[ReconciliationCase] = []
        for rule in self._rules:
            if rule.enabled:
                new_cases.extend(self._evaluate_rule(rule))
        new_cases.extend(self._detect_conflicts())
        new_cases.extend(self._detect_orphans())
        for case in new_cases:
            self._commit_case(case)
        return new_cases

    def _evaluate_rule(self, rule: ReconciliationRule) -> list[ReconciliationCase]:
        cases = []
        for source_obj in self._graph.get_objects_by_type(rule.source_object_type.value):
            if not source_obj.is_active():
                continue
            outbound_edges = self._graph.get_outbound_edges(
                source_obj.object_id, [rule.required_relationship]
            )
            has_required_link = any(
                (target := self._graph.get_object(e.target_object_id)) is not None
                and target.object_type == rule.target_object_type
                and target.operational_plane == rule.target_plane
                and target.is_active()
                for e in outbound_edges
            )
            if not has_required_link:
                cases.append(
                    ReconciliationCase(
                        case_type=ReconciliationCaseType.GAP,
                        severity=rule.severity,
                        title=f"GAP: {source_obj.name} lacks required {rule.required_relationship.value} link",
                        description=f"Rule '{rule.rule_name}': Active {rule.source_object_type.value} '{source_obj.name}' in plane '{rule.source_plane}' has no '{rule.required_relationship.value}' relationship to any active {rule.target_object_type.value} in plane '{rule.target_plane}'.",
                        affected_object_ids=[source_obj.object_id],
                        affected_planes=[rule.source_plane, rule.target_plane],
                        violated_rule_id=rule.rule_id,
                        missing_relationship_type=rule.required_relationship,
                        severity_score=self._compute_severity_score(rule.severity, [source_obj]),
                        remediation_suggestions=[
                            f"Create a '{rule.required_relationship.value}' relationship from '{source_obj.name}' to an appropriate {rule.target_object_type.value}.",
                            f"Review whether '{source_obj.name}' should be deprecated if no applicable {rule.target_object_type.value} exists.",
                        ],
                    )
                )
        return cases

    def _detect_conflicts(self) -> list[ReconciliationCase]:
        cases = []
        conflict_rels = [RelationshipType.CONFLICTS, RelationshipType.VIOLATES]
        for edge_id, edge in self._graph._edges.items():
            if edge.relationship_type not in conflict_rels or not edge.is_active:
                continue
            source = self._graph.get_object(edge.source_object_id)
            target = self._graph.get_object(edge.target_object_id)
            if not source or not target or not source.is_active() or not target.is_active():
                continue
            cases.append(
                ReconciliationCase(
                    case_type=ReconciliationCaseType.CONFLICT,
                    severity=ReconciliationCaseSeverity.CRITICAL,
                    title=f"CONFLICT: '{source.name}' {edge.relationship_type.value} '{target.name}'",
                    description=f"Active conflict: '{source.name}' ({source.operational_plane}) has a '{edge.relationship_type.value}' relationship with '{target.name}' ({target.operational_plane}).",
                    affected_object_ids=[source.object_id, target.object_id],
                    affected_planes=list({source.operational_plane, target.operational_plane}),
                    conflicting_edge_ids=[edge_id],
                    severity_score=100,
                    remediation_suggestions=[
                        f"Review the conflict between '{source.name}' and '{target.name}'.",
                        "Update one or both objects to resolve the incompatibility.",
                    ],
                )
            )
        return cases

    def _detect_orphans(self) -> list[ReconciliationCase]:
        cases = []
        for obj in self._graph.get_active_objects():
            if not self._graph.get_outbound_edges(
                obj.object_id
            ) and not self._graph.get_inbound_edges(obj.object_id):
                cases.append(
                    ReconciliationCase(
                        case_type=ReconciliationCaseType.ORPHAN,
                        severity=ReconciliationCaseSeverity.MEDIUM,
                        title=f"ORPHAN: '{obj.name}' has no governance relationships",
                        description=f"Active {obj.object_type.value} '{obj.name}' in plane '{obj.operational_plane}' has no relationships.",
                        affected_object_ids=[obj.object_id],
                        affected_planes=[obj.operational_plane],
                        severity_score=40,
                        remediation_suggestions=[
                            f"Link '{obj.name}' to at least one related control object.",
                            f"If '{obj.name}' is no longer relevant, deprecate it.",
                        ],
                    )
                )
        return cases

    def _commit_case(self, case: ReconciliationCase) -> None:
        self._cases[case.case_id] = case
        for obj_id in case.affected_object_ids:
            self._case_index_by_object.setdefault(obj_id, []).append(case.case_id)

    @staticmethod
    def _compute_severity_score(
        severity: ReconciliationCaseSeverity, objects: list[ControlObject]
    ) -> int:
        base = {"critical": 100, "high": 70, "medium": 40, "low": 10}.get(severity.value, 10)
        return base + len(objects)

    def get_open_cases(self) -> list[ReconciliationCase]:
        return [c for c in self._cases.values() if c.status == ReconciliationCaseStatus.OPEN]

    def get_cases_by_severity(
        self, severity: ReconciliationCaseSeverity
    ) -> list[ReconciliationCase]:
        return [c for c in self._cases.values() if c.severity == severity]

    def get_cases_for_object(self, object_id: str) -> list[ReconciliationCase]:
        return [
            self._cases[cid]
            for cid in self._case_index_by_object.get(object_id, [])
            if cid in self._cases
        ]

    @property
    def total_cases(self) -> int:
        return len(self._cases)

    @property
    def open_case_count(self) -> int:
        return len(self.get_open_cases())
