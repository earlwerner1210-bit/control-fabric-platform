"""Wave 2 reconciliation orchestrator — coordinates the full reconciliation lifecycle."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.audit import FabricAuditHook
from app.core.control_link import ControlLink
from app.core.control_object import ControlObject
from app.core.graph.service import GraphService
from app.core.reconciliation.coverage import CoverageAnalyzer, EvidenceSufficiencyEvaluator
from app.core.reconciliation.domain_types import (
    CoverageGap,
    CrossPlaneMismatchCategory,
    ReconciliationAssemblyInput,
    ReconciliationCase,
    ReconciliationCasePriority,
    ReconciliationCaseStatus,
    ReconciliationDecisionTrace,
    ReconciliationDeterminismLevel,
    ReconciliationExecutionPlan,
    ReconciliationExecutionResult,
    ReconciliationOutcome,
    ReconciliationOutcomeType,
    ReconciliationRequest,
    ReconciliationRun,
    ReconciliationRunId,
    ReconciliationScope,
    ReconciliationScopeType,
    ReconciliationStatus,
    ReconciliationTarget,
    new_case_id,
    new_run_id,
)
from app.core.reconciliation.matching import (
    CandidateGenerator,
    CandidateScorer,
    DuplicateDetector,
    MismatchClassifier,
    ReconciliationAssembler,
)
from app.core.reconciliation.reconciliation_audit import ReconciliationAuditIntegration
from app.core.reconciliation.repository import (
    InMemoryReconciliationCaseRepository,
    InMemoryReconciliationRunRepository,
    ReconciliationCaseRepository,
    ReconciliationRunRepository,
)
from app.core.reconciliation.rule_model import (
    ReconciliationRuleRegistry,
    ReconciliationRuleTraceEntry,
    build_default_rule_registry,
)
from app.core.types import GraphTraversalPolicy, PlaneType


class ReconciliationCaseFactory:
    """Creates reconciliation cases from outcomes."""

    def create_case(
        self,
        run_id: ReconciliationRunId,
        tenant_id: uuid.UUID,
        outcome: ReconciliationOutcome,
        domain: str = "",
    ) -> ReconciliationCase:
        priority = self._derive_priority(outcome)
        involved_ids = []
        involved_planes: list[PlaneType] = []
        if outcome.source_object_id:
            involved_ids.append(outcome.source_object_id)
        if outcome.target_object_id:
            involved_ids.append(outcome.target_object_id)
        if outcome.candidate:
            if outcome.candidate.source_plane not in involved_planes:
                involved_planes.append(outcome.candidate.source_plane)
            if outcome.candidate.target_plane not in involved_planes:
                involved_planes.append(outcome.candidate.target_plane)

        return ReconciliationCase(
            run_id=run_id,
            tenant_id=tenant_id,
            status=ReconciliationCaseStatus.OPEN,
            priority=priority,
            outcome=outcome,
            involved_object_ids=involved_ids,
            involved_planes=involved_planes,
            domain=domain,
            description=self._derive_description(outcome),
        )

    def _derive_priority(self, outcome: ReconciliationOutcome) -> ReconciliationCasePriority:
        if outcome.outcome_type == ReconciliationOutcomeType.FULLY_RECONCILED:
            return ReconciliationCasePriority.LOW
        if outcome.outcome_type == ReconciliationOutcomeType.DUPLICATE_DETECTED:
            return ReconciliationCasePriority.HIGH
        if outcome.outcome_type == ReconciliationOutcomeType.COVERAGE_GAP:
            return ReconciliationCasePriority.MEDIUM
        if outcome.outcome_type == ReconciliationOutcomeType.INSUFFICIENT_EVIDENCE:
            return ReconciliationCasePriority.MEDIUM
        if outcome.outcome_type == ReconciliationOutcomeType.MISMATCH_DETECTED:
            has_cost = any(
                m.category == CrossPlaneMismatchCategory.COST_CONFLICT for m in outcome.mismatches
            )
            return ReconciliationCasePriority.HIGH if has_cost else ReconciliationCasePriority.MEDIUM
        if outcome.outcome_type == ReconciliationOutcomeType.DISPUTED:
            return ReconciliationCasePriority.CRITICAL
        return ReconciliationCasePriority.MEDIUM

    def _derive_description(self, outcome: ReconciliationOutcome) -> str:
        otype = outcome.outcome_type.value
        mismatch_count = len(outcome.mismatches)
        if outcome.source_object_id and outcome.target_object_id:
            return (
                f"{otype}: {outcome.source_object_id} ↔ {outcome.target_object_id} "
                f"({mismatch_count} mismatches)"
            )
        if outcome.coverage_gap:
            return f"{otype}: {outcome.coverage_gap.description}"
        return f"{otype}: {mismatch_count} mismatches"


class ReconciliationRunFactory:
    """Creates reconciliation run instances."""

    def create_run(
        self,
        request: ReconciliationRequest,
    ) -> ReconciliationRun:
        return ReconciliationRun(
            tenant_id=request.tenant_id,
            scope=request.scope,
            target=request.target,
            status=ReconciliationStatus.PENDING,
        )


class ReconciliationOrchestrator:
    """Coordinates the full cross-plane reconciliation lifecycle."""

    def __init__(
        self,
        graph_service: GraphService,
        rule_registry: ReconciliationRuleRegistry | None = None,
        run_repository: ReconciliationRunRepository | None = None,
        case_repository: ReconciliationCaseRepository | None = None,
        audit_hook: FabricAuditHook | None = None,
        match_threshold: float = 0.7,
        duplicate_gap_threshold: float = 0.05,
    ) -> None:
        self._graph = graph_service
        self._rule_registry = rule_registry or build_default_rule_registry()
        self._run_repo = run_repository or InMemoryReconciliationRunRepository()
        self._case_repo = case_repository or InMemoryReconciliationCaseRepository()
        self._audit_hook = audit_hook or FabricAuditHook()
        self._audit = ReconciliationAuditIntegration(self._audit_hook)
        self._match_threshold = match_threshold
        self._duplicate_gap_threshold = duplicate_gap_threshold
        self._candidate_generator = CandidateGenerator()
        self._candidate_scorer = CandidateScorer(self._rule_registry)
        self._duplicate_detector = DuplicateDetector(self._duplicate_gap_threshold)
        self._mismatch_classifier = MismatchClassifier()
        self._assembler = ReconciliationAssembler(self._match_threshold)
        self._coverage_analyzer = CoverageAnalyzer()
        self._case_factory = ReconciliationCaseFactory()
        self._run_factory = ReconciliationRunFactory()

    @property
    def rule_registry(self) -> ReconciliationRuleRegistry:
        return self._rule_registry

    @property
    def run_repository(self) -> ReconciliationRunRepository:
        return self._run_repo

    @property
    def case_repository(self) -> ReconciliationCaseRepository:
        return self._case_repo

    def execute(self, request: ReconciliationRequest) -> ReconciliationExecutionResult:
        run = self._run_factory.create_run(request)
        run.status = ReconciliationStatus.IN_PROGRESS
        self._run_repo.store_run(run)

        self._audit.reconciliation_run_started(
            run_id=run.id,
            tenant_id=run.tenant_id,
            planes=request.scope.planes,
        )

        plan = self._build_execution_plan(run, request)

        source_objects, target_objects, links = self._fetch_graph_data(request)

        objects_by_id = {uuid.UUID(bytes=o.id.bytes): o for o in source_objects + target_objects}

        candidates = self._candidate_generator.generate(source_objects, target_objects, links)

        for candidate in candidates:
            self._audit.reconciliation_candidate_generated(
                run_id=run.id,
                tenant_id=run.tenant_id,
                source_object_id=candidate.source_object_id,
                target_object_id=candidate.target_object_id,
                match_method=candidate.match_method,
            )

        scored_candidates, rule_traces = self._candidate_scorer.score_all(
            candidates, objects_by_id, links
        )

        duplicates = self._duplicate_detector.detect(scored_candidates)
        for dup_set in duplicates:
            self._audit.reconciliation_duplicate_detected(
                run_id=run.id,
                tenant_id=run.tenant_id,
                source_object_id=dup_set.source_object_id,
                duplicate_count=len(dup_set.duplicate_target_ids),
            )

        rankings = self._duplicate_detector.build_rankings(scored_candidates)

        matched_source_ids = {
            uuid.UUID(bytes=c.source_object_id.bytes)
            for c in scored_candidates
            if float(c.score) > 0.0
        }
        matched_target_ids = {
            uuid.UUID(bytes=c.target_object_id.bytes)
            for c in scored_candidates
            if float(c.score) > 0.0
        }

        source_plane = request.scope.planes[0] if request.scope.planes else PlaneType.COMMERCIAL
        target_plane = request.scope.planes[1] if len(request.scope.planes) > 1 else PlaneType.FIELD

        missing_mismatches = self._mismatch_classifier.classify_missing_objects(
            matched_source_ids,
            matched_target_ids,
            source_objects,
            target_objects,
            source_plane,
            target_plane,
        )

        identifier_mismatches = self._mismatch_classifier.classify_identifier_conflicts(
            source_objects, target_objects
        )

        all_extra_mismatches = missing_mismatches + identifier_mismatches

        coverage_result = self._coverage_analyzer.analyze(
            source_objects + target_objects,
            request.coverage_expectations,
        )
        if not coverage_result.is_fully_covered:
            for gap in coverage_result.gaps:
                self._audit.reconciliation_coverage_gap_detected(
                    run_id=run.id,
                    tenant_id=run.tenant_id,
                    plane=gap.plane,
                    expected_kind=gap.expected_object_kind,
                    missing_count=gap.missing_count,
                )

        evidence_evaluator = EvidenceSufficiencyEvaluator()
        evidence_results = evidence_evaluator.get_insufficient(source_objects + target_objects)
        for ev_result in evidence_results:
            self._audit.reconciliation_insufficient_evidence(
                run_id=run.id,
                tenant_id=run.tenant_id,
                object_id=ev_result.object_id,
                missing_types=ev_result.missing_evidence_types,
            )

        assembly_input = ReconciliationAssemblyInput(
            candidates=scored_candidates,
            rankings=rankings,
            duplicates=duplicates,
            coverage_result=coverage_result,
            evidence_results=evidence_results,
            mismatches=all_extra_mismatches,
        )

        assembly_output = self._assembler.assemble(
            assembly_input,
            run_id=run.id,
            tenant_id=run.tenant_id,
            planes=request.scope.planes,
            domains=request.scope.domains,
        )

        for outcome in assembly_output.outcomes:
            self._audit.reconciliation_outcome_hashed(
                run_id=run.id,
                tenant_id=run.tenant_id,
                outcome_hash=outcome.hash,
                outcome_type=outcome.outcome_type,
            )

        cases: list[ReconciliationCase] = []
        for outcome in assembly_output.outcomes:
            if outcome.outcome_type == ReconciliationOutcomeType.FULLY_RECONCILED:
                if not outcome.mismatches:
                    continue
            case = self._case_factory.create_case(
                run_id=run.id,
                tenant_id=run.tenant_id,
                outcome=outcome,
                domain=request.scope.domains[0] if request.scope.domains else "",
            )
            self._case_repo.store_case(case)
            cases.append(case)
            self._audit.reconciliation_case_created(case=case)
            self._audit.reconciliation_case_classified(
                case_id=case.id,
                tenant_id=run.tenant_id,
                outcome_type=outcome.outcome_type,
            )

        decision_trace = ReconciliationDecisionTrace(
            run_id=run.id,
            rule_traces=[
                {
                    "rule_id": t.rule_id,
                    "category": t.category.value,
                    "source_object_id": t.source_object_id,
                    "target_object_id": t.target_object_id,
                    "score_contribution": t.score_contribution,
                    "applied": t.applied,
                }
                for t in rule_traces
            ],
            candidate_count=len(scored_candidates),
            mismatch_count=sum(len(o.mismatches) for o in assembly_output.outcomes),
            outcome_count=len(assembly_output.outcomes),
        )

        run.outcomes = assembly_output.outcomes
        run.cases = cases
        run.summary = assembly_output.summary
        run.decision_trace = decision_trace
        run.status = ReconciliationStatus.COMPLETED
        run.completed_at = datetime.now(UTC)
        if assembly_output.summary:
            assembly_output.summary.total_objects_evaluated = len(source_objects) + len(
                target_objects
            )
            assembly_output.summary.total_cases_created = len(cases)
        run.compute_run_hash()
        self._run_repo.store_run(run)

        self._audit.reconciliation_run_completed(
            run_id=run.id,
            tenant_id=run.tenant_id,
            run_hash=run.run_hash,
            outcome_count=len(assembly_output.outcomes),
            case_count=len(cases),
        )

        return ReconciliationExecutionResult(
            run=run,
            cases=cases,
            summary=assembly_output.summary or ReconciliationSummary(
                run_id=run.id, tenant_id=run.tenant_id
            ),
            execution_plan=plan,
        )

    def _build_execution_plan(
        self,
        run: ReconciliationRun,
        request: ReconciliationRequest,
    ) -> ReconciliationExecutionPlan:
        rule_ids = [r.rule_id for r in self._rule_registry.list_rules()]
        return ReconciliationExecutionPlan(
            run_id=run.id,
            scope=request.scope,
            target=request.target,
            planes_to_reconcile=list(request.scope.planes),
            rule_ids_to_apply=rule_ids,
            match_threshold=request.match_threshold,
            duplicate_threshold=request.duplicate_threshold,
            coverage_expectations=list(request.coverage_expectations),
        )

    def _fetch_graph_data(
        self,
        request: ReconciliationRequest,
    ) -> tuple[list[ControlObject], list[ControlObject], list[ControlLink]]:
        tenant_id = request.scope.tenant_id
        planes = request.scope.planes

        if request.target.graph_slice_root_ids:
            policy = GraphTraversalPolicy(
                max_depth=5,
                allowed_planes=planes if planes else None,
            )
            slice_result = self._graph.get_typed_graph_slice(
                request.target.graph_slice_root_ids, policy
            )
            all_objects: list[ControlObject] = []
            for oid in slice_result.object_ids:
                obj = self._graph.get_object(oid)
                if obj:
                    all_objects.append(obj)
            all_links = self._graph.repository.get_all_links(tenant_id)
            relevant_ids = {uuid.UUID(bytes=oid.bytes) for oid in slice_result.object_ids}
            relevant_links = [
                l
                for l in all_links
                if uuid.UUID(bytes=l.source_id.bytes) in relevant_ids
                or uuid.UUID(bytes=l.target_id.bytes) in relevant_ids
            ]
            if len(planes) >= 2:
                source_objects = [o for o in all_objects if o.plane == planes[0]]
                target_objects = [o for o in all_objects if o.plane != planes[0]]
            else:
                source_objects = all_objects
                target_objects = []
            return source_objects, target_objects, relevant_links

        if request.target.object_ids:
            all_objects = []
            for oid in request.target.object_ids:
                obj = self._graph.get_object(oid)
                if obj:
                    all_objects.append(obj)
            all_links = self._graph.repository.get_all_links(tenant_id)
            obj_id_set = {uuid.UUID(bytes=o.id.bytes) for o in all_objects}
            relevant_links = [
                l
                for l in all_links
                if uuid.UUID(bytes=l.source_id.bytes) in obj_id_set
                or uuid.UUID(bytes=l.target_id.bytes) in obj_id_set
            ]
            if len(planes) >= 2:
                source_objects = [o for o in all_objects if o.plane == planes[0]]
                target_objects = [o for o in all_objects if o.plane != planes[0]]
            else:
                source_objects = all_objects
                target_objects = []
            return source_objects, target_objects, relevant_links

        source_plane = planes[0] if planes else PlaneType.COMMERCIAL
        target_plane = planes[1] if len(planes) > 1 else PlaneType.FIELD

        domains = request.scope.domains
        domain_filter = domains[0] if domains else None

        source_objects = self._graph.list_objects(
            tenant_id, plane=source_plane, domain=domain_filter
        )
        target_objects = self._graph.list_objects(
            tenant_id, plane=target_plane, domain=domain_filter
        )

        if request.scope.object_kinds:
            source_objects = [
                o for o in source_objects if o.object_kind in request.scope.object_kinds
            ]
            target_objects = [
                o for o in target_objects if o.object_kind in request.scope.object_kinds
            ]

        all_links = self._graph.repository.get_all_links(tenant_id)
        return source_objects, target_objects, all_links
