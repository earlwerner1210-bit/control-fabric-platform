"""Dashboard aggregation service — pre-computed summaries for the SMB dashboard."""

from __future__ import annotations

from datetime import UTC, datetime

from app.products.release_guard.domain.enums import ReleaseStatus
from app.products.release_guard.domain.models import DashboardSummary


class DashboardService:
    def get_summary(
        self,
        workspace_id: str,
        period_days: int = 30,
    ) -> DashboardSummary:
        from app.products.release_guard.services.release_request_service import (
            release_request_service,
        )

        releases = release_request_service.list_for_workspace(workspace_id, limit=1000)

        now = datetime.now(UTC)

        # Filter to period
        def in_period(r):
            try:
                created = datetime.fromisoformat(r.created_at.replace("Z", "+00:00"))
                return (now - created).days <= period_days
            except Exception:
                return True

        period_releases = [r for r in releases if in_period(r)]

        approved = [r for r in period_releases if r.status == ReleaseStatus.APPROVED]
        blocked = [r for r in period_releases if r.status == ReleaseStatus.BLOCKED]
        pending = [r for r in period_releases if r.status == ReleaseStatus.PENDING]

        # Top block reasons
        block_reasons: dict[str, int] = {}
        for r in blocked:
            for check in r.blocked_checks:
                block_reasons[check] = block_reasons.get(check, 0) + 1
        top_reasons = sorted(
            [{"reason": k.replace("_", " ").title(), "count": v} for k, v in block_reasons.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]

        # Average time to decision
        decision_times = []
        for r in [*approved, *blocked]:
            if r.submitted_at and r.decided_at:
                try:
                    submitted = datetime.fromisoformat(r.submitted_at.replace("Z", "+00:00"))
                    decided = datetime.fromisoformat(r.decided_at.replace("Z", "+00:00"))
                    decision_times.append((decided - submitted).total_seconds() / 3600)
                except Exception:
                    pass
        avg_hours = round(sum(decision_times) / len(decision_times), 1) if decision_times else 0.0

        # Recent releases
        recent = [
            {
                "release_id": r.release_id,
                "title": r.title,
                "service_name": r.service_name,
                "status": r.status.value,
                "risk_level": r.risk_level.value,
                "created_at": r.created_at,
            }
            for r in period_releases[:10]
        ]

        # Audit readiness grade
        total = len(period_releases)
        if total == 0:
            grade = "N/A"
        else:
            governed_rate = len(approved) / total
            grade = "A" if governed_rate >= 0.9 else "B" if governed_rate >= 0.75 else "C"

        # Pending approvals
        from app.products.release_guard.services.approval_service import _steps as approval_steps

        all_pending = [s for s in approval_steps.values() if s.status.value == "pending"]
        workspace_pending = [
            s for s in all_pending if any(r.release_id == s.release_id for r in period_releases)
        ]

        return DashboardSummary(
            workspace_id=workspace_id,
            period_days=period_days,
            total_releases=len(period_releases),
            approved=len(approved),
            blocked=len(blocked),
            pending_approval=len(pending),
            approval_rate_pct=round(len(approved) / max(total, 1) * 100, 1),
            avg_time_to_decision_hours=avg_hours,
            top_block_reasons=top_reasons,
            recent_releases=recent,
            audit_readiness_grade=grade,
            pending_approvals=len(workspace_pending),
        )


dashboard_service = DashboardService()
