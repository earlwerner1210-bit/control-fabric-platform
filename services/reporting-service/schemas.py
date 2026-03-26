"""Reporting service request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas.common import BaseSchema


class GenerateReportRequest(BaseModel):
    case_id: uuid.UUID
    report_type: str = Field(
        default="case_summary", description="case_summary or management_summary"
    )
    format: str = Field(default="json", description="json or text")
    include_audit_trail: bool = True
    include_validations: bool = True


class ReportResponse(BaseSchema):
    id: uuid.UUID
    case_id: uuid.UUID
    tenant_id: uuid.UUID
    report_type: str
    content: dict[str, Any]
    format: str
    created_at: datetime
