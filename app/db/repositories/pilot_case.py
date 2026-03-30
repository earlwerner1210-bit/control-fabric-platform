"""Repository for pilot case database operations."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.pilot import (
    ApprovalDecision,
    BaselineComparison,
    CaseExport,
    CaseStateTransition,
    EvidenceBundle,
    FeedbackEntry,
    KpiMeasurement,
    OverrideDecision,
    PilotCase,
    PilotCaseArtifact,
    PilotCaseAssignment,
    ReviewDecision,
    ReviewerNote,
)


class PilotCaseRepository:
    """Database repository for pilot case operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Pilot Case CRUD ────────────────────────────────────────────────

    async def create_case(self, **kwargs: Any) -> PilotCase:
        case = PilotCase(id=uuid.uuid4(), **kwargs)
        self.db.add(case)
        await self.db.flush()
        return case

    async def get_case(self, case_id: uuid.UUID) -> PilotCase | None:
        result = await self.db.execute(select(PilotCase).where(PilotCase.id == case_id))
        return result.scalar_one_or_none()

    async def list_cases(
        self,
        tenant_id: uuid.UUID,
        state: str | None = None,
        workflow_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PilotCase], int]:
        stmt = select(PilotCase).where(PilotCase.tenant_id == tenant_id)

        if state:
            stmt = stmt.where(PilotCase.state == state)
        if workflow_type:
            stmt = stmt.where(PilotCase.workflow_type == workflow_type)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = (
            stmt.order_by(PilotCase.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def update_case_state(self, case_id: uuid.UUID, new_state: str) -> PilotCase | None:
        case = await self.get_case(case_id)
        if case:
            case.state = new_state
            await self.db.flush()
        return case

    # ── Artifacts ──────────────────────────────────────────────────────

    async def add_artifact(self, **kwargs: Any) -> PilotCaseArtifact:
        artifact = PilotCaseArtifact(id=uuid.uuid4(), **kwargs)
        self.db.add(artifact)
        await self.db.flush()
        return artifact

    async def get_artifacts(self, pilot_case_id: uuid.UUID) -> list[PilotCaseArtifact]:
        result = await self.db.execute(
            select(PilotCaseArtifact)
            .where(PilotCaseArtifact.pilot_case_id == pilot_case_id)
            .order_by(PilotCaseArtifact.created_at.asc())
        )
        return list(result.scalars().all())

    # ── Assignments ────────────────────────────────────────────────────

    async def assign_reviewer(self, **kwargs: Any) -> PilotCaseAssignment:
        assignment = PilotCaseAssignment(id=uuid.uuid4(), **kwargs)
        self.db.add(assignment)
        await self.db.flush()
        return assignment

    async def get_assignments(self, pilot_case_id: uuid.UUID) -> list[PilotCaseAssignment]:
        result = await self.db.execute(
            select(PilotCaseAssignment)
            .where(PilotCaseAssignment.pilot_case_id == pilot_case_id)
            .order_by(PilotCaseAssignment.assigned_at.desc())
        )
        return list(result.scalars().all())

    # ── State Transitions ──────────────────────────────────────────────

    async def record_transition(self, **kwargs: Any) -> CaseStateTransition:
        transition = CaseStateTransition(id=uuid.uuid4(), **kwargs)
        self.db.add(transition)
        await self.db.flush()
        return transition

    async def get_transitions(self, pilot_case_id: uuid.UUID) -> list[CaseStateTransition]:
        result = await self.db.execute(
            select(CaseStateTransition)
            .where(CaseStateTransition.pilot_case_id == pilot_case_id)
            .order_by(CaseStateTransition.transitioned_at.asc())
        )
        return list(result.scalars().all())

    # ── Review Decisions ───────────────────────────────────────────────

    async def add_review_decision(self, **kwargs: Any) -> ReviewDecision:
        decision = ReviewDecision(id=uuid.uuid4(), **kwargs)
        self.db.add(decision)
        await self.db.flush()
        return decision

    async def get_review_decisions(self, pilot_case_id: uuid.UUID) -> list[ReviewDecision]:
        result = await self.db.execute(
            select(ReviewDecision)
            .where(ReviewDecision.pilot_case_id == pilot_case_id)
            .order_by(ReviewDecision.created_at.asc())
        )
        return list(result.scalars().all())

    # ── Reviewer Notes ─────────────────────────────────────────────────

    async def add_reviewer_note(self, **kwargs: Any) -> ReviewerNote:
        note = ReviewerNote(id=uuid.uuid4(), **kwargs)
        self.db.add(note)
        await self.db.flush()
        return note

    async def get_reviewer_notes(self, pilot_case_id: uuid.UUID) -> list[ReviewerNote]:
        result = await self.db.execute(
            select(ReviewerNote)
            .where(ReviewerNote.pilot_case_id == pilot_case_id)
            .order_by(ReviewerNote.created_at.asc())
        )
        return list(result.scalars().all())

    # ── Approval / Override ────────────────────────────────────────────

    async def add_approval(self, **kwargs: Any) -> ApprovalDecision:
        approval = ApprovalDecision(id=uuid.uuid4(), **kwargs)
        self.db.add(approval)
        await self.db.flush()
        return approval

    async def get_approvals(self, pilot_case_id: uuid.UUID) -> list[ApprovalDecision]:
        result = await self.db.execute(
            select(ApprovalDecision)
            .where(ApprovalDecision.pilot_case_id == pilot_case_id)
            .order_by(ApprovalDecision.created_at.asc())
        )
        return list(result.scalars().all())

    async def add_override(self, **kwargs: Any) -> OverrideDecision:
        override = OverrideDecision(id=uuid.uuid4(), **kwargs)
        self.db.add(override)
        await self.db.flush()
        return override

    async def get_overrides(self, pilot_case_id: uuid.UUID) -> list[OverrideDecision]:
        result = await self.db.execute(
            select(OverrideDecision)
            .where(OverrideDecision.pilot_case_id == pilot_case_id)
            .order_by(OverrideDecision.created_at.asc())
        )
        return list(result.scalars().all())

    # ── Evidence ───────────────────────────────────────────────────────

    async def create_evidence_bundle(self, **kwargs: Any) -> EvidenceBundle:
        bundle = EvidenceBundle(id=uuid.uuid4(), **kwargs)
        self.db.add(bundle)
        await self.db.flush()
        return bundle

    async def get_evidence_bundle(self, pilot_case_id: uuid.UUID) -> EvidenceBundle | None:
        result = await self.db.execute(
            select(EvidenceBundle)
            .where(EvidenceBundle.pilot_case_id == pilot_case_id)
            .order_by(EvidenceBundle.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ── Baseline ───────────────────────────────────────────────────────

    async def create_baseline(self, **kwargs: Any) -> BaselineComparison:
        baseline = BaselineComparison(id=uuid.uuid4(), **kwargs)
        self.db.add(baseline)
        await self.db.flush()
        return baseline

    async def get_baseline(self, pilot_case_id: uuid.UUID) -> BaselineComparison | None:
        result = await self.db.execute(
            select(BaselineComparison)
            .where(BaselineComparison.pilot_case_id == pilot_case_id)
            .order_by(BaselineComparison.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_baselines(
        self,
        match_type: str | None = None,
        limit: int = 100,
    ) -> list[BaselineComparison]:
        stmt = select(BaselineComparison)
        if match_type:
            stmt = stmt.where(BaselineComparison.match_type == match_type)
        stmt = stmt.order_by(BaselineComparison.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── KPI ────────────────────────────────────────────────────────────

    async def record_kpi(self, **kwargs: Any) -> KpiMeasurement:
        kpi = KpiMeasurement(id=uuid.uuid4(), **kwargs)
        self.db.add(kpi)
        await self.db.flush()
        return kpi

    async def get_kpis(self, pilot_case_id: uuid.UUID) -> list[KpiMeasurement]:
        result = await self.db.execute(
            select(KpiMeasurement)
            .where(KpiMeasurement.pilot_case_id == pilot_case_id)
            .order_by(KpiMeasurement.created_at.asc())
        )
        return list(result.scalars().all())

    # ── Feedback ───────────────────────────────────────────────────────

    async def add_feedback(self, **kwargs: Any) -> FeedbackEntry:
        entry = FeedbackEntry(id=uuid.uuid4(), **kwargs)
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def get_feedback(self, pilot_case_id: uuid.UUID) -> list[FeedbackEntry]:
        result = await self.db.execute(
            select(FeedbackEntry)
            .where(FeedbackEntry.pilot_case_id == pilot_case_id)
            .order_by(FeedbackEntry.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_feedback_summary(
        self,
        tenant_id: uuid.UUID | None = None,
    ) -> dict[str, int]:
        stmt = select(
            FeedbackEntry.category,
            func.count(FeedbackEntry.id),
        ).group_by(FeedbackEntry.category)
        result = await self.db.execute(stmt)
        return dict(result.all())

    # ── Exports ────────────────────────────────────────────────────────

    async def create_export(self, **kwargs: Any) -> CaseExport:
        export = CaseExport(id=uuid.uuid4(), **kwargs)
        self.db.add(export)
        await self.db.flush()
        return export

    async def get_exports(self, pilot_case_id: uuid.UUID) -> list[CaseExport]:
        result = await self.db.execute(
            select(CaseExport)
            .where(CaseExport.pilot_case_id == pilot_case_id)
            .order_by(CaseExport.created_at.desc())
        )
        return list(result.scalars().all())
