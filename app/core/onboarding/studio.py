"""Onboarding Modelling Studio — session-based guided journey."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from .domain_types import (
    ONBOARDING_STEPS,
    OnboardingSession,
    OnboardingStep,
    StepOutcome,
    StepStatus,
)

logger = logging.getLogger(__name__)

_STEP_DEFINITIONS: list[OnboardingStep] = [
    OnboardingStep(
        name="domain_discovery",
        order=0,
        description="Identify domain entities, relationships, and data sources",
    ),
    OnboardingStep(
        name="schema_mapping",
        order=1,
        description="Map source schemas to control-fabric canonical types",
    ),
    OnboardingStep(
        name="rule_authoring",
        order=2,
        description="Author reconciliation rules for the domain",
    ),
    OnboardingStep(
        name="evidence_binding",
        order=3,
        description="Bind evidence sources to rule assertions",
    ),
    OnboardingStep(
        name="pack_assembly",
        order=4,
        description="Assemble domain pack with schemas, rules, and prompts",
    ),
    OnboardingStep(
        name="validation_dry_run",
        order=5,
        description="Run validation dry-run against sample data",
    ),
    OnboardingStep(
        name="activation",
        order=6,
        description="Activate domain pack in target environment",
        required=True,
    ),
]


class OnboardingStudio:
    """Manages onboarding sessions with progress tracking."""

    def __init__(self) -> None:
        self._sessions: dict[str, OnboardingSession] = {}

    # ── session lifecycle ───────────────────────────────────

    def create_session(self, domain_name: str, created_by: str) -> OnboardingSession:
        session = OnboardingSession(domain_name=domain_name, created_by=created_by)
        session.steps = [
            StepOutcome(step_name=name, status=StepStatus.PENDING) for name in ONBOARDING_STEPS
        ]
        self._sessions[session.session_id] = session
        logger.info(
            "Created onboarding session %s for domain '%s'", session.session_id, domain_name
        )
        return session

    def get_session(self, session_id: str) -> OnboardingSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[OnboardingSession]:
        return list(self._sessions.values())

    # ── step progression ────────────────────────────────────

    def advance_step(
        self,
        session_id: str,
        artifacts: dict[str, str] | None = None,
    ) -> StepOutcome:
        session = self._sessions[session_id]
        if session.completed:
            raise ValueError(f"Session {session_id} is already completed")

        idx = session.current_step
        if idx >= len(ONBOARDING_STEPS):
            raise ValueError("All steps already completed")

        outcome = StepOutcome(
            step_name=ONBOARDING_STEPS[idx],
            status=StepStatus.COMPLETED,
            artifacts=artifacts or {},
            completed_at=datetime.now(UTC),
        )
        session.steps[idx] = outcome
        session.current_step = idx + 1

        if session.current_step >= len(ONBOARDING_STEPS):
            session.completed = True
            logger.info("Session %s completed all steps", session_id)

        return outcome

    def skip_step(self, session_id: str, reason: str = "") -> StepOutcome:
        session = self._sessions[session_id]
        idx = session.current_step
        step_def = _STEP_DEFINITIONS[idx]

        if step_def.required:
            raise ValueError(f"Step '{step_def.name}' is required and cannot be skipped")

        outcome = StepOutcome(
            step_name=ONBOARDING_STEPS[idx],
            status=StepStatus.SKIPPED,
            artifacts={"skip_reason": reason} if reason else {},
            completed_at=datetime.now(UTC),
        )
        session.steps[idx] = outcome
        session.current_step = idx + 1
        return outcome

    def fail_step(self, session_id: str, error: str) -> StepOutcome:
        session = self._sessions[session_id]
        idx = session.current_step
        outcome = StepOutcome(
            step_name=ONBOARDING_STEPS[idx],
            status=StepStatus.FAILED,
            error=error,
            completed_at=datetime.now(UTC),
        )
        session.steps[idx] = outcome
        return outcome

    # ── queries ─────────────────────────────────────────────

    def get_progress(self, session_id: str) -> dict[str, object]:
        session = self._sessions[session_id]
        completed = sum(1 for s in session.steps if s.status == StepStatus.COMPLETED)
        return {
            "session_id": session_id,
            "domain_name": session.domain_name,
            "total_steps": len(ONBOARDING_STEPS),
            "completed_steps": completed,
            "current_step": ONBOARDING_STEPS[session.current_step]
            if session.current_step < len(ONBOARDING_STEPS)
            else "done",
            "percent_complete": round(completed / len(ONBOARDING_STEPS) * 100, 1),
            "is_complete": session.completed,
        }

    def get_step_definitions(self) -> list[OnboardingStep]:
        return list(_STEP_DEFINITIONS)
