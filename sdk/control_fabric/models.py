"""SDK domain models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Case:
    case_id: str
    case_type: str
    severity: str
    status: str
    title: str
    affected_planes: list[str]
    detected_at: str

    @classmethod
    def from_dict(cls, d: dict) -> Case:
        return cls(
            **{
                k: d[k]
                for k in [
                    "case_id",
                    "case_type",
                    "severity",
                    "status",
                    "title",
                    "affected_planes",
                    "detected_at",
                ]
                if k in d
            }
        )


@dataclass
class ControlObject:
    object_id: str
    object_type: str
    name: str
    state: str
    operational_plane: str

    @classmethod
    def from_dict(cls, d: dict) -> ControlObject:
        return cls(
            **{
                k: d[k]
                for k in [
                    "object_id",
                    "object_type",
                    "name",
                    "state",
                    "operational_plane",
                ]
                if k in d
            }
        )


@dataclass
class EvidencePackage:
    package_id: str
    action_type: str
    package_hash: str
    status: str

    @classmethod
    def from_dict(cls, d: dict) -> EvidencePackage:
        return cls(
            **{k: d.get(k, "") for k in ["package_id", "action_type", "package_hash", "status"]}
        )
