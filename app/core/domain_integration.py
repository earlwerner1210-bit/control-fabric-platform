"""Domain pack integration — registers domain-specific kinds, rules, policies into the fabric."""

from __future__ import annotations

from app.core.audit import FabricAuditHook
from app.core.reconciliation.domain_types import (
    CrossPlaneMismatchCategory,
    ExpectedPlaneCoverage,
    ReconciliationMismatch,
    ReconciliationRuleId,
)
from app.core.reconciliation.rule_model import (
    CostAlignmentRule,
    QuantityAlignmentRule,
    ReconciliationRule,
    ReconciliationRuleApplicability,
    ReconciliationRuleCategory,
    ReconciliationRuleExplanation,
    ReconciliationRuleRegistry,
    ReconciliationRuleResult,
    ReconciliationRuleWeight,
)
from app.core.reconciliation.rules import (
    BillingWithoutCompletionRule,
    MissingEvidenceRule,
    ObligationUnmetRule,
    QuantityDiscrepancyRule,
    RateDeviationRule,
    ScopeMatchRule,
)
from app.core.registry import (
    ActionPolicySpec,
    FabricRegistry,
    LinkPolicySpec,
    ObjectKindSpec,
    ReconciliationRuleSpec,
)
from app.core.types import ControlLinkType, ControlObjectType, PlaneType


def register_contract_margin(registry: FabricRegistry) -> None:
    """Register contract-margin domain pack kinds and policies."""
    registry.register_object_kind(
        ObjectKindSpec(
            kind_name="extracted_clause",
            object_type=ControlObjectType.OBLIGATION,
            allowed_planes=[PlaneType.COMMERCIAL],
            domain="contract_margin",
            description="Clause extracted from a contract document",
            required_payload_fields=["clause_text", "clause_type"],
        )
    )
    registry.register_object_kind(
        ObjectKindSpec(
            kind_name="rate_card_entry",
            object_type=ControlObjectType.RATE_CARD,
            allowed_planes=[PlaneType.COMMERCIAL],
            domain="contract_margin",
            description="Rate card entry from contract",
            required_payload_fields=["rate", "unit"],
        )
    )
    registry.register_object_kind(
        ObjectKindSpec(
            kind_name="billable_event",
            object_type=ControlObjectType.BILLABLE_EVENT,
            allowed_planes=[PlaneType.COMMERCIAL],
            domain="contract_margin",
            description="A billable event from field or service data",
            required_payload_fields=["amount"],
        )
    )
    registry.register_object_kind(
        ObjectKindSpec(
            kind_name="leakage_trigger",
            object_type=ControlObjectType.LEAKAGE_TRIGGER,
            allowed_planes=[PlaneType.COMMERCIAL],
            domain="contract_margin",
            description="Margin leakage trigger detected by rules",
        )
    )
    registry.register_object_kind(
        ObjectKindSpec(
            kind_name="margin_diagnosis",
            object_type=ControlObjectType.RECONCILIATION_CASE,
            allowed_planes=[PlaneType.COMMERCIAL, PlaneType.FIELD],
            domain="contract_margin",
            description="Margin diagnosis reconciliation case",
        )
    )

    registry.register_link_policy(
        LinkPolicySpec(
            source_kind="billable_event",
            target_kind="rate_card_entry",
            allowed_link_types=[ControlLinkType.BILLS_FOR, ControlLinkType.DERIVES_FROM],
        )
    )
    registry.register_link_policy(
        LinkPolicySpec(
            source_kind="leakage_trigger",
            target_kind="extracted_clause",
            allowed_link_types=[ControlLinkType.EVIDENCES, ControlLinkType.CONTRADICTS],
        )
    )

    registry.register_reconciliation_rule(
        ReconciliationRuleSpec(
            rule_name="contract_rate_deviation",
            domain="contract_margin",
            description="Rate deviation between contract and billing",
            source_kind="rate_card_entry",
            target_kind="billable_event",
            planes=[PlaneType.COMMERCIAL],
            priority=10,
        )
    )

    registry.register_action_policy(
        ActionPolicySpec(
            action_type="credit_note",
            domain="contract_margin",
            description="Issue credit note for overcharge",
            required_object_kinds=["billable_event", "rate_card_entry"],
            required_evidence_types=["clause_extraction", "rate_comparison"],
            requires_approval=True,
        )
    )
    registry.register_action_policy(
        ActionPolicySpec(
            action_type="invoice_adjustment",
            domain="contract_margin",
            description="Adjust invoice for rate deviation",
            required_object_kinds=["billable_event"],
            requires_approval=True,
        )
    )


def register_telco_ops(registry: FabricRegistry) -> None:
    """Register telco-ops domain pack kinds and policies."""
    registry.register_object_kind(
        ObjectKindSpec(
            kind_name="incident_state",
            object_type=ControlObjectType.INCIDENT_STATE,
            allowed_planes=[PlaneType.SERVICE],
            domain="telco_ops",
            description="Parsed incident state from service management",
        )
    )
    registry.register_object_kind(
        ObjectKindSpec(
            kind_name="escalation_rule",
            object_type=ControlObjectType.ESCALATION_RULE,
            allowed_planes=[PlaneType.SERVICE],
            domain="telco_ops",
            description="SLA escalation rule",
        )
    )
    registry.register_object_kind(
        ObjectKindSpec(
            kind_name="service_state",
            object_type=ControlObjectType.SERVICE_STATE,
            allowed_planes=[PlaneType.SERVICE],
            domain="telco_ops",
            description="Current service state object",
        )
    )

    registry.register_link_policy(
        LinkPolicySpec(
            source_kind="incident_state",
            target_kind="service_state",
            allowed_link_types=[ControlLinkType.IMPACTS, ControlLinkType.CORRELATES_WITH],
        )
    )
    registry.register_link_policy(
        LinkPolicySpec(
            source_kind="escalation_rule",
            target_kind="incident_state",
            allowed_link_types=[ControlLinkType.IMPLEMENTS, ControlLinkType.BLOCKS],
        )
    )

    registry.register_reconciliation_rule(
        ReconciliationRuleSpec(
            rule_name="sla_breach_check",
            domain="telco_ops",
            description="SLA breach detection across service incidents",
            source_kind="incident_state",
            target_kind="service_state",
            planes=[PlaneType.SERVICE],
            priority=8,
        )
    )

    registry.register_action_policy(
        ActionPolicySpec(
            action_type="sla_escalation",
            domain="telco_ops",
            description="Escalate SLA breach",
            required_object_kinds=["incident_state"],
            requires_approval=False,
            auto_release=True,
        )
    )


def register_utilities_field(registry: FabricRegistry) -> None:
    """Register utilities-field domain pack kinds and policies."""
    registry.register_object_kind(
        ObjectKindSpec(
            kind_name="work_order",
            object_type=ControlObjectType.WORK_ORDER,
            allowed_planes=[PlaneType.FIELD],
            domain="utilities_field",
            description="Parsed work order from field operations",
            required_payload_fields=["work_order_id"],
        )
    )
    registry.register_object_kind(
        ObjectKindSpec(
            kind_name="readiness_check",
            object_type=ControlObjectType.READINESS_CHECK,
            allowed_planes=[PlaneType.FIELD],
            domain="utilities_field",
            description="Field readiness gate check",
        )
    )
    registry.register_object_kind(
        ObjectKindSpec(
            kind_name="completion_certificate",
            object_type=ControlObjectType.COMPLETION_CERTIFICATE,
            allowed_planes=[PlaneType.FIELD],
            domain="utilities_field",
            description="Work completion certificate",
        )
    )

    registry.register_link_policy(
        LinkPolicySpec(
            source_kind="work_order",
            target_kind="completion_certificate",
            allowed_link_types=[ControlLinkType.FULFILLS],
        )
    )
    registry.register_link_policy(
        LinkPolicySpec(
            source_kind="readiness_check",
            target_kind="work_order",
            allowed_link_types=[ControlLinkType.VALIDATES, ControlLinkType.BLOCKS],
        )
    )
    registry.register_link_policy(
        LinkPolicySpec(
            source_kind="work_order",
            target_kind="incident_state",
            allowed_link_types=[ControlLinkType.FULFILLS, ControlLinkType.CORRELATES_WITH],
            required_cross_plane=True,
        )
    )

    registry.register_reconciliation_rule(
        ReconciliationRuleSpec(
            rule_name="field_completion_billing",
            domain="utilities_field",
            description="Field completion vs billing reconciliation",
            source_kind="completion_certificate",
            target_kind="billable_event",
            planes=[PlaneType.FIELD, PlaneType.COMMERCIAL],
            priority=9,
        )
    )

    registry.register_action_policy(
        ActionPolicySpec(
            action_type="work_order_dispatch",
            domain="utilities_field",
            description="Dispatch work order to field crew",
            required_object_kinds=["work_order", "readiness_check"],
            requires_approval=False,
        )
    )


def register_all_domain_packs(
    registry: FabricRegistry,
    audit_hook: FabricAuditHook | None = None,
) -> None:
    """Register all known domain packs."""
    register_contract_margin(registry)
    register_telco_ops(registry)
    register_utilities_field(registry)

    if audit_hook:
        for domain_name in ("contract_margin", "telco_ops", "utilities_field"):
            kinds = registry.list_object_kinds(domain=domain_name)
            audit_hook.domain_pack_registered(domain=domain_name, kind_count=len(kinds))


# ── Wave 2: Domain pack reconciliation rule registration ──


class ContractMarginCostRule(CostAlignmentRule):
    """Contract-margin domain pack: cost alignment with tighter threshold."""

    rule_id = ReconciliationRuleId("contract-margin-cost-alignment")
    category = ReconciliationRuleCategory.COST_ALIGNMENT
    weight = ReconciliationRuleWeight(
        rule_id=ReconciliationRuleId("contract-margin-cost-alignment"),
        weight=2.0,
        is_hard_fail=False,
    )
    applicability = ReconciliationRuleApplicability(
        applicable_planes=[PlaneType.COMMERCIAL, PlaneType.FIELD],
        applicable_object_kinds=["rate_card_entry", "billable_event"],
        requires_cross_plane=True,
    )

    def __init__(self) -> None:
        super().__init__(cost_field="rate", threshold=0.005)


class TelcoOpsStateAlignmentRule(ReconciliationRule):
    """Telco-ops domain pack: service state alignment for SLA tracking."""

    rule_id = ReconciliationRuleId("telco-ops-service-state-alignment")
    category = ReconciliationRuleCategory.STATE_ALIGNMENT
    weight = ReconciliationRuleWeight(
        rule_id=ReconciliationRuleId("telco-ops-service-state-alignment"),
        weight=1.5,
        is_hard_fail=False,
    )
    applicability = ReconciliationRuleApplicability(
        applicable_planes=[PlaneType.SERVICE],
        applicable_object_kinds=["incident_state", "service_state"],
    )

    def evaluate(self, source, target, links) -> ReconciliationRuleResult:
        src_sla = source.payload.get("sla_status")
        tgt_sla = target.payload.get("sla_status")
        if src_sla is not None and tgt_sla is not None and src_sla != tgt_sla:
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=0.0,
                matched=False,
                mismatches=[
                    ReconciliationMismatch(
                        category=CrossPlaneMismatchCategory.STATE_CONFLICT,
                        source_object_id=source.id,
                        target_object_id=target.id,
                        source_plane=source.plane,
                        target_plane=target.plane,
                        description=f"SLA status conflict: {src_sla} vs {tgt_sla}",
                        expected_value=src_sla,
                        actual_value=tgt_sla,
                        rule_id=self.rule_id,
                    )
                ],
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description=f"SLA status mismatch: {src_sla} vs {tgt_sla}",
                    score_contribution=0.0,
                    matched=False,
                ),
            )
        score = 1.0 * self.weight.weight if src_sla == tgt_sla and src_sla is not None else 0.0
        return ReconciliationRuleResult(
            rule_id=self.rule_id,
            score_contribution=score,
            matched=score > 0.0,
            explanation=ReconciliationRuleExplanation(
                rule_id=self.rule_id,
                description="SLA states aligned" if score > 0.0 else "SLA status not present",
                score_contribution=score,
                matched=score > 0.0,
            ),
        )


class UtilitiesFieldCompletionRule(ReconciliationRule):
    """Utilities-field domain pack: field completion vs billing alignment."""

    rule_id = ReconciliationRuleId("utilities-field-completion-billing")
    category = ReconciliationRuleCategory.QUANTITY_ALIGNMENT
    weight = ReconciliationRuleWeight(
        rule_id=ReconciliationRuleId("utilities-field-completion-billing"),
        weight=1.8,
        is_hard_fail=True,
    )
    applicability = ReconciliationRuleApplicability(
        applicable_planes=[PlaneType.FIELD, PlaneType.COMMERCIAL],
        applicable_object_kinds=["completion_certificate", "billable_event", "work_order"],
        requires_cross_plane=True,
    )

    def evaluate(self, source, target, links) -> ReconciliationRuleResult:
        is_completed = source.payload.get("is_completed", False) or target.payload.get(
            "is_completed", False
        )
        is_billed = source.payload.get("is_billed", False) or target.payload.get(
            "is_billed", False
        )

        if is_billed and not is_completed:
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=0.0,
                matched=False,
                hard_fail=True,
                mismatches=[
                    ReconciliationMismatch(
                        category=CrossPlaneMismatchCategory.QUANTITY_CONFLICT,
                        source_object_id=source.id,
                        target_object_id=target.id,
                        source_plane=source.plane,
                        target_plane=target.plane,
                        description="Billing without field completion",
                        rule_id=self.rule_id,
                    )
                ],
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description="Billed without completion — hard fail",
                    score_contribution=0.0,
                    matched=False,
                    hard_fail=True,
                ),
            )

        if is_completed and is_billed:
            return ReconciliationRuleResult(
                rule_id=self.rule_id,
                score_contribution=1.0 * self.weight.weight,
                matched=True,
                explanation=ReconciliationRuleExplanation(
                    rule_id=self.rule_id,
                    description="Completion and billing aligned",
                    score_contribution=1.0 * self.weight.weight,
                    matched=True,
                ),
            )

        return ReconciliationRuleResult(
            rule_id=self.rule_id,
            score_contribution=0.0,
            matched=False,
            explanation=ReconciliationRuleExplanation(
                rule_id=self.rule_id,
                description="Completion/billing status not fully present",
                score_contribution=0.0,
                matched=False,
            ),
        )


def register_domain_pack_reconciliation_rules(
    rule_registry: ReconciliationRuleRegistry,
) -> None:
    """Register domain-pack-specific Wave 2 reconciliation rules."""
    rule_registry.register_rule(ContractMarginCostRule())
    rule_registry.register_rule(TelcoOpsStateAlignmentRule())
    rule_registry.register_rule(UtilitiesFieldCompletionRule())


def get_contract_margin_coverage_expectations() -> list[ExpectedPlaneCoverage]:
    return [
        ExpectedPlaneCoverage(
            plane=PlaneType.COMMERCIAL,
            expected_object_kinds=["rate_card_entry", "billable_event"],
            min_objects_per_kind={"rate_card_entry": 1, "billable_event": 1},
            require_cross_plane_links=True,
        ),
    ]


def get_utilities_field_coverage_expectations() -> list[ExpectedPlaneCoverage]:
    return [
        ExpectedPlaneCoverage(
            plane=PlaneType.FIELD,
            expected_object_kinds=["work_order", "completion_certificate"],
            min_objects_per_kind={"work_order": 1, "completion_certificate": 1},
            require_cross_plane_links=True,
        ),
    ]


def get_telco_ops_coverage_expectations() -> list[ExpectedPlaneCoverage]:
    return [
        ExpectedPlaneCoverage(
            plane=PlaneType.SERVICE,
            expected_object_kinds=["incident_state", "service_state"],
            min_objects_per_kind={"incident_state": 1, "service_state": 1},
            require_cross_plane_links=False,
        ),
    ]


# ── Wave 3: Domain pack validation rule registration ──

from app.core.validation.domain_types import (
    ValidationFailure,
    ValidationFailureCode,
    ValidationResult,
    ValidationRuleId,
    ValidationWarning,
    W3ValidationStatus,
)
from app.core.validation.rule_model import (
    ValidationRuleApplicability,
    ValidationRuleCategory,
    ValidationRuleRegistry,
    ValidationRuleWeight,
    W3ValidationRule,
)


class ContractMarginEvidenceRule(W3ValidationRule):
    """Contract-margin domain: requires clause_extraction and rate_comparison evidence."""

    rule_id = ValidationRuleId("contract-margin-evidence")
    category = ValidationRuleCategory.EVIDENCE_SUFFICIENCY
    weight = ValidationRuleWeight(
        rule_id=ValidationRuleId("contract-margin-evidence"), is_hard_fail=True
    )
    applicability = ValidationRuleApplicability(
        applicable_object_kinds=["rate_card_entry", "billable_event"],
    )

    def validate(self, objects, graph_service, context):
        required = {"clause_extraction", "rate_comparison"}
        failures: list[ValidationFailure] = []
        for obj in objects:
            present = {e.evidence_type for e in obj.evidence}
            missing = required - present
            if missing:
                failures.append(
                    ValidationFailure(
                        code=ValidationFailureCode.EVIDENCE_INSUFFICIENT,
                        object_id=obj.id,
                        description=f"Object '{obj.label}' missing evidence types: {sorted(missing)}",
                        rule_id=self.rule_id,
                        metadata={"missing_types": sorted(missing)},
                    )
                )
        return ValidationResult(
            rule_id=self.rule_id,
            status=W3ValidationStatus.FAILED if failures else W3ValidationStatus.PASSED,
            passed=len(failures) == 0,
            failures=failures,
            explanation="Contract-margin evidence check",
        )


class TelcoOpsActionPreconditionRule(W3ValidationRule):
    """Telco-ops domain: SLA escalation requires incident in active/enriched state."""

    rule_id = ValidationRuleId("telco-ops-action-precondition")
    category = ValidationRuleCategory.ACTION_PRECONDITION
    weight = ValidationRuleWeight(
        rule_id=ValidationRuleId("telco-ops-action-precondition"),
        is_hard_fail=False,
        is_blocking=False,
    )
    applicability = ValidationRuleApplicability(
        applicable_object_kinds=["incident_state", "escalation_rule"],
        applicable_action_types=["sla-escalation"],
    )

    def validate(self, objects, graph_service, context):
        from app.core.types import ControlState

        allowed = {ControlState.ACTIVE.value, ControlState.ENRICHED.value, ControlState.FROZEN.value}
        warnings: list[ValidationWarning] = []
        for obj in objects:
            if obj.state.value not in allowed:
                warnings.append(
                    ValidationWarning(
                        rule_id=self.rule_id,
                        object_id=obj.id,
                        description=f"Object '{obj.label}' is {obj.state.value}, expected active/enriched/frozen for SLA escalation",
                    )
                )
        return ValidationResult(
            rule_id=self.rule_id,
            status=W3ValidationStatus.PASSED_WITH_WARNINGS if warnings else W3ValidationStatus.PASSED,
            passed=True,
            warnings=warnings,
            explanation="Telco-ops action precondition check",
        )


class UtilitiesFieldGraphRule(W3ValidationRule):
    """Utilities-field domain: work orders must have fulfills links."""

    rule_id = ValidationRuleId("utilities-field-graph-completeness")
    category = ValidationRuleCategory.GRAPH_COMPLETENESS
    weight = ValidationRuleWeight(
        rule_id=ValidationRuleId("utilities-field-graph-completeness"),
        is_hard_fail=False,
        is_blocking=False,
    )
    applicability = ValidationRuleApplicability(
        applicable_object_kinds=["work_order", "completion_certificate"],
    )

    def validate(self, objects, graph_service, context):
        from app.core.types import ControlLinkType

        warnings: list[ValidationWarning] = []
        for obj in objects:
            if obj.object_kind == "work_order":
                links = graph_service.get_links_for_object(
                    obj.id, link_type=ControlLinkType.FULFILLS
                )
                if not links:
                    warnings.append(
                        ValidationWarning(
                            rule_id=self.rule_id,
                            object_id=obj.id,
                            description=f"Work order '{obj.label}' has no fulfills links",
                        )
                    )
        return ValidationResult(
            rule_id=self.rule_id,
            status=W3ValidationStatus.PASSED_WITH_WARNINGS if warnings else W3ValidationStatus.PASSED,
            passed=True,
            warnings=warnings,
            explanation="Utilities-field graph completeness check",
        )


def register_domain_pack_validation_rules(
    rule_registry: ValidationRuleRegistry,
) -> None:
    """Register domain-pack-specific Wave 3 validation rules."""
    rule_registry.register_rule(ContractMarginEvidenceRule())
    rule_registry.register_rule(TelcoOpsActionPreconditionRule())
    rule_registry.register_rule(UtilitiesFieldGraphRule())
