"""Graph policy engine — prevents invalid plane/type combinations."""

from __future__ import annotations

from app.core.control_link import ControlLink, ControlLinkCreate
from app.core.control_object import ControlObject
from app.core.errors import GraphPolicyViolation, InvalidLinkError
from app.core.registry import FabricRegistry
from app.core.types import ControlLinkType, PlaneType

FORBIDDEN_SELF_LINKS: set[ControlLinkType] = {
    ControlLinkType.CONTRADICTS,
    ControlLinkType.SUPERCEDES,
}


class GraphPolicyEngine:
    """Enforces structural policies on the control graph."""

    def __init__(self, registry: FabricRegistry | None = None) -> None:
        self._registry = registry

    def validate_link(
        self,
        create: ControlLinkCreate,
        source: ControlObject,
        target: ControlObject,
    ) -> list[str]:
        """Validate a proposed link. Returns list of violation messages (empty = valid)."""
        violations: list[str] = []

        if create.source_id == create.target_id:
            violations.append("Self-links are not permitted")
            return violations

        if create.link_type in FORBIDDEN_SELF_LINKS and source.plane == target.plane:
            if create.link_type == ControlLinkType.CONTRADICTS:
                pass  # contradictions within same plane are valid

        if create.link_type == ControlLinkType.SUPERCEDES:
            if source.object_type != target.object_type:
                violations.append(
                    f"SUPERCEDES link requires same object type: "
                    f"{source.object_type.value} != {target.object_type.value}"
                )
            if source.plane != target.plane:
                violations.append("SUPERCEDES link requires same plane")

        if create.link_type == ControlLinkType.BILLS_FOR:
            if source.plane != PlaneType.COMMERCIAL:
                violations.append("BILLS_FOR source must be in commercial plane")

        if create.link_type == ControlLinkType.FULFILLS:
            if target.plane == PlaneType.SERVICE and source.plane != PlaneType.FIELD:
                pass  # field fulfills service is valid
            # No strict restriction, but flag if reversed
            if source.plane == PlaneType.SERVICE and target.plane == PlaneType.FIELD:
                violations.append(
                    "FULFILLS direction: service should not fulfill field "
                    "(consider reversing source/target)"
                )

        if self._registry and source.object_kind and target.object_kind:
            policies = self._registry.get_link_policies(
                source_kind=source.object_kind,
                target_kind=target.object_kind,
            )
            for policy in policies:
                if create.link_type not in policy.allowed_link_types:
                    violations.append(
                        f"Link type {create.link_type.value} not allowed between "
                        f"{policy.source_kind} and {policy.target_kind}"
                    )
                if policy.required_same_plane and source.plane != target.plane:
                    violations.append(
                        f"Link between {policy.source_kind} and {policy.target_kind} "
                        f"requires same plane"
                    )
                if policy.required_cross_plane and source.plane == target.plane:
                    violations.append(
                        f"Link between {policy.source_kind} and {policy.target_kind} "
                        f"requires cross-plane"
                    )

        return violations

    def enforce_link(
        self,
        create: ControlLinkCreate,
        source: ControlObject,
        target: ControlObject,
    ) -> None:
        """Raise InvalidLinkError if policy is violated."""
        violations = self.validate_link(create, source, target)
        if violations:
            raise InvalidLinkError("; ".join(violations))
