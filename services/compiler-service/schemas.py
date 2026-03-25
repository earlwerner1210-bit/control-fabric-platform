"""Compiler service request/response schemas."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas.common import BaseSchema
from shared.schemas.control_objects import ControlObjectResponse


class CompileContractRequest(BaseModel):
    document_id: uuid.UUID
    domain_pack: str = "contract-margin"
    extract_obligations: bool = True
    extract_penalties: bool = True
    extract_billing: bool = True


class CompileWorkOrderRequest(BaseModel):
    document_id: uuid.UUID
    domain_pack: str = "utilities-field"


class CompileIncidentRequest(BaseModel):
    document_id: uuid.UUID
    domain_pack: str = "telco-ops"
    severity: int = Field(default=3, ge=1, le=5)


class CompileResponse(BaseSchema):
    document_id: uuid.UUID
    control_objects: list[ControlObjectResponse] = Field(default_factory=list)
    links_created: int = 0
    warnings: list[str] = Field(default_factory=list)
