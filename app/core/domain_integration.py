"""Domain pack integration — registers domain-specific kinds, rules, policies into the fabric."""

from __future__ import annotations

from app.core.audit import FabricAuditHook
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
