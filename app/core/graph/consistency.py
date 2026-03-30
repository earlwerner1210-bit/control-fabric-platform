"""Graph consistency checker — detects structural issues in the control graph."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.core.control_link import ControlLink
from app.core.control_object import ControlObject
from app.core.types import ControlLinkType, ControlObjectId, ControlObjectType, PlaneType


class ConsistencyIssue(BaseModel):
    """A single consistency issue detected in the graph."""

    issue_type: str
    severity: str  # info, warning, error, critical
    object_id: ControlObjectId | None = None
    link_id: uuid.UUID | None = None
    description: str
    details: dict[str, Any] = Field(default_factory=dict)


class ConsistencyReport(BaseModel):
    """Full consistency report for a graph slice."""

    total_objects: int
    total_links: int
    issues: list[ConsistencyIssue] = Field(default_factory=list)
    is_consistent: bool = True

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity in ("error", "critical"))

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


class GraphConsistencyChecker:
    """Checks structural consistency of the control graph."""

    def check(
        self,
        objects: list[ControlObject],
        links: list[ControlLink],
    ) -> ConsistencyReport:
        issues: list[ConsistencyIssue] = []
        obj_ids = {o.id for o in objects}
        obj_map = {o.id: o for o in objects}

        # 1. Dangling links
        for link in links:
            if link.source_id not in obj_ids:
                issues.append(
                    ConsistencyIssue(
                        issue_type="dangling_link_source",
                        severity="error",
                        link_id=link.id,
                        description=f"Link source {link.source_id} not found in graph",
                    )
                )
            if link.target_id not in obj_ids:
                issues.append(
                    ConsistencyIssue(
                        issue_type="dangling_link_target",
                        severity="error",
                        link_id=link.id,
                        description=f"Link target {link.target_id} not found in graph",
                    )
                )

        # 2. Contradictory link sets
        contradictions: dict[frozenset[ControlObjectId], int] = {}
        for link in links:
            if link.link_type == ControlLinkType.CONTRADICTS:
                pair = frozenset([link.source_id, link.target_id])
                contradictions[pair] = contradictions.get(pair, 0) + 1
        for pair, count in contradictions.items():
            ids = list(pair)
            issues.append(
                ConsistencyIssue(
                    issue_type="contradiction_detected",
                    severity="warning",
                    description=(f"Contradiction between {ids[0]} and {ids[1]} ({count} link(s))"),
                    details={"object_ids": [str(i) for i in ids]},
                )
            )

        # 3. Missing expected links — billable events should have BILLS_FOR
        for obj in objects:
            if obj.object_type == ControlObjectType.BILLABLE_EVENT:
                has_bills_for = any(
                    l
                    for l in links
                    if l.source_id == obj.id and l.link_type == ControlLinkType.BILLS_FOR
                )
                if not has_bills_for:
                    issues.append(
                        ConsistencyIssue(
                            issue_type="missing_expected_link",
                            severity="warning",
                            object_id=obj.id,
                            description=(f"Billable event '{obj.label}' has no BILLS_FOR link"),
                        )
                    )

        # 4. Orphaned objects — no links at all
        linked_ids: set[ControlObjectId] = set()
        for link in links:
            linked_ids.add(link.source_id)
            linked_ids.add(link.target_id)
        for obj in objects:
            if obj.id not in linked_ids:
                issues.append(
                    ConsistencyIssue(
                        issue_type="orphaned_object",
                        severity="info",
                        object_id=obj.id,
                        description=f"Object '{obj.label}' has no links",
                    )
                )

        # 5. Superseded objects still active in links
        for obj in objects:
            if obj.state.value == "superseded":
                incoming = [
                    l
                    for l in links
                    if l.target_id == obj.id and l.link_type != ControlLinkType.SUPERCEDES
                ]
                for link in incoming:
                    src = obj_map.get(link.source_id)
                    if src and src.state.value == "active":
                        issues.append(
                            ConsistencyIssue(
                                issue_type="stale_reference",
                                severity="warning",
                                object_id=obj.id,
                                link_id=link.id,
                                description=(
                                    f"Active object '{src.label}' references "
                                    f"superseded '{obj.label}'"
                                ),
                            )
                        )

        # 6. Plane coverage gaps
        planes_present = {o.plane for o in objects}
        if len(planes_present) > 1:
            for plane in PlaneType:
                plane_objects = [o for o in objects if o.plane == plane]
                if plane_objects:
                    cross_links = [
                        l
                        for l in links
                        if (l.source_plane == plane and l.target_plane != plane)
                        or (l.target_plane == plane and l.source_plane != plane)
                    ]
                    if not cross_links and len(planes_present) > 1:
                        issues.append(
                            ConsistencyIssue(
                                issue_type="isolated_plane",
                                severity="info",
                                description=(
                                    f"Plane '{plane.value}' has {len(plane_objects)} objects "
                                    f"but no cross-plane links"
                                ),
                            )
                        )

        is_consistent = all(i.severity not in ("error", "critical") for i in issues)

        return ConsistencyReport(
            total_objects=len(objects),
            total_links=len(links),
            issues=issues,
            is_consistent=is_consistent,
        )
