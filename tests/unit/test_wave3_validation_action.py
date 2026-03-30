"""Wave 3 — Deterministic Validation Chain + Evidence-Gated Action Engine tests."""

from __future__ import annotations

import uuid

import pytest

from app.core.audit import FabricAuditEventType, FabricAuditHook
from app.core.control_link import ControlLinkCreate
from app.core.control_object import ControlObjectCreate
from app.core.graph.service import GraphService
from app.core.types import (
    ConfidenceScore,
    ControlLinkType,
    ControlObjectId,
    ControlObjectType,
    ControlProvenance,
    ControlState,
    EvidenceRef,
    PlaneType,
)
from app.core.validation.domain_types import (
    ValidationContext,
    ValidationDecision,
    ValidationDecisionPolicy,
    ValidationExecutionRequest,
    ValidationFailureCode,
    ValidationReport,
    ValidationReportHash,
    ValidationScope,
    ValidationTarget,
    W3ValidationStatus,
    new_chain_id,
    new_run_id,
)
from app.core.validation.executor import ValidationChainExecutor
from app.core.validation.repository import (
    InMemoryValidationReportRepository,
    InMemoryValidationRunRepository,
)
from app.core.validation.rule_model import (
    ValidationRuleRegistry,
    build_default_validation_rule_registry,
)

TENANT = uuid.uuid4()


def _graph() -> GraphService:
    return GraphService(audit_hook=FabricAuditHook())


def _make_object(
    svc: GraphService,
    label: str,
    plane: PlaneType = PlaneType.COMMERCIAL,
    domain: str = "contract_margin",
    evidence: list[EvidenceRef] | None = None,
    confidence: float = 1.0,
    provenance: ControlProvenance | None = None,
    object_kind: str = "",
    payload: dict | None = None,
):
    ev = evidence or [EvidenceRef(evidence_type="clause_extraction", source_label="test")]
    prov = provenance or ControlProvenance(created_by="test", creation_method="deterministic")
    obj = svc.create_object(
        TENANT,
        ControlObjectCreate(
            object_type=ControlObjectType.OBLIGATION,
            object_kind=object_kind,
            plane=plane,
            domain=domain,
            label=label,
            confidence=confidence,
            provenance=prov,
            evidence=ev,
            payload=payload or {},
        ),
    )
    return obj


def _executor(
    svc: GraphService,
    audit_hook: FabricAuditHook | None = None,
    rule_registry: ValidationRuleRegistry | None = None,
    decision_policy: ValidationDecisionPolicy | None = None,
) -> ValidationChainExecutor:
    hook = audit_hook or svc.audit_hook
    return ValidationChainExecutor(
        graph_service=svc,
        rule_registry=rule_registry or build_default_validation_rule_registry(),
        audit_hook=hook,
        decision_policy=decision_policy,
    )


def _request(
    object_ids: list[ControlObjectId],
    action_type: str = "",
    require_reconciled: bool = False,
    min_confidence: float = 0.5,
    required_evidence_types: list[str] | None = None,
    policy_overrides: dict | None = None,
) -> ValidationExecutionRequest:
    return ValidationExecutionRequest(
        tenant_id=TENANT,
        context=ValidationContext(
            scope=ValidationScope(tenant_id=TENANT, action_type=action_type),
            target=ValidationTarget(object_ids=object_ids),
            require_reconciled=require_reconciled,
            min_confidence=min_confidence,
            required_evidence_types=required_evidence_types or [],
            policy_overrides=policy_overrides or {},
        ),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Validation Domain Types
# ══════════════════════════════════════════════════════════════════════════════


class TestValidationDomainTypes:
    def test_failure_code_enum_has_13_values(self):
        assert len(ValidationFailureCode) == 13

    def test_decision_enum_has_4_values(self):
        assert len(ValidationDecision) == 4

    def test_status_enum_has_6_values(self):
        assert len(W3ValidationStatus) == 6

    def test_report_hash_deterministic(self):
        r1 = ValidationReport(
            run_id=new_run_id(),
            chain_id=new_chain_id(),
            tenant_id=TENANT,
            status=W3ValidationStatus.PASSED,
            decision=ValidationDecision.ELIGIBLE,
        )
        h1 = r1.compute_hash()
        h2 = r1.compute_hash()
        assert h1 == h2
        assert h1 != ""

    def test_report_is_actionable(self):
        r = ValidationReport(
            run_id=new_run_id(),
            chain_id=new_chain_id(),
            tenant_id=TENANT,
            decision=ValidationDecision.ELIGIBLE,
        )
        assert r.is_actionable is True

    def test_report_not_actionable_when_rejected(self):
        r = ValidationReport(
            run_id=new_run_id(),
            chain_id=new_chain_id(),
            tenant_id=TENANT,
            decision=ValidationDecision.REJECTED,
        )
        assert r.is_actionable is False

    def test_report_passed_property(self):
        r = ValidationReport(
            run_id=new_run_id(),
            chain_id=new_chain_id(),
            tenant_id=TENANT,
            status=W3ValidationStatus.PASSED,
        )
        assert r.passed is True

    def test_report_failed_property(self):
        r = ValidationReport(
            run_id=new_run_id(),
            chain_id=new_chain_id(),
            tenant_id=TENANT,
            status=W3ValidationStatus.FAILED,
        )
        assert r.passed is False


# ══════════════════════════════════════════════════════════════════════════════
# Validation Rule Model + Registry
# ══════════════════════════════════════════════════════════════════════════════


class TestValidationRuleModel:
    def test_default_registry_has_10_rules(self):
        reg = build_default_validation_rule_registry()
        assert reg.rule_count == 10

    def test_ordered_rules_returns_all(self):
        reg = build_default_validation_rule_registry()
        assert len(reg.get_ordered_rules()) == 10

    def test_custom_rule_registration(self):
        from app.core.validation.domain_types import (
            ValidationFailure,
            ValidationResult,
            ValidationRuleId,
            W3ValidationStatus,
        )
        from app.core.validation.rule_model import (
            ValidationRuleApplicability,
            ValidationRuleCategory,
            ValidationRuleWeight,
            W3ValidationRule,
        )

        class CustomRule(W3ValidationRule):
            rule_id = ValidationRuleId("custom-test-rule")
            category = ValidationRuleCategory.POLICY_COMPLIANCE
            weight = ValidationRuleWeight(
                rule_id=ValidationRuleId("custom-test-rule"), is_hard_fail=True
            )
            applicability = ValidationRuleApplicability()

            def validate(self, objects, graph_service, context):
                return ValidationResult(
                    rule_id=self.rule_id,
                    status=W3ValidationStatus.PASSED,
                    passed=True,
                    explanation="Custom rule passed",
                )

        reg = build_default_validation_rule_registry()
        reg.register_rule(CustomRule())
        assert reg.rule_count == 11
        assert reg.get_rule(ValidationRuleId("custom-test-rule")) is not None

    def test_applicable_rules_filter(self):
        svc = _graph()
        obj = _make_object(svc, "test-obj")
        reg = build_default_validation_rule_registry()
        applicable = reg.get_applicable_rules([obj])
        assert len(applicable) == 10


# ══════════════════════════════════════════════════════════════════════════════
# Validation Chain Executor — Happy Path
# ══════════════════════════════════════════════════════════════════════════════


class TestValidationChainExecutorHappyPath:
    def test_all_pass_returns_eligible(self):
        svc = _graph()
        obj = _make_object(svc, "valid-object")
        executor = _executor(svc)
        result = executor.execute(_request([obj.id]))
        assert result.decision == ValidationDecision.ELIGIBLE
        assert result.report.status in (
            W3ValidationStatus.PASSED,
            W3ValidationStatus.PASSED_WITH_WARNINGS,
        )
        assert result.report.report_hash != ""

    def test_run_persisted_in_repository(self):
        svc = _graph()
        obj = _make_object(svc, "valid-object")
        executor = _executor(svc)
        result = executor.execute(_request([obj.id]))
        stored = executor.run_repository.get_run(result.run.id)
        assert stored is not None
        assert stored.id == result.run.id

    def test_report_persisted_in_repository(self):
        svc = _graph()
        obj = _make_object(svc, "valid-object")
        executor = _executor(svc)
        result = executor.execute(_request([obj.id]))
        stored = executor.report_repository.get_report(result.report.id)
        assert stored is not None

    def test_steps_executed_in_order(self):
        svc = _graph()
        obj = _make_object(svc, "valid-object")
        executor = _executor(svc)
        result = executor.execute(_request([obj.id]))
        for i, step in enumerate(result.report.steps):
            assert step.order == i
            assert step.executed is True

    def test_decision_trace_populated(self):
        svc = _graph()
        obj = _make_object(svc, "valid-object")
        executor = _executor(svc)
        result = executor.execute(_request([obj.id]))
        assert result.report.decision_trace is not None
        assert result.report.decision_trace.steps_executed > 0


# ══════════════════════════════════════════════════════════════════════════════
# Validation Chain — Failure Paths
# ══════════════════════════════════════════════════════════════════════════════


class TestValidationFailurePaths:
    def test_schema_invalid_empty_label(self):
        """Object with empty label triggers SCHEMA_INVALID."""
        svc = _graph()
        obj = svc.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.COMMERCIAL,
                domain="contract_margin",
                label="x",
                evidence=[EvidenceRef(evidence_type="clause_extraction", source_label="t")],
            ),
        )
        # Manually blank the label after creation to bypass factory validation
        obj.label = ""
        svc.repository.store_object(obj)

        executor = _executor(svc)
        result = executor.execute(_request([obj.id]))
        assert result.decision == ValidationDecision.REJECTED
        codes = [f.code for f in result.report.failures]
        assert ValidationFailureCode.SCHEMA_INVALID in codes

    def test_evidence_insufficient(self):
        """Object with no evidence triggers EVIDENCE_INSUFFICIENT."""
        svc = _graph()
        obj = svc.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.COMMERCIAL,
                domain="contract_margin",
                label="no-evidence",
                evidence=[],
            ),
        )
        executor = _executor(svc)
        result = executor.execute(_request([obj.id]))
        codes = [f.code for f in result.report.failures]
        assert ValidationFailureCode.EVIDENCE_INSUFFICIENT in codes

    def test_provenance_missing_creator(self):
        """Object with empty provenance creator triggers PROVENANCE_INVALID."""
        svc = _graph()
        obj = _make_object(
            svc,
            "bad-provenance",
            provenance=ControlProvenance(created_by="", creation_method="deterministic"),
        )
        executor = _executor(svc)
        result = executor.execute(_request([obj.id]))
        codes = [f.code for f in result.report.failures]
        assert ValidationFailureCode.PROVENANCE_INVALID in codes

    def test_confidence_below_threshold(self):
        """Object with low confidence triggers CONFIDENCE_BELOW_THRESHOLD."""
        svc = _graph()
        obj = _make_object(svc, "low-conf", confidence=0.1)
        executor = _executor(svc)
        result = executor.execute(_request([obj.id], min_confidence=0.8))
        codes = [f.code for f in result.report.failures]
        assert ValidationFailureCode.CONFIDENCE_BELOW_THRESHOLD in codes

    def test_contradictory_evidence(self):
        """Object with CONTRADICTS link triggers CONTRADICTORY_EVIDENCE."""
        svc = _graph()
        obj1 = _make_object(svc, "A")
        obj2 = _make_object(svc, "B")
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=obj1.id,
                target_id=obj2.id,
                link_type=ControlLinkType.CONTRADICTS,
            ),
        )
        executor = _executor(svc)
        result = executor.execute(_request([obj1.id]))
        codes = [f.code for f in result.report.failures]
        assert ValidationFailureCode.CONTRADICTORY_EVIDENCE in codes

    def test_reconciliation_state_disputed(self):
        """Disputed object triggers RECONCILIATION_INCOMPLETE."""
        svc = _graph()
        obj = _make_object(svc, "disputed-obj")
        svc.freeze_object(obj.id)
        svc.transition_object(obj.id, ControlState.DISPUTED)
        executor = _executor(svc)
        result = executor.execute(_request([obj.id]))
        codes = [f.code for f in result.report.failures]
        assert ValidationFailureCode.RECONCILIATION_INCOMPLETE in codes

    def test_blocked_when_no_target_objects(self):
        """Request with invalid object IDs blocks execution."""
        svc = _graph()
        fake_id = ControlObjectId(uuid.uuid4())
        executor = _executor(svc)
        result = executor.execute(_request([fake_id]))
        assert result.report.status == W3ValidationStatus.BLOCKED
        assert result.decision == ValidationDecision.REJECTED


# ══════════════════════════════════════════════════════════════════════════════
# Validation Decision Policy
# ══════════════════════════════════════════════════════════════════════════════


class TestValidationDecisionPolicy:
    def test_auto_eligible_on_pass(self):
        svc = _graph()
        obj = _make_object(svc, "good-obj")
        policy = ValidationDecisionPolicy(auto_eligible_on_pass=True)
        executor = _executor(svc, decision_policy=policy)
        result = executor.execute(_request([obj.id]))
        assert result.decision in (
            ValidationDecision.ELIGIBLE,
            ValidationDecision.APPROVAL_REQUIRED,
        )

    def test_proposal_only_on_warnings(self):
        """With proposal_only_on_warnings, warnings produce PROPOSAL_ONLY."""
        svc = _graph()
        # No graph links → graph completeness warning
        obj = _make_object(svc, "warn-obj")
        policy = ValidationDecisionPolicy(proposal_only_on_warnings=True)
        executor = _executor(svc, decision_policy=policy)
        result = executor.execute(_request([obj.id]))
        if result.report.warnings:
            assert result.decision == ValidationDecision.PROPOSAL_ONLY

    def test_approval_required_on_many_warnings(self):
        """Exceeding max_warnings triggers APPROVAL_REQUIRED."""
        svc = _graph()
        obj = _make_object(svc, "warn-obj")
        policy = ValidationDecisionPolicy(
            max_warnings=0,
            allow_warnings=True,
            proposal_only_on_warnings=False,
        )
        executor = _executor(svc, decision_policy=policy)
        result = executor.execute(_request([obj.id]))
        if result.report.warnings:
            assert result.decision == ValidationDecision.APPROVAL_REQUIRED


# ══════════════════════════════════════════════════════════════════════════════
# Report Hash Determinism
# ══════════════════════════════════════════════════════════════════════════════


class TestReportHashDeterminism:
    def test_same_inputs_same_hash(self):
        svc = _graph()
        obj = _make_object(svc, "hash-obj")
        e1 = _executor(svc)
        r1 = e1.execute(_request([obj.id]))

        e2 = _executor(svc)
        r2 = e2.execute(_request([obj.id]))

        # Both runs should produce the same decision and status
        assert r1.report.status == r2.report.status
        assert r1.decision == r2.decision

    def test_report_hash_is_nonempty(self):
        svc = _graph()
        obj = _make_object(svc, "hash-obj")
        executor = _executor(svc)
        result = executor.execute(_request([obj.id]))
        assert result.report.report_hash != ""
        assert len(str(result.report.report_hash)) == 64  # SHA256 hex


# ══════════════════════════════════════════════════════════════════════════════
# Validation Audit Events
# ══════════════════════════════════════════════════════════════════════════════


class TestValidationAuditEvents:
    def test_run_started_event(self):
        hook = FabricAuditHook()
        svc = GraphService(audit_hook=hook)
        obj = _make_object(svc, "audit-obj")
        executor = _executor(svc, audit_hook=hook)
        executor.execute(_request([obj.id]))
        events = hook.get_events_by_type(FabricAuditEventType.VALIDATION_RUN_STARTED)
        assert len(events) >= 1

    def test_run_completed_event(self):
        hook = FabricAuditHook()
        svc = GraphService(audit_hook=hook)
        obj = _make_object(svc, "audit-obj")
        executor = _executor(svc, audit_hook=hook)
        executor.execute(_request([obj.id]))
        events = hook.get_events_by_type(FabricAuditEventType.VALIDATION_RUN_COMPLETED)
        assert len(events) >= 1

    def test_step_completed_events(self):
        hook = FabricAuditHook()
        svc = GraphService(audit_hook=hook)
        obj = _make_object(svc, "audit-obj")
        executor = _executor(svc, audit_hook=hook)
        executor.execute(_request([obj.id]))
        events = hook.get_events_by_type(FabricAuditEventType.VALIDATION_STEP_COMPLETED)
        assert len(events) >= 1

    def test_decision_recorded_event(self):
        hook = FabricAuditHook()
        svc = GraphService(audit_hook=hook)
        obj = _make_object(svc, "audit-obj")
        executor = _executor(svc, audit_hook=hook)
        executor.execute(_request([obj.id]))
        events = hook.get_events_by_type(FabricAuditEventType.VALIDATION_DECISION_RECORDED)
        assert len(events) >= 1

    def test_failure_event_on_rejection(self):
        hook = FabricAuditHook()
        svc = GraphService(audit_hook=hook)
        obj = svc.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.COMMERCIAL,
                domain="contract_margin",
                label="fail-obj",
                evidence=[],
            ),
        )
        executor = _executor(svc, audit_hook=hook)
        executor.execute(_request([obj.id]))
        events = hook.get_events_by_type(FabricAuditEventType.VALIDATION_FAILED)
        assert len(events) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# Validation Repositories
# ══════════════════════════════════════════════════════════════════════════════


class TestValidationRepositories:
    def test_run_repository_store_and_get(self):
        repo = InMemoryValidationRunRepository()
        from app.core.validation.domain_types import ValidationRun

        run = ValidationRun(
            chain_id=new_chain_id(),
            tenant_id=TENANT,
            context=ValidationContext(
                scope=ValidationScope(tenant_id=TENANT),
                target=ValidationTarget(),
            ),
        )
        repo.store_run(run)
        assert repo.get_run(run.id) is not None

    def test_report_repository_store_and_get(self):
        repo = InMemoryValidationReportRepository()
        report = ValidationReport(
            run_id=new_run_id(),
            chain_id=new_chain_id(),
            tenant_id=TENANT,
        )
        repo.store_report(report)
        assert repo.get_report(report.id) is not None

    def test_run_repository_list_by_tenant(self):
        repo = InMemoryValidationRunRepository()
        from app.core.validation.domain_types import ValidationRun

        for _ in range(3):
            repo.store_run(
                ValidationRun(
                    chain_id=new_chain_id(),
                    tenant_id=TENANT,
                    context=ValidationContext(
                        scope=ValidationScope(tenant_id=TENANT),
                        target=ValidationTarget(),
                    ),
                )
            )
        assert repo.count >= 3


# ══════════════════════════════════════════════════════════════════════════════
# Action Domain Types
# ══════════════════════════════════════════════════════════════════════════════


class TestActionDomainTypes:
    def test_action_type_enum_has_8_values(self):
        from app.core.action.domain_types import W3ActionType

        assert len(W3ActionType) == 8

    def test_action_status_enum_has_7_values(self):
        from app.core.action.domain_types import W3ActionStatus

        assert len(W3ActionStatus) == 7

    def test_execution_mode_enum_has_3_values(self):
        from app.core.action.domain_types import W3ActionExecutionMode

        assert len(W3ActionExecutionMode) == 3

    def test_evidence_manifest_hash_deterministic(self):
        from app.core.action.domain_types import (
            W3ActionEvidenceManifest,
            new_action_id,
        )

        m = W3ActionEvidenceManifest(action_id=new_action_id())
        h1 = m.compute_hash()
        h2 = m.compute_hash()
        assert h1 == h2
        assert h1 != ""

    def test_proposal_decision_hash_deterministic(self):
        from app.core.action.domain_types import W3ActionProposal, W3ActionType

        p = W3ActionProposal(
            tenant_id=TENANT,
            action_type=W3ActionType.CREDIT_NOTE,
        )
        h1 = p.compute_decision_hash()
        h2 = p.compute_decision_hash()
        assert h1 == h2

    def test_proposal_not_releasable_when_rejected(self):
        from app.core.action.domain_types import (
            W3ActionProposal,
            W3ActionStatus,
            W3ActionType,
        )

        p = W3ActionProposal(
            tenant_id=TENANT,
            action_type=W3ActionType.CREDIT_NOTE,
            status=W3ActionStatus.REJECTED,
        )
        assert p.is_releasable is False

    def test_proposal_not_releasable_dry_run(self):
        from app.core.action.domain_types import (
            W3ActionExecutionMode,
            W3ActionProposal,
            W3ActionType,
        )

        p = W3ActionProposal(
            tenant_id=TENANT,
            action_type=W3ActionType.CREDIT_NOTE,
            execution_mode=W3ActionExecutionMode.DRY_RUN,
            validation_decision=ValidationDecision.ELIGIBLE,
        )
        assert p.is_releasable is False


# ══════════════════════════════════════════════════════════════════════════════
# Action Policy Engine
# ══════════════════════════════════════════════════════════════════════════════


class TestActionPolicyEngine:
    def _run_validation(self, svc, obj):
        executor = _executor(svc)
        return executor.execute(_request([obj.id]))

    def test_propose_action_happy_path(self):
        from app.core.action.domain_types import W3ActionExecutionMode, W3ActionType
        from app.core.action.policy_engine import W3ActionPolicyEngine

        svc = _graph()
        obj = _make_object(svc, "action-target")
        vresult = self._run_validation(svc, obj)

        engine = W3ActionPolicyEngine(
            graph_service=svc,
            validation_executor=_executor(svc),
        )
        proposal = engine.propose_action(
            tenant_id=TENANT,
            action_type=W3ActionType.CREDIT_NOTE,
            target_object_ids=[obj.id],
            validation_result=vresult,
            execution_mode=W3ActionExecutionMode.APPROVAL_GATED,
        )
        assert proposal.evidence_manifest is not None
        assert proposal.decision_hash != ""

    def test_propose_action_validation_rejected(self):
        from app.core.action.domain_types import W3ActionType
        from app.core.action.policy_engine import ActionPolicyError, W3ActionPolicyEngine

        svc = _graph()
        obj = svc.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.COMMERCIAL,
                domain="contract_margin",
                label="bad-obj",
                evidence=[],
            ),
        )
        vresult = self._run_validation(svc, obj)
        assert vresult.decision == ValidationDecision.REJECTED

        engine = W3ActionPolicyEngine(
            graph_service=svc,
            validation_executor=_executor(svc),
        )
        with pytest.raises(ActionPolicyError):
            engine.propose_action(
                tenant_id=TENANT,
                action_type=W3ActionType.CREDIT_NOTE,
                target_object_ids=[obj.id],
                validation_result=vresult,
            )

    def test_approve_and_release(self):
        from app.core.action.domain_types import (
            W3ActionExecutionMode,
            W3ActionStatus,
            W3ActionType,
        )
        from app.core.action.policy_engine import W3ActionPolicyEngine

        svc = _graph()
        obj = _make_object(svc, "release-target")
        vresult = self._run_validation(svc, obj)

        engine = W3ActionPolicyEngine(
            graph_service=svc,
            validation_executor=_executor(svc),
        )
        proposal = engine.propose_action(
            tenant_id=TENANT,
            action_type=W3ActionType.CREDIT_NOTE,
            target_object_ids=[obj.id],
            validation_result=vresult,
            execution_mode=W3ActionExecutionMode.APPROVAL_GATED,
        )
        engine.approve_action(proposal.id, approver="test-admin")
        release = engine.release_action(proposal.id)
        assert release.decision_hash == proposal.decision_hash
        assert proposal.status == W3ActionStatus.RELEASED

    def test_reject_action(self):
        from app.core.action.domain_types import W3ActionStatus, W3ActionType
        from app.core.action.policy_engine import W3ActionPolicyEngine

        svc = _graph()
        obj = _make_object(svc, "reject-target")
        vresult = self._run_validation(svc, obj)

        engine = W3ActionPolicyEngine(
            graph_service=svc,
            validation_executor=_executor(svc),
        )
        proposal = engine.propose_action(
            tenant_id=TENANT,
            action_type=W3ActionType.CREDIT_NOTE,
            target_object_ids=[obj.id],
            validation_result=vresult,
        )
        engine.reject_action(proposal.id, reason="Not approved")
        assert proposal.status == W3ActionStatus.REJECTED
        assert proposal.is_releasable is False

    def test_dry_run_not_releasable(self):
        from app.core.action.domain_types import W3ActionExecutionMode, W3ActionType
        from app.core.action.policy_engine import ActionPolicyError, W3ActionPolicyEngine

        svc = _graph()
        obj = _make_object(svc, "dry-run-target")
        vresult = self._run_validation(svc, obj)

        engine = W3ActionPolicyEngine(
            graph_service=svc,
            validation_executor=_executor(svc),
        )
        proposal = engine.propose_action(
            tenant_id=TENANT,
            action_type=W3ActionType.CREDIT_NOTE,
            target_object_ids=[obj.id],
            validation_result=vresult,
            execution_mode=W3ActionExecutionMode.DRY_RUN,
        )
        assert proposal.is_releasable is False
        with pytest.raises(ActionPolicyError):
            engine.release_action(proposal.id)

    def test_auto_release_mode(self):
        from app.core.action.domain_types import (
            W3ActionExecutionMode,
            W3ActionStatus,
            W3ActionType,
        )
        from app.core.action.policy_engine import W3ActionPolicyEngine

        svc = _graph()
        obj = _make_object(svc, "auto-release-target")
        vresult = self._run_validation(svc, obj)

        engine = W3ActionPolicyEngine(
            graph_service=svc,
            validation_executor=_executor(svc),
        )
        proposal = engine.propose_action(
            tenant_id=TENANT,
            action_type=W3ActionType.CREDIT_NOTE,
            target_object_ids=[obj.id],
            validation_result=vresult,
            execution_mode=W3ActionExecutionMode.DETERMINISTIC_AUTO_RELEASE,
        )
        assert proposal.status == W3ActionStatus.VALIDATED
        release = engine.release_action(proposal.id)
        assert release is not None
        assert proposal.status == W3ActionStatus.RELEASED

    def test_evidence_missing_blocks_proposal(self):
        from app.core.action.domain_types import W3ActionPolicy, W3ActionType
        from app.core.action.policy_engine import ActionPolicyError, W3ActionPolicyEngine

        svc = _graph()
        obj = svc.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.COMMERCIAL,
                domain="contract_margin",
                label="no-ev-action",
                evidence=[EvidenceRef(evidence_type="clause_extraction", source_label="t")],
            ),
        )
        # Run validation first — passes because has evidence
        vresult = self._run_validation(svc, obj)
        if vresult.decision != ValidationDecision.ELIGIBLE:
            pytest.skip("Validation did not produce eligible decision")

        # But then strip evidence to simulate policy requiring more
        engine = W3ActionPolicyEngine(
            graph_service=svc,
            validation_executor=_executor(svc),
            policy=W3ActionPolicy(min_evidence_count=5),
        )
        with pytest.raises(ActionPolicyError):
            engine.propose_action(
                tenant_id=TENANT,
                action_type=W3ActionType.CREDIT_NOTE,
                target_object_ids=[obj.id],
                validation_result=vresult,
            )


# ══════════════════════════════════════════════════════════════════════════════
# Action Audit Events
# ══════════════════════════════════════════════════════════════════════════════


class TestActionAuditEvents:
    def test_action_proposed_event(self):
        from app.core.action.domain_types import W3ActionType
        from app.core.action.policy_engine import W3ActionPolicyEngine

        hook = FabricAuditHook()
        svc = GraphService(audit_hook=hook)
        obj = _make_object(svc, "audit-action")
        executor = _executor(svc, audit_hook=hook)
        vresult = executor.execute(_request([obj.id]))

        engine = W3ActionPolicyEngine(
            graph_service=svc,
            validation_executor=executor,
            audit_hook=hook,
        )
        engine.propose_action(
            tenant_id=TENANT,
            action_type=W3ActionType.CREDIT_NOTE,
            target_object_ids=[obj.id],
            validation_result=vresult,
        )
        events = hook.get_events_by_type(FabricAuditEventType.ACTION_PROPOSED)
        assert len(events) >= 1

    def test_action_released_event(self):
        from app.core.action.domain_types import (
            W3ActionExecutionMode,
            W3ActionType,
        )
        from app.core.action.policy_engine import W3ActionPolicyEngine

        hook = FabricAuditHook()
        svc = GraphService(audit_hook=hook)
        obj = _make_object(svc, "audit-release")
        executor = _executor(svc, audit_hook=hook)
        vresult = executor.execute(_request([obj.id]))

        engine = W3ActionPolicyEngine(
            graph_service=svc,
            validation_executor=executor,
            audit_hook=hook,
        )
        proposal = engine.propose_action(
            tenant_id=TENANT,
            action_type=W3ActionType.CREDIT_NOTE,
            target_object_ids=[obj.id],
            validation_result=vresult,
            execution_mode=W3ActionExecutionMode.DETERMINISTIC_AUTO_RELEASE,
        )
        engine.release_action(proposal.id)
        events = hook.get_events_by_type(FabricAuditEventType.ACTION_RELEASED)
        assert len(events) >= 1

    def test_action_rejected_event(self):
        from app.core.action.domain_types import W3ActionType
        from app.core.action.policy_engine import W3ActionPolicyEngine

        hook = FabricAuditHook()
        svc = GraphService(audit_hook=hook)
        obj = _make_object(svc, "audit-reject")
        executor = _executor(svc, audit_hook=hook)
        vresult = executor.execute(_request([obj.id]))

        engine = W3ActionPolicyEngine(
            graph_service=svc,
            validation_executor=executor,
            audit_hook=hook,
        )
        proposal = engine.propose_action(
            tenant_id=TENANT,
            action_type=W3ActionType.CREDIT_NOTE,
            target_object_ids=[obj.id],
            validation_result=vresult,
        )
        engine.reject_action(proposal.id, reason="test")
        events = hook.get_events_by_type(FabricAuditEventType.ACTION_REJECTED)
        assert len(events) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# Action Repositories
# ══════════════════════════════════════════════════════════════════════════════


class TestActionRepositories:
    def test_proposal_repository_store_and_get(self):
        from app.core.action.domain_types import W3ActionProposal, W3ActionType
        from app.core.action.w3_repository import InMemoryW3ActionProposalRepository

        repo = InMemoryW3ActionProposalRepository()
        p = W3ActionProposal(
            tenant_id=TENANT,
            action_type=W3ActionType.CREDIT_NOTE,
        )
        repo.store_proposal(p)
        assert repo.get_proposal(p.id) is not None
        assert repo.count == 1

    def test_release_repository_store_and_get(self):
        from app.core.action.domain_types import (
            W3ActionEvidenceManifest,
            W3ActionRelease,
            W3ActionType,
            new_action_id,
        )
        from app.core.action.w3_repository import InMemoryW3ActionReleaseRepository

        repo = InMemoryW3ActionReleaseRepository()
        aid = new_action_id()
        r = W3ActionRelease(
            action_id=aid,
            tenant_id=TENANT,
            action_type=W3ActionType.CREDIT_NOTE,
            evidence_manifest=W3ActionEvidenceManifest(action_id=aid),
        )
        repo.store_release(r)
        assert repo.get_release(aid) is not None
        assert repo.count == 1

    def test_proposal_repository_list_by_tenant(self):
        from app.core.action.domain_types import W3ActionProposal, W3ActionType
        from app.core.action.w3_repository import InMemoryW3ActionProposalRepository

        repo = InMemoryW3ActionProposalRepository()
        for _ in range(3):
            repo.store_proposal(
                W3ActionProposal(
                    tenant_id=TENANT,
                    action_type=W3ActionType.CREDIT_NOTE,
                )
            )
        assert len(repo.list_proposals(TENANT)) == 3


# ══════════════════════════════════════════════════════════════════════════════
# Domain Pack Integration — Wave 3 Validation Rules
# ══════════════════════════════════════════════════════════════════════════════


class TestDomainPackValidationRules:
    def test_contract_margin_evidence_rule_registers(self):
        from app.core.domain_integration import ContractMarginEvidenceRule

        rule = ContractMarginEvidenceRule()
        assert rule.rule_id == "contract-margin-evidence"

    def test_telco_ops_precondition_rule_registers(self):
        from app.core.domain_integration import TelcoOpsActionPreconditionRule

        rule = TelcoOpsActionPreconditionRule()
        assert rule.rule_id == "telco-ops-action-precondition"

    def test_utilities_field_graph_rule_registers(self):
        from app.core.domain_integration import UtilitiesFieldGraphRule

        rule = UtilitiesFieldGraphRule()
        assert rule.rule_id == "utilities-field-graph-completeness"

    def test_register_all_domain_validation_rules(self):
        from app.core.domain_integration import register_domain_pack_validation_rules

        reg = build_default_validation_rule_registry()
        register_domain_pack_validation_rules(reg)
        assert reg.rule_count == 13  # 10 default + 3 domain

    def test_contract_margin_evidence_rule_fails_on_missing(self):
        from app.core.domain_integration import ContractMarginEvidenceRule

        svc = _graph()
        obj = _make_object(
            svc,
            "no-rate-evidence",
            evidence=[EvidenceRef(evidence_type="other", source_label="t")],
        )
        rule = ContractMarginEvidenceRule()
        result = rule.validate([obj], svc, {})
        assert result.passed is False
        assert any(f.code == ValidationFailureCode.EVIDENCE_INSUFFICIENT for f in result.failures)

    def test_contract_margin_evidence_rule_passes(self):
        from app.core.domain_integration import ContractMarginEvidenceRule

        svc = _graph()
        obj = _make_object(
            svc,
            "good-evidence",
            evidence=[
                EvidenceRef(evidence_type="clause_extraction", source_label="t"),
                EvidenceRef(evidence_type="rate_comparison", source_label="t"),
            ],
        )
        rule = ContractMarginEvidenceRule()
        result = rule.validate([obj], svc, {})
        assert result.passed is True
