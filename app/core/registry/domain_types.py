from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.core.graph.domain_types import ControlObjectType


class SchemaNamespace(BaseModel):
    """
    A registered schema namespace — defines valid attributes for a control object type.
    Patent Claim (Theme 5): Domain packs inject new namespaces without modifying core.
    """

    namespace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    version: str
    domain_pack: str = Field(description="Which domain pack owns this namespace")
    object_type: ControlObjectType
    required_attributes: list[str] = Field(default_factory=list)
    optional_attributes: list[str] = Field(default_factory=list)
    description: str = Field(default="")
    is_core: bool = Field(default=False, description="True for core platform namespaces")
    registered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VersionRecord(BaseModel):
    """
    Immutable record of a single object version.
    Patent Claim: Linear version history — past states cannot be altered.
    """

    model_config = {"frozen": True}

    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    object_id: str
    version: int
    object_hash: str
    state: str
    changed_by: str
    change_reason: str = Field(default="")
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    snapshot: dict[str, Any] = Field(description="Full object snapshot at this version")
    record_hash: str = Field(default="")

    @model_validator(mode="after")
    def compute_record_hash(self) -> VersionRecord:
        payload = f"{self.object_id}{self.version}{self.object_hash}{self.state}{self.recorded_at.isoformat()}"
        object.__setattr__(self, "record_hash", hashlib.sha256(payload.encode()).hexdigest())
        return self


class RegistryEvent(BaseModel):
    """
    An immutable event in the registry audit log.
    Every registration, update, and state change is recorded.
    """

    model_config = {"frozen": True}

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(
        description="registered | updated | state_changed | deprecated | retired"
    )
    object_id: str
    object_type: str
    performed_by: str
    event_detail: str = Field(default="")
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_hash: str = Field(default="")

    @model_validator(mode="after")
    def compute_event_hash(self) -> RegistryEvent:
        payload = f"{self.event_id}{self.event_type}{self.object_id}{self.performed_by}{self.occurred_at.isoformat()}"
        object.__setattr__(self, "event_hash", hashlib.sha256(payload.encode()).hexdigest())
        return self
