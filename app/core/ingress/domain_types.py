from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ArtefactFormat(str, Enum):
    PDF = "pdf"
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    TEXT = "text"
    API_RESPONSE = "api_response"
    SYSTEM_LOG = "system_log"


class NormalisationStatus(str, Enum):
    PENDING = "pending"
    NORMALISED = "normalised"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class RawArtefact(BaseModel):
    """
    An unprocessed enterprise artefact entering the platform.
    Patent Claim (Theme 1): The Ingress Layer captures heterogeneous raw
    inputs and normalises them into typed control objects.
    """

    artefact_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_system: str
    source_uri: str | None = None
    format: ArtefactFormat
    raw_content: str | bytes
    submitted_by: str
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
    content_hash: str = Field(default="")

    @model_validator(mode="after")
    def compute_content_hash(self) -> RawArtefact:
        content = (
            self.raw_content if isinstance(self.raw_content, bytes) else self.raw_content.encode()
        )
        self.content_hash = hashlib.sha256(content).hexdigest()
        return self


class NormalisationResult(BaseModel):
    """
    Result of normalising a raw artefact into typed control objects.
    Patent Claim: Early metadata stamping ensures unbreakable provenance
    chain from the exact moment of ingestion.
    """

    artefact_id: str
    status: NormalisationStatus
    extracted_objects: list[dict[str, Any]] = Field(default_factory=list)
    extraction_errors: list[str] = Field(default_factory=list)
    normalised_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    normalised_by: str = Field(default="ingress-pipeline")
    object_count: int = Field(default=0)

    @model_validator(mode="after")
    def set_object_count(self) -> NormalisationResult:
        self.object_count = len(self.extracted_objects)
        return self
