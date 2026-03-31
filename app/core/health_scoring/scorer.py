"""
Customer Health Scoring

Produces a 0-100 health score per tenant based on:
  - Active user engagement (20 pts)
  - Case resolution rate (25 pts)
  - Evidence completeness (20 pts)
  - Override / exception frequency (15 pts)
  - Platform usage depth (20 pts)

A score below 60 triggers a CSM alert.
A score below 40 indicates churn risk.

Used by:
  - GET /health-scores/{tenant_id}
  - GET /health-scores/all (CSM dashboard)
  - Celery task: daily health score recalculation
  - Alert when score drops more than 15 points in 7 days
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


@dataclass
class HealthScoreComponent:
    name: str
    score: float  # 0-max_points
    max_points: float
    detail: str
    status: str  # healthy / warning / critical


@dataclass
class TenantHealthScore:
    tenant_id: str
    overall_score: float  # 0-100
    grade: str  # A / B / C / D / F
    risk_level: str  # healthy / at_risk / churn_risk
    components: list[HealthScoreComponent]
    recommendations: list[str]
    calculated_at: str
    previous_score: float | None = None
    score_delta_7d: float | None = None

    @property
    def trend(self) -> str:
        if self.score_delta_7d is None:
            return "unknown"
        if self.score_delta_7d > 5:
            return "improving"
        if self.score_delta_7d < -5:
            return "declining"
        return "stable"


class CustomerHealthScorer:
    """
    Calculates health scores for pilot and production tenants.
    All data is pulled from existing platform telemetry —
    no additional instrumentation required.
    """

    GRADE_THRESHOLDS = [(90, "A"), (75, "B"), (60, "C"), (40, "D"), (0, "F")]
    RISK_THRESHOLDS = [(70, "healthy"), (50, "at_risk"), (0, "churn_risk")]

    def __init__(self) -> None:
        self._history: dict[str, list[dict]] = {}

    def score_tenant(self, tenant_id: str) -> TenantHealthScore:
        """Calculate health score for a tenant using live platform data."""
        components = []
        total = 0.0

        # Component 1: Active user engagement (20 pts)
        user_score = self._score_user_engagement(tenant_id)
        components.append(user_score)
        total += user_score.score

        # Component 2: Case resolution rate (25 pts)
        case_score = self._score_case_resolution(tenant_id)
        components.append(case_score)
        total += case_score.score

        # Component 3: Evidence completeness (20 pts)
        evidence_score = self._score_evidence_completeness(tenant_id)
        components.append(evidence_score)
        total += evidence_score.score

        # Component 4: Override frequency (15 pts)
        override_score = self._score_override_frequency(tenant_id)
        components.append(override_score)
        total += override_score.score

        # Component 5: Platform usage depth (20 pts)
        usage_score = self._score_usage_depth(tenant_id)
        components.append(usage_score)
        total += usage_score.score

        grade = next(g for threshold, g in self.GRADE_THRESHOLDS if total >= threshold)
        risk = next(r for threshold, r in self.RISK_THRESHOLDS if total >= threshold)
        recommendations = self._generate_recommendations(components, total)

        # Track history
        history = self._history.setdefault(tenant_id, [])
        prev_score = history[-1]["score"] if history else None
        prev_7d = history[-7]["score"] if len(history) >= 7 else None
        history.append({"score": total, "at": datetime.now(UTC).isoformat()})
        if len(history) > 90:
            history.pop(0)

        return TenantHealthScore(
            tenant_id=tenant_id,
            overall_score=round(total, 1),
            grade=grade,
            risk_level=risk,
            components=components,
            recommendations=recommendations,
            calculated_at=datetime.now(UTC).isoformat(),
            previous_score=prev_score,
            score_delta_7d=round(total - prev_7d, 1) if prev_7d else None,
        )

    def score_all_tenants(self) -> list[TenantHealthScore]:
        """Score all known tenants."""
        try:
            from app.core.metering.meter import metering_engine

            tenants = metering_engine.get_all_tenants()
        except Exception:
            tenants = ["default"]
        if not tenants:
            tenants = ["default"]
        return [self.score_tenant(tid) for tid in tenants]

    def get_at_risk_tenants(self) -> list[TenantHealthScore]:
        return [s for s in self.score_all_tenants() if s.risk_level != "healthy"]

    def _score_user_engagement(self, tenant_id: str) -> HealthScoreComponent:
        """Score based on metered platform usage activity."""
        try:
            from app.core.metering.meter import metering_engine

            usage = metering_engine.get_usage(tenant_id)
            total_actions = sum(usage.values())
            gate_subs = usage.get("gate_submission", 0)
            recon_runs = usage.get("reconciliation_run", 0)
            if gate_subs >= 20 or recon_runs >= 5:
                score = 20.0
                detail = (
                    f"High engagement: {gate_subs} gate submissions,"
                    f" {recon_runs} reconciliation runs"
                )
            elif gate_subs >= 5 or recon_runs >= 2:
                score = 14.0
                detail = f"Moderate engagement: {gate_subs} submissions, {recon_runs} runs"
            elif total_actions > 0:
                score = 8.0
                detail = f"Low engagement: {total_actions} total platform actions"
            else:
                score = 3.0
                detail = "No platform activity recorded yet"
            status = "healthy" if score >= 14 else "warning" if score >= 8 else "critical"
        except Exception:
            score, detail, status = (
                10.0,
                "Usage data unavailable — assuming baseline",
                "warning",
            )
        return HealthScoreComponent("User engagement", score, 20.0, detail, status)

    def _score_case_resolution(self, tenant_id: str) -> HealthScoreComponent:
        """Score based on governance case handling."""
        try:
            from app.core.graph.store import ControlGraphStore
            from app.core.reconciliation.cross_plane_engine import (
                CrossPlaneReconciliationEngine,
            )

            graph = ControlGraphStore()
            engine = CrossPlaneReconciliationEngine(graph=graph)
            open_cases = engine.get_open_cases()
            critical_open = [c for c in open_cases if c.severity.value == "critical"]
            if not open_cases:
                score = 25.0
                detail = "No open cases — all governance issues resolved"
            elif not critical_open and len(open_cases) < 5:
                score = 20.0
                detail = f"{len(open_cases)} open cases, none critical — actively managed"
            elif not critical_open:
                score = 15.0
                detail = f"{len(open_cases)} open cases — no critical issues, review backlog"
            elif len(critical_open) <= 2:
                score = 10.0
                detail = f"{len(critical_open)} critical cases open — needs immediate attention"
            else:
                score = 4.0
                detail = f"{len(critical_open)} critical cases open — governance posture at risk"
            status = "healthy" if score >= 20 else "warning" if score >= 12 else "critical"
        except Exception:
            score, detail, status = (
                15.0,
                "Case data unavailable — baseline score applied",
                "warning",
            )
        return HealthScoreComponent("Case resolution", score, 25.0, detail, status)

    def _score_evidence_completeness(self, tenant_id: str) -> HealthScoreComponent:
        """Score based on evidence chain completeness."""
        try:
            from app.core.platform_action_release_gate import PlatformActionReleaseGate

            gate = PlatformActionReleaseGate()
            total = gate.total_submitted
            dispatched = gate.total_dispatched
            if total == 0:
                score = 10.0
                detail = "No gate submissions yet — platform not yet in active use"
                status = "warning"
            else:
                pass_rate = dispatched / total
                if pass_rate >= 0.85:
                    score = 20.0
                    detail = (
                        f"{round(pass_rate * 100)}% of submissions have complete evidence chains"
                    )
                    status = "healthy"
                elif pass_rate >= 0.65:
                    score = 14.0
                    detail = f"{round(pass_rate * 100)}% pass rate — review evidence requirements"
                    status = "warning"
                else:
                    score = 7.0
                    detail = (
                        f"Only {round(pass_rate * 100)}% pass rate"
                        " — evidence model may be misconfigured"
                    )
                    status = "critical"
        except Exception:
            score, detail, status = (
                12.0,
                "Evidence data unavailable — baseline applied",
                "warning",
            )
        return HealthScoreComponent("Evidence completeness", score, 20.0, detail, status)

    def _score_override_frequency(self, tenant_id: str) -> HealthScoreComponent:
        """Score based on exception/override rate — lower is better."""
        try:
            from app.core.exception_framework.manager import ExceptionManager

            mgr = ExceptionManager()
            total = mgr.total_requests

            from app.core.metering.meter import metering_engine

            gate_subs = metering_engine.get_usage(tenant_id).get("gate_submission", 1)
            override_rate = total / max(gate_subs, 1)
            if override_rate < 0.02:
                score = 15.0
                detail = (
                    f"Excellent: override rate {round(override_rate * 100, 1)}%"
                    " — policies well-calibrated"
                )
                status = "healthy"
            elif override_rate < 0.05:
                score = 11.0
                detail = (
                    f"Good: override rate {round(override_rate * 100, 1)}% — minor tuning may help"
                )
                status = "healthy"
            elif override_rate < 0.10:
                score = 7.0
                detail = (
                    f"Elevated: override rate {round(override_rate * 100, 1)}%"
                    " — review policy strictness"
                )
                status = "warning"
            else:
                score = 3.0
                detail = (
                    f"High override rate {round(override_rate * 100, 1)}%"
                    " — policies may be too restrictive"
                )
                status = "critical"
        except Exception:
            score, detail, status = (
                10.0,
                "Override data unavailable — baseline applied",
                "warning",
            )
        return HealthScoreComponent("Override frequency", score, 15.0, detail, status)

    def _score_usage_depth(self, tenant_id: str) -> HealthScoreComponent:
        """Score based on breadth of platform features used."""
        try:
            from app.core.metering.meter import metering_engine

            usage = metering_engine.get_usage(tenant_id)
            features_used = sum(1 for et, count in usage.items() if count > 0)
            if features_used >= 7:
                score = 20.0
                detail = f"{features_used}/10 platform capabilities in active use — deep adoption"
                status = "healthy"
            elif features_used >= 4:
                score = 14.0
                detail = f"{features_used}/10 capabilities used — good initial adoption"
                status = "healthy"
            elif features_used >= 2:
                score = 8.0
                detail = f"{features_used}/10 capabilities used — room to expand usage"
                status = "warning"
            else:
                score = 3.0
                detail = "Minimal platform features in use — onboarding may need support"
                status = "critical"
        except Exception:
            score, detail, status = (
                10.0,
                "Usage depth unavailable — baseline applied",
                "warning",
            )
        return HealthScoreComponent("Usage depth", score, 20.0, detail, status)

    def _generate_recommendations(
        self, components: list[HealthScoreComponent], total: float
    ) -> list[str]:
        recs = []
        for c in components:
            if c.status == "critical":
                if c.name == "Case resolution":
                    recs.append(
                        "Assign owners to all open CRITICAL cases immediately"
                        " — use the Case Queue bulk assign feature"
                    )
                elif c.name == "Evidence completeness":
                    recs.append(
                        "Review evidence requirements"
                        " — POST /defaults/apply to reset to platform defaults"
                    )
                elif c.name == "User engagement":
                    recs.append(
                        "Schedule a platform walkthrough with the team"
                        " — share the 9-step journey guide"
                    )
                elif c.name == "Override frequency":
                    recs.append(
                        "Review and relax overly restrictive policies"
                        " — use POST /policies/{id}/simulate before"
                        " publishing changes"
                    )
                elif c.name == "Usage depth":
                    recs.append(
                        "Expand to additional platform capabilities — install a second domain pack"
                    )
        if total < 60:
            recs.append(
                "Consider scheduling a CSM call to review platform configuration and usage patterns"
            )
        if not recs:
            recs.append(
                "Platform health is good — focus on expanding governance"
                " coverage to additional teams or environments"
            )
        return recs


# Singleton
health_scorer = CustomerHealthScorer()
