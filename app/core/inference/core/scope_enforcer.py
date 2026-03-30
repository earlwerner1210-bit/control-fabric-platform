"""
Control Fabric Platform — Bounded Inference Engine
Scope Enforcer: Mathematical Boundary on Model Data Access

Patent Claim (Dependent Claim 3.1): Scope parameters strictly limit
reasoning access to a predefined subgraph, preventing access to
unrelated operational planes.

Author: Control Fabric Platform
Date: March 2026
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.inference.models.domain_types import ScopeParameters

logger = logging.getLogger(__name__)


class ScopeViolationError(Exception):
    pass


class ScopeEnforcer:
    """
    Enforces mathematical boundary defined by ScopeParameters.
    The model ONLY receives the sanitised context produced by this class.
    """

    _ALWAYS_REDACTED_FIELDS = frozenset(
        [
            "personal_data",
            "credentials",
            "encryption_keys",
            "internal_api_keys",
            "raw_pii",
            "financial_account_numbers",
        ]
    )

    _CLASSIFICATION_HIERARCHY = {
        "public": 0,
        "internal": 1,
        "confidential": 2,
        "restricted": 3,
        "top_secret": 4,
    }

    def __init__(self, scope: ScopeParameters) -> None:
        self._scope = scope
        self._verify_scope_integrity()

    def _verify_scope_integrity(self) -> None:
        recomputed = ScopeParameters(
            allowed_control_object_ids=self._scope.allowed_control_object_ids,
            allowed_operational_planes=self._scope.allowed_operational_planes,
            max_graph_depth=self._scope.max_graph_depth,
            allowed_relationship_types=self._scope.allowed_relationship_types,
            data_classification_ceiling=self._scope.data_classification_ceiling,
        )
        if recomputed.scope_hash != self._scope.scope_hash:
            raise ScopeViolationError(
                "Scope hash mismatch — parameters may have been tampered with"
            )

    def enforce(self, raw_context: dict[str, Any]) -> dict[str, Any]:
        sanitised: dict[str, Any] = {}
        if "control_objects" in raw_context:
            sanitised["control_objects"] = self._filter_control_objects(
                raw_context["control_objects"]
            )
        if "relationships" in raw_context:
            sanitised["relationships"] = self._filter_relationships(raw_context["relationships"])
        if "graph_data" in raw_context:
            sanitised["graph_data"] = self._enforce_graph_depth(raw_context["graph_data"])
        if "plane_data" in raw_context:
            sanitised["plane_data"] = self._filter_planes(raw_context["plane_data"])
        sanitised = self._apply_classification_ceiling(sanitised)
        sanitised = self._strip_sensitive_fields(sanitised)
        sanitised["_scope_metadata"] = {
            "scope_hash": self._scope.scope_hash,
            "allowed_planes": self._scope.allowed_operational_planes,
            "max_depth": self._scope.max_graph_depth,
            "allowed_relationship_types": self._scope.allowed_relationship_types,
            "data_classification_ceiling": self._scope.data_classification_ceiling,
            "object_count": len(sanitised.get("control_objects", [])),
        }
        return sanitised

    def _filter_control_objects(self, objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        approved_ids = set(self._scope.allowed_control_object_ids)
        return [obj for obj in objects if isinstance(obj, dict) and obj.get("id") in approved_ids]

    def _filter_relationships(self, relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
        approved_ids = set(self._scope.allowed_control_object_ids)
        approved_types = set(self._scope.allowed_relationship_types)
        return [
            rel
            for rel in relationships
            if isinstance(rel, dict)
            and rel.get("type") in approved_types
            and rel.get("source_id") in approved_ids
            and rel.get("target_id") in approved_ids
        ]

    def _enforce_graph_depth(self, graph_data: dict[str, Any]) -> dict[str, Any]:
        max_depth = self._scope.max_graph_depth
        return {
            k: v for k, v in graph_data.items() if self._get_node_depth(k, graph_data) <= max_depth
        }

    def _filter_planes(self, plane_data: dict[str, Any]) -> dict[str, Any]:
        approved = set(self._scope.allowed_operational_planes)
        return {k: v for k, v in plane_data.items() if k in approved}

    def _apply_classification_ceiling(self, data: dict[str, Any]) -> dict[str, Any]:
        ceiling_level = self._CLASSIFICATION_HIERARCHY.get(
            self._scope.data_classification_ceiling, 1
        )

        def redact_if_above(obj: Any) -> Any:
            if isinstance(obj, list):
                return [redact_if_above(item) for item in obj]
            if not isinstance(obj, dict):
                return obj
            obj_level = self._CLASSIFICATION_HIERARCHY.get(obj.get("classification", "internal"), 1)
            if obj_level > ceiling_level:
                return {"_redacted": True, "reason": "above_classification_ceiling"}
            return {k: redact_if_above(v) for k, v in obj.items()}

        return {k: redact_if_above(v) for k, v in data.items()}

    def _strip_sensitive_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        def strip(obj: Any) -> Any:
            if isinstance(obj, list):
                return [strip(item) for item in obj]
            if not isinstance(obj, dict):
                return obj
            return {k: strip(v) for k, v in obj.items() if k not in self._ALWAYS_REDACTED_FIELDS}

        return strip(data)

    @staticmethod
    def _get_node_depth(key: str, graph_data: dict[str, Any]) -> int:
        if "level_" in key:
            try:
                return int(key.split("level_")[1].split("_")[0])
            except (ValueError, IndexError):
                pass
        return 1
