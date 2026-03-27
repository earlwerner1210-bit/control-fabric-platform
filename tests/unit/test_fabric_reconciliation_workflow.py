"""Tests for the Fabric Reconciliation Workflow."""

from __future__ import annotations

import uuid

import pytest

from app.workflows.fabric_reconciliation.workflow import (
    FabricReconciliationActivities,
    FabricReconciliationInput,
    FabricReconciliationWorkflow,
)

TENANT = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))


class TestFabricReconciliationWorkflow:
    def test_clean_run_no_conflicts(self):
        wf = FabricReconciliationWorkflow(FabricReconciliationActivities())
        result = wf.run(FabricReconciliationInput(tenant_id=TENANT))
        assert result.status == "completed"
        assert result.total_conflicts == 0
        assert result.auto_resolved == 0
        assert result.error is None

    def test_with_contradictions(self):
        class CustomActivities(FabricReconciliationActivities):
            def run_contradiction_check(self, tenant_id, snapshot_id):
                return [
                    {
                        "conflict_type": "contradiction",
                        "severity": "error",
                        "resolution": "unresolved",
                    }
                ]

        wf = FabricReconciliationWorkflow(CustomActivities())
        result = wf.run(FabricReconciliationInput(tenant_id=TENANT))
        assert result.status == "completed"
        assert result.total_conflicts == 1
        assert result.conflicts_by_type["contradiction"] == 1

    def test_auto_resolve_info(self):
        class CustomActivities(FabricReconciliationActivities):
            def run_confidence_divergence_check(self, tenant_id, snapshot_id):
                return [
                    {
                        "conflict_type": "confidence_divergence",
                        "severity": "info",
                        "resolution": "unresolved",
                    }
                ]

        wf = FabricReconciliationWorkflow(CustomActivities())
        result = wf.run(FabricReconciliationInput(tenant_id=TENANT, auto_resolve_info=True))
        assert result.auto_resolved == 1

    def test_escalate_critical(self):
        class CustomActivities(FabricReconciliationActivities):
            def run_authorization_gap_check(self, tenant_id, snapshot_id):
                return [
                    {
                        "conflict_type": "authorization_gap",
                        "severity": "critical",
                        "resolution": "unresolved",
                    }
                ]

        wf = FabricReconciliationWorkflow(CustomActivities())
        result = wf.run(FabricReconciliationInput(tenant_id=TENANT, escalate_critical=True))
        assert result.escalated == 1

    def test_scope_planes(self):
        wf = FabricReconciliationWorkflow(FabricReconciliationActivities())
        result = wf.run(
            FabricReconciliationInput(
                tenant_id=TENANT,
                scope_planes=["commercial", "field"],
            )
        )
        assert result.status == "completed"

    def test_error_handling(self):
        class FailingActivities(FabricReconciliationActivities):
            def build_fabric_snapshot(self, tenant_id, scope_planes, scope_domains):
                raise RuntimeError("Snapshot failed")

        wf = FabricReconciliationWorkflow(FailingActivities())
        result = wf.run(FabricReconciliationInput(tenant_id=TENANT))
        assert result.status == "failed"
        assert result.error is not None

    def test_mixed_conflicts(self):
        class CustomActivities(FabricReconciliationActivities):
            def run_contradiction_check(self, tenant_id, snapshot_id):
                return [
                    {
                        "conflict_type": "contradiction",
                        "severity": "error",
                        "resolution": "unresolved",
                    }
                ]

            def run_authorization_gap_check(self, tenant_id, snapshot_id):
                return [
                    {
                        "conflict_type": "authorization_gap",
                        "severity": "critical",
                        "resolution": "unresolved",
                    }
                ]

            def run_confidence_divergence_check(self, tenant_id, snapshot_id):
                return [
                    {
                        "conflict_type": "confidence_divergence",
                        "severity": "info",
                        "resolution": "unresolved",
                    }
                ]

        wf = FabricReconciliationWorkflow(CustomActivities())
        result = wf.run(
            FabricReconciliationInput(
                tenant_id=TENANT,
                auto_resolve_info=True,
                escalate_critical=True,
            )
        )
        assert result.total_conflicts == 3
        assert result.auto_resolved == 1
        assert result.escalated == 1
        assert result.unresolved == 1
