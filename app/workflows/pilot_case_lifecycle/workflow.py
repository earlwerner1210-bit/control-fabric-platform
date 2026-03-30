"""Temporal workflow for pilot case lifecycle."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class PilotCaseLifecycleInput:
    """Input for the pilot case lifecycle workflow."""

    pilot_case_id: str
    tenant_id: str
    workflow_type: str
    title: str
    created_by: str
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    external_refs: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    severity: str = "medium"
    business_impact: str = "moderate"
    baseline_expectation: dict[str, Any] | None = None
    reviewer_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PilotCaseLifecycleOutput:
    """Output from the pilot case lifecycle workflow."""

    pilot_case_id: str
    final_state: str
    review_outcome: str | None = None
    approval_type: str | None = None
    baseline_match_type: str | None = None
    kpi_measurements: list[dict[str, Any]] = field(default_factory=list)
    export_id: str | None = None
    timeline: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


@dataclass
class ActivityResult:
    """Standard activity result."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class PilotCaseLifecycleActivities:
    """Activities for pilot case lifecycle workflow."""

    def __init__(
        self,
        case_service: Any = None,
        evidence_service: Any = None,
        baseline_service: Any = None,
        kpi_service: Any = None,
        export_service: Any = None,
        audit_service: Any = None,
    ) -> None:
        self.case_service = case_service
        self.evidence_service = evidence_service
        self.baseline_service = baseline_service
        self.kpi_service = kpi_service
        self.export_service = export_service
        self.audit_service = audit_service
        self._timeline: list[dict[str, Any]] = []

    def create_pilot_case(self, input_data: PilotCaseLifecycleInput) -> ActivityResult:
        """Create the pilot case record."""
        try:
            now = datetime.now(UTC)
            self._record_timeline("case_created", input_data.pilot_case_id, now)
            self._record_audit(
                "pilot_case.created",
                input_data.pilot_case_id,
                input_data.tenant_id,
                input_data.created_by,
                {
                    "title": input_data.title,
                    "workflow_type": input_data.workflow_type,
                    "severity": input_data.severity,
                },
            )
            return ActivityResult(
                success=True,
                data={
                    "pilot_case_id": input_data.pilot_case_id,
                    "state": "created",
                    "created_at": now.isoformat(),
                },
            )
        except Exception as e:
            return ActivityResult(success=False, error=str(e))

    def link_artifacts(self, pilot_case_id: str, artifacts: list[dict[str, Any]]) -> ActivityResult:
        """Link artifacts to the pilot case."""
        try:
            now = datetime.now(UTC)
            for artifact in artifacts:
                self._record_timeline("artifact_linked", pilot_case_id, now, artifact)
            self._record_audit(
                "pilot_case.artifacts_linked",
                pilot_case_id,
                None,
                None,
                {"artifact_count": len(artifacts)},
            )
            return ActivityResult(
                success=True,
                data={"artifact_count": len(artifacts)},
            )
        except Exception as e:
            return ActivityResult(success=False, error=str(e))

    def assign_reviewer(
        self, pilot_case_id: str, reviewer_id: str, assigned_by: str
    ) -> ActivityResult:
        """Assign a reviewer to the pilot case."""
        try:
            now = datetime.now(UTC)
            self._record_timeline(
                "reviewer_assigned",
                pilot_case_id,
                now,
                {"reviewer_id": reviewer_id},
            )
            self._record_audit(
                "pilot_case.reviewer_assigned",
                pilot_case_id,
                None,
                assigned_by,
                {"reviewer_id": reviewer_id},
            )
            return ActivityResult(
                success=True,
                data={"reviewer_id": reviewer_id, "assigned_at": now.isoformat()},
            )
        except Exception as e:
            return ActivityResult(success=False, error=str(e))

    def transition_state(self, pilot_case_id: str, new_state: str, actor_id: str) -> ActivityResult:
        """Transition pilot case to a new state."""
        try:
            now = datetime.now(UTC)
            self._record_timeline(
                "state_transition",
                pilot_case_id,
                now,
                {"new_state": new_state},
            )
            self._record_audit(
                "pilot_case.state_transition",
                pilot_case_id,
                None,
                actor_id,
                {"new_state": new_state},
            )
            return ActivityResult(
                success=True,
                data={"state": new_state, "transitioned_at": now.isoformat()},
            )
        except Exception as e:
            return ActivityResult(success=False, error=str(e))

    def create_evidence_bundle(
        self, pilot_case_id: str, items: list[dict[str, Any]], chain_stages: list[str]
    ) -> ActivityResult:
        """Create an evidence bundle for the case."""
        try:
            bundle_id = str(uuid.uuid4())
            now = datetime.now(UTC)
            self._record_timeline(
                "evidence_bundle_created",
                pilot_case_id,
                now,
                {"bundle_id": bundle_id, "item_count": len(items)},
            )
            return ActivityResult(
                success=True,
                data={
                    "bundle_id": bundle_id,
                    "item_count": len(items),
                    "chain_stages": chain_stages,
                },
            )
        except Exception as e:
            return ActivityResult(success=False, error=str(e))

    def store_baseline_expectation(
        self, pilot_case_id: str, expectation: dict[str, Any]
    ) -> ActivityResult:
        """Store baseline expectation for comparison."""
        try:
            self._record_timeline(
                "baseline_expectation_stored",
                pilot_case_id,
                datetime.now(UTC),
                expectation,
            )
            return ActivityResult(success=True, data=expectation)
        except Exception as e:
            return ActivityResult(success=False, error=str(e))

    def compare_baseline(
        self,
        pilot_case_id: str,
        platform_outcome: str | None,
        reviewer_outcome: str | None,
    ) -> ActivityResult:
        """Compare against baseline expectation."""
        try:
            now = datetime.now(UTC)
            self._record_timeline(
                "baseline_compared",
                pilot_case_id,
                now,
                {
                    "platform_outcome": platform_outcome,
                    "reviewer_outcome": reviewer_outcome,
                },
            )
            return ActivityResult(
                success=True,
                data={
                    "compared_at": now.isoformat(),
                    "platform_outcome": platform_outcome,
                    "reviewer_outcome": reviewer_outcome,
                },
            )
        except Exception as e:
            return ActivityResult(success=False, error=str(e))

    def record_kpi(
        self, pilot_case_id: str, metric_name: str, metric_value: float, **kwargs: Any
    ) -> ActivityResult:
        """Record a KPI measurement."""
        try:
            measurement_id = str(uuid.uuid4())
            return ActivityResult(
                success=True,
                data={
                    "measurement_id": measurement_id,
                    "metric_name": metric_name,
                    "metric_value": metric_value,
                    **kwargs,
                },
            )
        except Exception as e:
            return ActivityResult(success=False, error=str(e))

    def export_case(
        self,
        pilot_case_id: str,
        exported_by: str,
        format: str = "json",
    ) -> ActivityResult:
        """Export the pilot case."""
        try:
            export_id = str(uuid.uuid4())
            now = datetime.now(UTC)
            self._record_timeline(
                "case_exported",
                pilot_case_id,
                now,
                {"export_id": export_id, "format": format},
            )
            self._record_audit(
                "pilot_case.exported",
                pilot_case_id,
                None,
                exported_by,
                {"export_id": export_id, "format": format},
            )
            return ActivityResult(
                success=True,
                data={
                    "export_id": export_id,
                    "format": format,
                    "exported_at": now.isoformat(),
                },
            )
        except Exception as e:
            return ActivityResult(success=False, error=str(e))

    def get_timeline(self) -> list[dict[str, Any]]:
        """Return the accumulated timeline."""
        return list(self._timeline)

    def _record_timeline(
        self,
        event_type: str,
        pilot_case_id: str,
        timestamp: datetime,
        details: Any = None,
    ) -> None:
        self._timeline.append(
            {
                "event_type": event_type,
                "pilot_case_id": pilot_case_id,
                "timestamp": timestamp.isoformat(),
                "details": details,
            }
        )

    def _record_audit(
        self,
        event_type: str,
        pilot_case_id: str | None,
        tenant_id: str | None,
        actor_id: str | None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self.audit_service is not None:
            try:
                self.audit_service.record(
                    event_type=event_type,
                    resource_id=pilot_case_id,
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    payload=payload or {},
                )
            except Exception:
                pass


class PilotCaseLifecycleWorkflow:
    """Orchestrates the full pilot case lifecycle.

    Workflow steps:
    1. Create pilot case
    2. Link artifacts
    3. Assign reviewer (if provided)
    4. Transition to evidence_ready
    5. Store baseline expectation (if provided)
    6. Transition through workflow_executed -> validation_completed
    7. Move to under_review
    8. (Await external review decision)
    9. Record KPIs
    10. Export case
    """

    def __init__(self, activities: PilotCaseLifecycleActivities | None = None) -> None:
        self.activities = activities or PilotCaseLifecycleActivities()

    def run(self, input_data: PilotCaseLifecycleInput) -> PilotCaseLifecycleOutput:
        """Execute the pilot case lifecycle workflow."""
        pilot_case_id = input_data.pilot_case_id
        kpi_measurements: list[dict[str, Any]] = []
        start_time = datetime.now(UTC)

        # Step 1: Create case
        result = self.activities.create_pilot_case(input_data)
        if not result.success:
            return PilotCaseLifecycleOutput(
                pilot_case_id=pilot_case_id,
                final_state="failed",
                error=result.error,
            )

        # Step 2: Link artifacts
        if input_data.artifacts:
            result = self.activities.link_artifacts(pilot_case_id, input_data.artifacts)
            if not result.success:
                return PilotCaseLifecycleOutput(
                    pilot_case_id=pilot_case_id,
                    final_state="created",
                    error=f"Failed to link artifacts: {result.error}",
                )

        # Step 3: Assign reviewer
        if input_data.reviewer_id:
            self.activities.assign_reviewer(
                pilot_case_id, input_data.reviewer_id, input_data.created_by
            )

        # Step 4: Transition to evidence_ready
        self.activities.transition_state(pilot_case_id, "evidence_ready", input_data.created_by)

        # Step 5: Store baseline expectation
        if input_data.baseline_expectation:
            self.activities.store_baseline_expectation(
                pilot_case_id, input_data.baseline_expectation
            )

        # Step 6: Transition through workflow stages
        self.activities.transition_state(pilot_case_id, "workflow_executed", input_data.created_by)
        self.activities.transition_state(
            pilot_case_id, "validation_completed", input_data.created_by
        )

        # Step 7: Move to under_review
        self.activities.transition_state(pilot_case_id, "under_review", input_data.created_by)

        # Step 8: Record time to review KPI
        elapsed = (datetime.now(UTC) - start_time).total_seconds() / 3600
        kpi_result = self.activities.record_kpi(
            pilot_case_id,
            "time_to_review_setup",
            elapsed,
            metric_unit="hours",
        )
        if kpi_result.success:
            kpi_measurements.append(kpi_result.data)

        return PilotCaseLifecycleOutput(
            pilot_case_id=pilot_case_id,
            final_state="under_review",
            kpi_measurements=kpi_measurements,
            timeline=self.activities.get_timeline(),
        )
