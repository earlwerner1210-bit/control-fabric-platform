"""
Celery tasks — reconciliation, retention, alerting.
"""

from __future__ import annotations

import logging

from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.worker.tasks.run_scheduled_reconciliation")
def run_scheduled_reconciliation(self) -> dict:
    """Run cross-plane reconciliation on a schedule."""
    try:
        from app.core.graph.store import ControlGraphStore
        from app.core.reconciliation.cross_plane_engine import (
            CrossPlaneReconciliationEngine,
        )

        graph = ControlGraphStore()
        engine = CrossPlaneReconciliationEngine(graph=graph)
        cases = engine.run_full_reconciliation()
        logger.info("Scheduled reconciliation: %d cases", len(cases))
        critical = [c for c in cases if c.severity.value == "critical"]
        if critical:
            alert_on_open_critical_cases.delay()
        return {
            "total_cases": len(cases),
            "critical": len(critical),
            "status": "complete",
        }
    except Exception as exc:
        logger.error("Reconciliation task failed: %s", exc)
        self.retry(countdown=60, max_retries=3, exc=exc)


@celery_app.task(bind=True, name="app.worker.tasks.run_retention_cleanup")
def run_retention_cleanup(self) -> dict:
    """Apply retention policy — soft-delete expired records."""
    try:
        from app.core.retention.policy import RetentionPolicyManager

        manager = RetentionPolicyManager()
        simulation = manager.run_cleanup_simulation()
        logger.info("Retention cleanup simulation: %s", simulation)
        return {"status": "complete", "processed": list(simulation.keys())}
    except Exception as exc:
        logger.error("Retention cleanup failed: %s", exc)
        raise


@celery_app.task(name="app.worker.tasks.alert_on_open_critical_cases")
def alert_on_open_critical_cases() -> dict:
    """Send alerts for any open CRITICAL cases."""
    try:
        import asyncio

        from app.core.alerting.service import AlertPayload, alert_service

        payload = AlertPayload(
            severity="critical",
            title="Open CRITICAL governance cases detected — immediate review required",
            case_id="scheduled-check",
            affected_planes=["operations"],
            remediation=[
                "Review open cases in the operator console",
                "http://localhost:3000/cases",
            ],
        )
        results = asyncio.run(alert_service.alert(payload))
        return {"alerts_sent": len(results), "results": results}
    except Exception as exc:
        logger.error("Alert task failed: %s", exc)
        return {"alerts_sent": 0, "error": str(exc)}


@celery_app.task(name="app.worker.tasks.report_usage_to_stripe")
def report_usage_to_stripe() -> dict:
    """Push hourly usage records to Stripe for all active tenants."""
    try:
        from app.core.billing.stripe_billing import stripe_billing

        records = stripe_billing.report_all_tenants()
        reported = sum(1 for r in records if r.stripe_reported)
        logger.info(
            "Stripe usage reporting: %d/%d tenants reported",
            reported,
            len(records),
        )
        return {
            "tenants_processed": len(records),
            "tenants_reported_to_stripe": reported,
        }
    except Exception as exc:
        logger.error("Stripe reporting task failed: %s", exc)
        return {"error": str(exc)}
