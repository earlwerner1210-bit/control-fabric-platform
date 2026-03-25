"""Standalone readiness rule engine for testing -- no domain-pack schema dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReadinessCheckResult:
    """Result of a single readiness check."""
    rule_name: str
    passed: bool
    message: str
    severity: str = "info"


@dataclass
class ReadinessResult:
    """Overall readiness evaluation result."""
    ready: bool
    verdict: str
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: list[ReadinessCheckResult] = field(default_factory=list)
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)


class ReadinessRuleEngine:
    """Evaluates work order readiness for field dispatch using plain dicts."""

    def evaluate(self, work_order: dict[str, Any]) -> ReadinessResult:
        checks: list[ReadinessCheckResult] = []
        blockers: list[str] = []
        warnings: list[str] = []

        for check_fn in [
            self._check_skills,
            self._check_certifications,
            self._check_permits,
            self._check_materials,
            self._check_schedule,
        ]:
            result = check_fn(work_order)
            checks.append(result)
            if not result.passed:
                if result.severity == "blocking":
                    blockers.append(result.message)
                else:
                    warnings.append(result.message)

        required_skills = set(work_order.get("required_skills", []))
        engineer = work_order.get("engineer", {})
        engineer_skills = set(engineer.get("skills", []))
        matched_skills = sorted(required_skills & engineer_skills)
        missing_skills = sorted(required_skills - engineer_skills)

        if blockers:
            verdict = "blocked"
            ready = False
        elif warnings:
            verdict = "warn"
            ready = True
        else:
            verdict = "ready"
            ready = True

        return ReadinessResult(
            ready=ready, verdict=verdict, blockers=blockers, warnings=warnings,
            checks=checks, matched_skills=matched_skills, missing_skills=missing_skills,
        )

    def _check_skills(self, wo: dict[str, Any]) -> ReadinessCheckResult:
        required = set(wo.get("required_skills", []))
        if not required:
            return ReadinessCheckResult("skills_check", True, "No specific skills required")
        engineer = wo.get("engineer", {})
        if not engineer:
            return ReadinessCheckResult("skills_check", False, "No engineer assigned", "blocking")
        eng_skills = set(engineer.get("skills", []))
        missing = required - eng_skills
        if missing:
            return ReadinessCheckResult("skills_check", False,
                f"Engineer missing required skills: {', '.join(sorted(missing))}", "blocking")
        return ReadinessCheckResult("skills_check", True, "Engineer has all required skills")

    def _check_certifications(self, wo: dict[str, Any]) -> ReadinessCheckResult:
        required_certs = set(wo.get("required_certifications", []))
        if not required_certs:
            return ReadinessCheckResult("certifications_check", True, "No certifications required")
        engineer = wo.get("engineer", {})
        certs = engineer.get("certifications", [])
        cert_types = {c.get("type") for c in certs}
        missing = required_certs - cert_types
        if missing:
            return ReadinessCheckResult("certifications_check", False,
                f"Engineer missing certifications: {', '.join(sorted(missing))}", "blocking")
        from datetime import date as dt
        today = dt.today().isoformat()
        for cert in certs:
            if cert.get("type") in required_certs:
                expiry = cert.get("expiry", "")
                if expiry and expiry < today:
                    return ReadinessCheckResult("certifications_check", False,
                        f"Certification '{cert['type']}' expired on {expiry}", "blocking")
        return ReadinessCheckResult("certifications_check", True, "All certifications valid")

    def _check_permits(self, wo: dict[str, Any]) -> ReadinessCheckResult:
        permits = wo.get("required_permits", [])
        if not permits:
            return ReadinessCheckResult("permits_check", True, "No permits required")
        pending = [p for p in permits if p.get("status") != "approved"]
        if pending:
            types = [p.get("type", "unknown") for p in pending]
            return ReadinessCheckResult("permits_check", False,
                f"Permits not approved: {', '.join(types)}", "blocking")
        return ReadinessCheckResult("permits_check", True, "All permits approved")

    def _check_materials(self, wo: dict[str, Any]) -> ReadinessCheckResult:
        materials = wo.get("materials", [])
        if not materials:
            return ReadinessCheckResult("materials_check", True, "No materials specified")
        unavailable = [m for m in materials if m.get("status") not in ("in_stock", "delivered", "available")]
        if unavailable:
            items = [m.get("item", "unknown") for m in unavailable]
            return ReadinessCheckResult("materials_check", False,
                f"Materials not available: {', '.join(items)}", "warning")
        return ReadinessCheckResult("materials_check", True, "All materials available")

    def _check_schedule(self, wo: dict[str, Any]) -> ReadinessCheckResult:
        schedule = wo.get("schedule", {})
        if not schedule:
            return ReadinessCheckResult("schedule_check", False, "No schedule defined", "blocking")
        if not schedule.get("scheduled_date"):
            return ReadinessCheckResult("schedule_check", False, "No scheduled date defined", "blocking")
        return ReadinessCheckResult("schedule_check", True, "Schedule is valid")
