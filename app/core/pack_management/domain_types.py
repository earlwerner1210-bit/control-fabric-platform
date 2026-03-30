"""Domain types for the Pack Management System."""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class PackStatus(str, enum.Enum):
    AVAILABLE = "available"
    INSTALLED = "installed"
    UPGRADING = "upgrading"
    DEPRECATED = "deprecated"
    INCOMPATIBLE = "incompatible"


class PackVersion(BaseModel, frozen=True):
    major: int = 1
    minor: int = 0
    patch: int = 0

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def is_compatible_with(self, other: PackVersion) -> bool:
        return self.major == other.major


class PackManifest(BaseModel, frozen=True):
    """Immutable manifest describing a domain pack."""

    pack_id: str
    pack_name: str
    version: PackVersion
    description: str = ""
    author: str = "platform"
    namespaces: list[str] = Field(default_factory=list)
    rule_count: int = 0
    schema_count: int = 0
    dependencies: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PackInstallRequest(BaseModel):
    pack_id: str
    target_environment: str = "staging"
    requested_by: str = "system"
    force: bool = False


class PackDiff(BaseModel, frozen=True):
    """Diff between two pack versions."""

    pack_id: str
    from_version: str
    to_version: str
    rules_added: list[str] = Field(default_factory=list)
    rules_removed: list[str] = Field(default_factory=list)
    rules_modified: list[str] = Field(default_factory=list)
    schemas_added: list[str] = Field(default_factory=list)
    schemas_removed: list[str] = Field(default_factory=list)
    breaking: bool = False
