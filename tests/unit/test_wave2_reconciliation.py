"""Wave 2 tests — cross-plane reconciliation engine."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.audit import FabricAuditEventType, FabricAuditHook
from app.core.control_link import ControlLinkCreate
from app.core.control_object import ControlObject, ControlObjectCreate
from app.core.graph.service import GraphService
from app.core.reconciliation.coverage import CoverageAnalyzer, EvidenceSufficiencyEvaluator
from app.core.reconciliation.domain_types import (
    CoverageGap,
    CrossPlaneMismatchCategory,
    ExpectedPlaneCoverage,
    MatchCandidate,
    MatchScore,
    ReconciliationAssemblyInput,
    ReconciliationCase,
    ReconciliationCasePriority,
    ReconciliationCaseStatus,
    ReconciliationDeterminismLevel,
    ReconciliationExecutionResult,
    ReconciliationMismatch,
    ReconciliationOutcome,
    ReconciliationOutcomeType,
    ReconciliationRequest,
    ReconciliationRun,
    ReconciliationRunId,
    ReconciliationScope,
    ReconciliationScopeType,
    ReconciliationStatus,
    ReconciliationTarget,
    new_run_id,
)
from app.core.reconciliation.matching import (
    CandidateGenerator,
    CandidateScorer,
    DuplicateDetector,
    MismatchClassifier,
    ReconciliationAssembler,
)
from app.core.reconciliation.orchestrator import (
    ReconciliationCaseFactory,
    ReconciliationOrchestrator,
    ReconciliationRunFactory,
)
from app.core.reconciliation.reconciliation_audit import ReconciliationAuditIntegration
from app.core.reconciliation.repository import (
    InMemoryReconciliationCaseRepository,
    InMemoryReconciliationRunRepository,
)
from app.core.reconciliation.rule_model import (
    ChronologyAlignmentRule,
    CostAlignmentRule,
    CoverageExpectationRule,
    EvidenceSufficiencyRule,
    ExternalReferenceCorrelationRule,
    IdentityCorrelationRule,
    QuantityAlignmentRule,
    ReconciliationRuleId,
    ReconciliationRuleRegistry,
    StateAlignmentRule,
    TopologyLinkageRule,
    build_default_rule_registry,
)
from app.core.types import (
    AuditContext,
    ConfidenceScore,
    ControlLinkType,
    ControlObjectId,
    ControlObjectType,
    ControlState,
    EvidenceRef,
    PlaneType,
)

TENANT = uuid.uuid4()
AUDIT_CTX = AuditContext(actor="test", action="test", timestamp=datetime.now(UTC))


def _make_object(
    svc: GraphService,
    label: str,
    plane: PlaneType,
    domain: str = "test",
    payload: dict | None = None,
    correlation_keys: dict | None = None,
    external_refs: dict | None = None,
    object_kind: str = "",
    evidence: list[EvidenceRef] | None = None,
) -> ControlObject:
    return svc.create_object(
        TENANT,
        ControlObjectCreate(
            object_type=ControlObjectType.OBLIGATION,
            object_kind=object_kind,
            plane=plane,
            domain=domain,
            label=label,
            payload=payload or {},
            correlation_keys=correlation_keys or {},
            external_refs=external_refs or {},
            evidence=evidence or [],
        ),
    )


class TestReconciliationRunCreation:
    def test_run_factory_creates_run(self):
        scope = ReconciliationScope(
            scope_type=ReconciliationScopeType.BY_PLANE_COMBINATION,
            planes=[PlaneType.COMMERCIAL, PlaneType.FIELD],
            tenant_id=TENANT,
        )
        target = ReconciliationTarget()
        request = ReconciliationRequest(tenant_id=TENANT, scope=scope, target=target)
        run = ReconciliationRunFactory().create_run(request)
        assert run.status == ReconciliationStatus.PENDING
        assert run.tenant_id == TENANT

    def test_run_has_unique_id(self):
        scope = ReconciliationScope(
            scope_type=ReconciliationScopeType.BY_PLANE_COMBINATION,
            planes=[PlaneType.COMMERCIAL, PlaneType.FIELD],
            tenant_id=TENANT,
        )
        target = ReconciliationTarget()
        request = ReconciliationRequest(tenant_id=TENANT, scope=scope, target=target)
        factory = ReconciliationRunFactory()
        r1 = factory.create_run(request)
        r2 = factory.create_run(request)
        assert r1.id != r2.id

    def test_run_repository_store_and_retrieve(self):
        repo = InMemoryReconciliationRunRepository()
        scope = ReconciliationScope(
            scope_type=ReconciliationScopeType.BY_PLANE_COMBINATION,
            planes=[PlaneType.COMMERCIAL, PlaneType.FIELD],
            tenant_id=TENANT,
        )
        run = ReconciliationRun(
            tenant_id=TENANT,
            scope=scope,
            target=ReconciliationTarget(),
        )
        repo.store_run(run)
        assert repo.get_run(run.id) is not None
        assert repo.count == 1


class TestCandidateGeneration:
    def test_generate_from_cross_plane_link(self):
        svc = GraphService()
        src = _make_object(svc, "Commercial Obj", PlaneType.COMMERCIAL)
        tgt = _make_object(svc, "Field Obj", PlaneType.FIELD)
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=src.id,
                target_id=tgt.id,
                link_type=ControlLinkType.FULFILLS,
            ),
        )
        links = svc.repository.get_all_links(TENANT)
        gen = CandidateGenerator()
        candidates = gen.generate([src], [tgt], links)
        assert len(candidates) >= 1
        assert candidates[0].match_method == "graph-link"

    def test_generate_from_correlation_keys(self):
        svc = GraphService()
        src = _make_object(
            svc,
            "Contract",
            PlaneType.COMMERCIAL,
            correlation_keys={"contract_ref": "C-100"},
        )
        tgt = _make_object(
            svc,
            "Work Order",
            PlaneType.FIELD,
            correlation_keys={"contract_ref": "C-100"},
        )
        gen = CandidateGenerator()
        candidates = gen.generate([src], [tgt], [])
        assert len(candidates) == 1
        assert candidates[0].match_method == "correlation-key"

    def test_generate_from_external_refs(self):
        svc = GraphService()
        src = _make_object(
            svc,
            "CRM Entry",
            PlaneType.COMMERCIAL,
            external_refs={"crm_id": "CRM-42"},
        )
        tgt = _make_object(
            svc,
            "Field Entry",
            PlaneType.FIELD,
            external_refs={"crm_id": "CRM-42"},
        )
        gen = CandidateGenerator()
        candidates = gen.generate([src], [tgt], [])
        assert len(candidates) == 1
        assert candidates[0].match_method == "external-ref"

    def test_no_duplicate_candidates(self):
        svc = GraphService()
        src = _make_object(
            svc,
            "Obj",
            PlaneType.COMMERCIAL,
            correlation_keys={"ref": "X"},
            external_refs={"crm_id": "Y"},
        )
        tgt = _make_object(
            svc,
            "Obj2",
            PlaneType.FIELD,
            correlation_keys={"ref": "X"},
            external_refs={"crm_id": "Y"},
        )
        gen = CandidateGenerator()
        candidates = gen.generate([src], [tgt], [])
        assert len(candidates) == 1


class TestCandidateScoring:
    def test_score_breakdown_by_rule(self):
        svc = GraphService()
        src = _make_object(
            svc,
            "A",
            PlaneType.COMMERCIAL,
            payload={"quantity": 10, "cost": 100},
            correlation_keys={"ref": "R1"},
        )
        tgt = _make_object(
            svc,
            "B",
            PlaneType.FIELD,
            payload={"quantity": 10, "cost": 100},
            correlation_keys={"ref": "R1"},
        )
        registry = build_default_rule_registry()
        scorer = CandidateScorer(registry)
        candidate = MatchCandidate(
            source_object_id=src.id,
            target_object_id=tgt.id,
            source_plane=PlaneType.COMMERCIAL,
            target_plane=PlaneType.FIELD,
        )
        scored, traces = scorer.score_candidate(candidate, src, tgt, [])
        assert scored.score_breakdown.rule_scores
        assert len(traces) > 0
        assert float(scored.score) > 0.0

    def test_identity_correlation_scores_on_matching_keys(self):
        svc = GraphService()
        src = _make_object(
            svc,
            "X",
            PlaneType.COMMERCIAL,
            correlation_keys={"contract_ref": "C1"},
        )
        tgt = _make_object(
            svc,
            "Y",
            PlaneType.FIELD,
            correlation_keys={"contract_ref": "C1"},
        )
        rule = IdentityCorrelationRule()
        result = rule.evaluate(src, tgt, [])
        assert result.matched
        assert result.score_contribution > 0.0

    def test_quantity_conflict_mismatch(self):
        svc = GraphService()
        src = _make_object(svc, "A", PlaneType.COMMERCIAL, payload={"quantity": 10})
        tgt = _make_object(svc, "B", PlaneType.FIELD, payload={"quantity": 8})
        rule = QuantityAlignmentRule()
        result = rule.evaluate(src, tgt, [])
        assert not result.matched
        assert len(result.mismatches) == 1
        assert result.mismatches[0].category == CrossPlaneMismatchCategory.QUANTITY_CONFLICT

    def test_cost_conflict_mismatch(self):
        svc = GraphService()
        src = _make_object(svc, "A", PlaneType.COMMERCIAL, payload={"cost": 100.0})
        tgt = _make_object(svc, "B", PlaneType.FIELD, payload={"cost": 200.0})
        rule = CostAlignmentRule()
        result = rule.evaluate(src, tgt, [])
        assert not result.matched
        assert len(result.mismatches) == 1
        assert result.mismatches[0].category == CrossPlaneMismatchCategory.COST_CONFLICT
        assert result.mismatches[0].deviation == 100.0

    def test_state_conflict_mismatch(self):
        svc = GraphService()
        src = _make_object(svc, "A", PlaneType.COMMERCIAL, payload={"state": "pending"})
        tgt = _make_object(svc, "B", PlaneType.FIELD, payload={"state": "closed"})
        # Freeze target so lifecycle states differ (active vs frozen)
        svc.freeze_object(tgt.id)
        tgt = svc.get_object(tgt.id)
        rule = StateAlignmentRule()
        result = rule.evaluate(src, tgt, [])
        assert len(result.mismatches) == 1
        assert result.mismatches[0].category == CrossPlaneMismatchCategory.STATE_CONFLICT

    def test_chronology_conflict_mismatch(self):
        svc = GraphService()
        src = _make_object(svc, "A", PlaneType.COMMERCIAL, payload={"effective_date": "2025-01-01"})
        tgt = _make_object(svc, "B", PlaneType.FIELD, payload={"effective_date": "2025-06-01"})
        rule = ChronologyAlignmentRule()
        result = rule.evaluate(src, tgt, [])
        assert len(result.mismatches) == 1
        assert result.mismatches[0].category == CrossPlaneMismatchCategory.CHRONOLOGY_CONFLICT

    def test_unsupported_linkage_hard_fail(self):
        svc = GraphService()
        src = _make_object(svc, "A", PlaneType.COMMERCIAL)
        tgt = _make_object(svc, "B", PlaneType.FIELD)
        from app.core.control_link import ControlLink, ControlLinkCreate, build_control_link

        link = build_control_link(
            TENANT,
            ControlLinkCreate(
                source_id=src.id,
                target_id=tgt.id,
                link_type=ControlLinkType.CONTRADICTS,
            ),
            source_plane=PlaneType.COMMERCIAL,
            target_plane=PlaneType.FIELD,
        )
        rule = TopologyLinkageRule()
        result = rule.evaluate(src, tgt, [link])
        assert result.hard_fail
        assert len(result.mismatches) == 1
        assert result.mismatches[0].category == CrossPlaneMismatchCategory.UNSUPPORTED_LINKAGE

    def test_evidence_insufficient(self):
        svc = GraphService()
        src = _make_object(svc, "A", PlaneType.COMMERCIAL)
        tgt = _make_object(svc, "B", PlaneType.FIELD)
        rule = EvidenceSufficiencyRule()
        result = rule.evaluate(src, tgt, [])
        assert not result.matched
        assert len(result.mismatches) == 1
        assert result.mismatches[0].category == CrossPlaneMismatchCategory.EVIDENCE_INSUFFICIENT


class TestDuplicateCandidateDetection:
    def test_detect_duplicate_candidates(self):
        src_id = ControlObjectId(uuid.uuid4())
        tgt1_id = ControlObjectId(uuid.uuid4())
        tgt2_id = ControlObjectId(uuid.uuid4())

        c1 = MatchCandidate(
            source_object_id=src_id,
            target_object_id=tgt1_id,
            source_plane=PlaneType.COMMERCIAL,
            target_plane=PlaneType.FIELD,
            score=MatchScore(0.9),
        )
        c2 = MatchCandidate(
            source_object_id=src_id,
            target_object_id=tgt2_id,
            source_plane=PlaneType.COMMERCIAL,
            target_plane=PlaneType.FIELD,
            score=MatchScore(0.88),
        )
        detector = DuplicateDetector(score_gap_threshold=0.05)
        dups = detector.detect([c1, c2])
        assert len(dups) == 1
        assert len(dups[0].duplicate_target_ids) == 2

    def test_no_duplicates_when_gap_large(self):
        src_id = ControlObjectId(uuid.uuid4())
        c1 = MatchCandidate(
            source_object_id=src_id,
            target_object_id=ControlObjectId(uuid.uuid4()),
            source_plane=PlaneType.COMMERCIAL,
            target_plane=PlaneType.FIELD,
            score=MatchScore(0.9),
        )
        c2 = MatchCandidate(
            source_object_id=src_id,
            target_object_id=ControlObjectId(uuid.uuid4()),
            source_plane=PlaneType.COMMERCIAL,
            target_plane=PlaneType.FIELD,
            score=MatchScore(0.5),
        )
        detector = DuplicateDetector(score_gap_threshold=0.05)
        dups = detector.detect([c1, c2])
        assert len(dups) == 0

    def test_rankings_built_correctly(self):
        src_id = ControlObjectId(uuid.uuid4())
        c1 = MatchCandidate(
            source_object_id=src_id,
            target_object_id=ControlObjectId(uuid.uuid4()),
            source_plane=PlaneType.COMMERCIAL,
            target_plane=PlaneType.FIELD,
            score=MatchScore(0.9),
        )
        c2 = MatchCandidate(
            source_object_id=src_id,
            target_object_id=ControlObjectId(uuid.uuid4()),
            source_plane=PlaneType.COMMERCIAL,
            target_plane=PlaneType.FIELD,
            score=MatchScore(0.7),
        )
        detector = DuplicateDetector(score_gap_threshold=0.05)
        rankings = detector.build_rankings([c1, c2])
        assert len(rankings) == 1
        assert float(rankings[0].top_score) == 0.9
        assert not rankings[0].is_ambiguous


class TestMissingObjectClassification:
    def test_missing_in_field(self):
        svc = GraphService()
        src = _make_object(svc, "Only Commercial", PlaneType.COMMERCIAL)
        classifier = MismatchClassifier()
        mismatches = classifier.classify_missing_objects(
            matched_source_ids=set(),
            matched_target_ids=set(),
            source_objects=[src],
            target_objects=[],
            source_plane=PlaneType.COMMERCIAL,
            target_plane=PlaneType.FIELD,
        )
        assert len(mismatches) == 1
        assert mismatches[0].category == CrossPlaneMismatchCategory.MISSING_IN_FIELD

    def test_missing_in_commercial(self):
        svc = GraphService()
        tgt = _make_object(svc, "Only Field", PlaneType.FIELD)
        classifier = MismatchClassifier()
        mismatches = classifier.classify_missing_objects(
            matched_source_ids=set(),
            matched_target_ids=set(),
            source_objects=[],
            target_objects=[tgt],
            source_plane=PlaneType.COMMERCIAL,
            target_plane=PlaneType.FIELD,
        )
        assert len(mismatches) == 1
        assert mismatches[0].category == CrossPlaneMismatchCategory.MISSING_IN_COMMERCIAL

    def test_missing_in_service(self):
        svc = GraphService()
        src = _make_object(svc, "Field Only", PlaneType.FIELD)
        classifier = MismatchClassifier()
        mismatches = classifier.classify_missing_objects(
            matched_source_ids=set(),
            matched_target_ids=set(),
            source_objects=[src],
            target_objects=[],
            source_plane=PlaneType.FIELD,
            target_plane=PlaneType.SERVICE,
        )
        assert len(mismatches) == 1
        assert mismatches[0].category == CrossPlaneMismatchCategory.MISSING_IN_SERVICE


class TestIdentifierConflict:
    def test_identifier_conflict_detected(self):
        svc = GraphService()
        src = _make_object(
            svc,
            "A",
            PlaneType.COMMERCIAL,
            domain="test",
            correlation_keys={"contract_ref": "C1"},
        )
        tgt = _make_object(
            svc,
            "B",
            PlaneType.FIELD,
            domain="test",
            correlation_keys={"contract_ref": "C2"},
        )
        classifier = MismatchClassifier()
        mismatches = classifier.classify_identifier_conflicts([src], [tgt])
        assert len(mismatches) == 1
        assert mismatches[0].category == CrossPlaneMismatchCategory.IDENTIFIER_CONFLICT


class TestCoverageExpectation:
    def test_coverage_gap_detected(self):
        svc = GraphService()
        obj = _make_object(svc, "A", PlaneType.COMMERCIAL, object_kind="rate_card_entry")
        expectations = [
            ExpectedPlaneCoverage(
                plane=PlaneType.COMMERCIAL,
                expected_object_kinds=["rate_card_entry", "billable_event"],
                min_objects_per_kind={"rate_card_entry": 1, "billable_event": 1},
            )
        ]
        analyzer = CoverageAnalyzer()
        result = analyzer.analyze([obj], expectations)
        assert not result.is_fully_covered
        assert result.gap_count == 1
        assert result.gaps[0].expected_object_kind == "billable_event"

    def test_coverage_fully_met(self):
        svc = GraphService()
        obj1 = _make_object(svc, "A", PlaneType.COMMERCIAL, object_kind="rate_card_entry")
        obj2 = _make_object(svc, "B", PlaneType.COMMERCIAL, object_kind="billable_event")
        expectations = [
            ExpectedPlaneCoverage(
                plane=PlaneType.COMMERCIAL,
                expected_object_kinds=["rate_card_entry", "billable_event"],
                min_objects_per_kind={"rate_card_entry": 1, "billable_event": 1},
            )
        ]
        analyzer = CoverageAnalyzer()
        result = analyzer.analyze([obj1, obj2], expectations)
        assert result.is_fully_covered

    def test_evidence_sufficiency_insufficient(self):
        svc = GraphService()
        obj = _make_object(svc, "NoEvidence", PlaneType.COMMERCIAL)
        evaluator = EvidenceSufficiencyEvaluator(required_evidence_types=["contract_doc"])
        result = evaluator.evaluate_object(obj)
        assert not result.is_sufficient
        assert "contract_doc" in result.missing_evidence_types


class TestDeterministicHashing:
    def test_outcome_hash_is_deterministic(self):
        outcome = ReconciliationOutcome(
            outcome_type=ReconciliationOutcomeType.MISMATCH_DETECTED,
            source_object_id=ControlObjectId(uuid.UUID("12345678-1234-1234-1234-123456789abc")),
            target_object_id=ControlObjectId(uuid.UUID("abcdefab-abcd-abcd-abcd-abcdefabcdef")),
            mismatches=[
                ReconciliationMismatch(
                    category=CrossPlaneMismatchCategory.COST_CONFLICT,
                    source_object_id=ControlObjectId(
                        uuid.UUID("12345678-1234-1234-1234-123456789abc")
                    ),
                    target_object_id=ControlObjectId(
                        uuid.UUID("abcdefab-abcd-abcd-abcd-abcdefabcdef")
                    ),
                    description="test",
                    expected_value=100,
                    actual_value=200,
                    rule_id=ReconciliationRuleId("cost-alignment"),
                )
            ],
        )
        h1 = outcome.compute_hash()
        h2 = outcome.compute_hash()
        assert h1 == h2
        assert len(h1) == 64

    def test_run_hash_is_deterministic(self):
        scope = ReconciliationScope(
            scope_type=ReconciliationScopeType.BY_PLANE_COMBINATION,
            planes=[PlaneType.COMMERCIAL, PlaneType.FIELD],
            tenant_id=TENANT,
        )
        run = ReconciliationRun(
            id=ReconciliationRunId(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")),
            tenant_id=TENANT,
            scope=scope,
            target=ReconciliationTarget(),
        )
        h1 = run.compute_run_hash()
        h2 = run.compute_run_hash()
        assert h1 == h2


class TestReconciliationCaseCreation:
    def test_case_factory_creates_case(self):
        run_id = new_run_id()
        outcome = ReconciliationOutcome(
            outcome_type=ReconciliationOutcomeType.MISMATCH_DETECTED,
            source_object_id=ControlObjectId(uuid.uuid4()),
            target_object_id=ControlObjectId(uuid.uuid4()),
        )
        factory = ReconciliationCaseFactory()
        case = factory.create_case(run_id, TENANT, outcome, domain="test")
        assert case.run_id == run_id
        assert case.status == ReconciliationCaseStatus.OPEN
        assert case.domain == "test"

    def test_case_priority_for_duplicate(self):
        factory = ReconciliationCaseFactory()
        outcome = ReconciliationOutcome(
            outcome_type=ReconciliationOutcomeType.DUPLICATE_DETECTED,
        )
        case = factory.create_case(new_run_id(), TENANT, outcome)
        assert case.priority == ReconciliationCasePriority.HIGH

    def test_case_repository_store_and_query(self):
        repo = InMemoryReconciliationCaseRepository()
        run_id = new_run_id()
        case = ReconciliationCase(
            run_id=run_id,
            tenant_id=TENANT,
            outcome=ReconciliationOutcome(
                outcome_type=ReconciliationOutcomeType.MISMATCH_DETECTED,
            ),
        )
        repo.store_case(case)
        assert repo.get_case(case.id) is not None
        assert len(repo.list_cases_for_run(run_id)) == 1


class TestFullReconciliationOrchestration:
    def test_happy_path_cross_plane(self):
        audit_hook = FabricAuditHook()
        svc = GraphService(audit_hook=audit_hook)

        src = _make_object(
            svc,
            "Contract Rate",
            PlaneType.COMMERCIAL,
            "test",
            payload={"quantity": 10, "cost": 100},
            correlation_keys={"contract_ref": "C1"},
        )
        tgt = _make_object(
            svc,
            "Field Rate",
            PlaneType.FIELD,
            "test",
            payload={"quantity": 10, "cost": 100},
            correlation_keys={"contract_ref": "C1"},
        )
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=src.id,
                target_id=tgt.id,
                link_type=ControlLinkType.FULFILLS,
            ),
        )

        orchestrator = ReconciliationOrchestrator(
            graph_service=svc,
            audit_hook=audit_hook,
        )

        scope = ReconciliationScope(
            scope_type=ReconciliationScopeType.BY_PLANE_COMBINATION,
            planes=[PlaneType.COMMERCIAL, PlaneType.FIELD],
            domains=["test"],
            tenant_id=TENANT,
        )
        request = ReconciliationRequest(
            tenant_id=TENANT,
            scope=scope,
            target=ReconciliationTarget(),
        )
        result = orchestrator.execute(request)
        assert result.run.status == ReconciliationStatus.COMPLETED
        assert result.run.run_hash != ""
        assert result.summary is not None
        assert result.summary.total_candidates_generated >= 1

    def test_mismatch_detected_cross_plane(self):
        svc = GraphService()
        src = _make_object(
            svc,
            "Src",
            PlaneType.COMMERCIAL,
            "test",
            payload={"cost": 100},
            correlation_keys={"ref": "R1"},
        )
        tgt = _make_object(
            svc,
            "Tgt",
            PlaneType.FIELD,
            "test",
            payload={"cost": 999},
            correlation_keys={"ref": "R1"},
        )

        orchestrator = ReconciliationOrchestrator(graph_service=svc)
        scope = ReconciliationScope(
            scope_type=ReconciliationScopeType.BY_PLANE_COMBINATION,
            planes=[PlaneType.COMMERCIAL, PlaneType.FIELD],
            domains=["test"],
            tenant_id=TENANT,
        )
        result = orchestrator.execute(
            ReconciliationRequest(tenant_id=TENANT, scope=scope, target=ReconciliationTarget())
        )
        all_mismatches = [m for o in result.run.outcomes for m in o.mismatches]
        cost_mismatches = [
            m for m in all_mismatches if m.category == CrossPlaneMismatchCategory.COST_CONFLICT
        ]
        assert len(cost_mismatches) >= 1

    def test_three_plane_reconciliation(self):
        svc = GraphService()
        commercial = _make_object(
            svc,
            "Contract",
            PlaneType.COMMERCIAL,
            "test",
            correlation_keys={"ref": "X"},
        )
        field = _make_object(
            svc,
            "Work Order",
            PlaneType.FIELD,
            "test",
            correlation_keys={"ref": "X"},
        )
        service = _make_object(
            svc,
            "Incident",
            PlaneType.SERVICE,
            "test",
            correlation_keys={"ref": "X"},
        )

        orchestrator = ReconciliationOrchestrator(graph_service=svc)
        scope = ReconciliationScope(
            scope_type=ReconciliationScopeType.BY_PLANE_COMBINATION,
            planes=[PlaneType.COMMERCIAL, PlaneType.FIELD],
            domains=["test"],
            tenant_id=TENANT,
        )
        result = orchestrator.execute(
            ReconciliationRequest(tenant_id=TENANT, scope=scope, target=ReconciliationTarget())
        )
        assert result.run.status == ReconciliationStatus.COMPLETED


class TestAuditEmission:
    def test_run_started_and_completed_events(self):
        audit_hook = FabricAuditHook()
        svc = GraphService(audit_hook=audit_hook)
        _make_object(svc, "A", PlaneType.COMMERCIAL, "test", correlation_keys={"r": "1"})
        _make_object(svc, "B", PlaneType.FIELD, "test", correlation_keys={"r": "1"})

        orchestrator = ReconciliationOrchestrator(graph_service=svc, audit_hook=audit_hook)
        scope = ReconciliationScope(
            scope_type=ReconciliationScopeType.BY_PLANE_COMBINATION,
            planes=[PlaneType.COMMERCIAL, PlaneType.FIELD],
            domains=["test"],
            tenant_id=TENANT,
        )
        orchestrator.execute(
            ReconciliationRequest(tenant_id=TENANT, scope=scope, target=ReconciliationTarget())
        )

        started = audit_hook.get_events_by_type(FabricAuditEventType.RECONCILIATION_RUN_STARTED)
        completed = audit_hook.get_events_by_type(FabricAuditEventType.RECONCILIATION_RUN_COMPLETED)
        assert len(started) >= 1
        assert len(completed) >= 1

    def test_candidate_generated_event(self):
        audit_hook = FabricAuditHook()
        svc = GraphService(audit_hook=audit_hook)
        _make_object(svc, "A", PlaneType.COMMERCIAL, "test", correlation_keys={"r": "1"})
        _make_object(svc, "B", PlaneType.FIELD, "test", correlation_keys={"r": "1"})

        orchestrator = ReconciliationOrchestrator(graph_service=svc, audit_hook=audit_hook)
        scope = ReconciliationScope(
            scope_type=ReconciliationScopeType.BY_PLANE_COMBINATION,
            planes=[PlaneType.COMMERCIAL, PlaneType.FIELD],
            domains=["test"],
            tenant_id=TENANT,
        )
        orchestrator.execute(
            ReconciliationRequest(tenant_id=TENANT, scope=scope, target=ReconciliationTarget())
        )
        events = audit_hook.get_events_by_type(
            FabricAuditEventType.RECONCILIATION_CANDIDATE_GENERATED
        )
        assert len(events) >= 1

    def test_outcome_hashed_event(self):
        audit_hook = FabricAuditHook()
        svc = GraphService(audit_hook=audit_hook)
        _make_object(svc, "A", PlaneType.COMMERCIAL, "test", correlation_keys={"r": "1"})
        _make_object(svc, "B", PlaneType.FIELD, "test", correlation_keys={"r": "1"})

        orchestrator = ReconciliationOrchestrator(graph_service=svc, audit_hook=audit_hook)
        scope = ReconciliationScope(
            scope_type=ReconciliationScopeType.BY_PLANE_COMBINATION,
            planes=[PlaneType.COMMERCIAL, PlaneType.FIELD],
            domains=["test"],
            tenant_id=TENANT,
        )
        orchestrator.execute(
            ReconciliationRequest(tenant_id=TENANT, scope=scope, target=ReconciliationTarget())
        )
        events = audit_hook.get_events_by_type(FabricAuditEventType.RECONCILIATION_OUTCOME_HASHED)
        assert len(events) >= 1


class TestDomainPackRuleRegistration:
    def test_contract_margin_rule_registers(self):
        from app.core.domain_integration import ContractMarginCostRule

        registry = build_default_rule_registry()
        rule = ContractMarginCostRule()
        registry.register_rule(rule)
        assert registry.get_rule(ReconciliationRuleId("contract-margin-cost-alignment")) is not None

    def test_telco_ops_rule_registers(self):
        from app.core.domain_integration import TelcoOpsStateAlignmentRule

        registry = build_default_rule_registry()
        rule = TelcoOpsStateAlignmentRule()
        registry.register_rule(rule)
        assert (
            registry.get_rule(ReconciliationRuleId("telco-ops-service-state-alignment")) is not None
        )

    def test_utilities_field_rule_registers(self):
        from app.core.domain_integration import UtilitiesFieldCompletionRule

        registry = build_default_rule_registry()
        rule = UtilitiesFieldCompletionRule()
        registry.register_rule(rule)
        assert (
            registry.get_rule(ReconciliationRuleId("utilities-field-completion-billing"))
            is not None
        )

    def test_register_all_domain_pack_rules(self):
        from app.core.domain_integration import register_domain_pack_reconciliation_rules

        registry = build_default_rule_registry()
        initial_count = registry.rule_count
        register_domain_pack_reconciliation_rules(registry)
        assert registry.rule_count == initial_count + 3

    def test_coverage_expectations_available(self):
        from app.core.domain_integration import (
            get_contract_margin_coverage_expectations,
            get_telco_ops_coverage_expectations,
            get_utilities_field_coverage_expectations,
        )

        cm = get_contract_margin_coverage_expectations()
        uf = get_utilities_field_coverage_expectations()
        to = get_telco_ops_coverage_expectations()
        assert len(cm) == 1
        assert cm[0].plane == PlaneType.COMMERCIAL
        assert len(uf) == 1
        assert uf[0].plane == PlaneType.FIELD
        assert len(to) == 1
        assert to[0].plane == PlaneType.SERVICE


class TestRuleRegistry:
    def test_default_registry_has_9_rules(self):
        registry = build_default_rule_registry()
        assert registry.rule_count == 9

    def test_get_applicable_rules_filters(self):
        svc = GraphService()
        src = _make_object(svc, "A", PlaneType.COMMERCIAL)
        tgt = _make_object(svc, "B", PlaneType.COMMERCIAL)
        registry = build_default_rule_registry()
        applicable = registry.get_applicable_rules(src, tgt)
        cross_plane_only = [r for r in applicable if r.applicability.requires_cross_plane]
        assert len(cross_plane_only) == 0

    def test_rule_set_retrieval(self):
        registry = build_default_rule_registry()
        default_set = registry.get_rule_set("default-cross-plane")
        assert len(default_set) == 9

    def test_custom_rule_registration(self):
        from app.core.reconciliation.rule_model import (
            ReconciliationRule,
            ReconciliationRuleApplicability,
            ReconciliationRuleCategory,
            ReconciliationRuleResult,
            ReconciliationRuleWeight,
        )

        class CustomRule(ReconciliationRule):
            rule_id = ReconciliationRuleId("custom-test")
            category = ReconciliationRuleCategory.IDENTITY_CORRELATION
            weight = ReconciliationRuleWeight(
                rule_id=ReconciliationRuleId("custom-test"), weight=1.0
            )
            applicability = ReconciliationRuleApplicability()

            def evaluate(self, source, target, links):
                return ReconciliationRuleResult(
                    rule_id=self.rule_id,
                    score_contribution=1.0,
                    matched=True,
                )

        registry = build_default_rule_registry()
        registry.register_rule(CustomRule())
        assert registry.rule_count == 10
