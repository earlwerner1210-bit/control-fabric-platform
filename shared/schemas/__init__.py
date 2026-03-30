"""Shared Pydantic schemas -- re-exported for convenience."""

from shared.schemas.audit import AuditEventCreate, AuditEventResponse
from shared.schemas.common import (
    BaseSchema,
    ErrorResponse,
    HealthResponse,
    PaginatedResponse,
    TenantContext,
)
from shared.schemas.control_objects import (
    ControlLinkCreate,
    ControlLinkResponse,
    ControlObjectCreate,
    ControlObjectResponse,
    ControlObjectType,
)
from shared.schemas.documents import (
    DocumentChunkResponse,
    DocumentResponse,
    DocumentUploadRequest,
)
from shared.schemas.validation import (
    ValidationResultCreate,
    ValidationResultResponse,
    ValidationRuleResult,
    ValidationSeverity,
)
from shared.schemas.workflows import (
    CaseVerdict,
    ContractCompileInput,
    ContractCompileOutput,
    IncidentDispatchInput,
    IncidentDispatchOutput,
    MarginDiagnosisInput,
    MarginDiagnosisOutput,
    MarginVerdict,
    ReadinessVerdict,
    WorkflowCaseCreate,
    WorkflowCaseResponse,
    WorkflowStatus,
    WorkOrderReadinessInput,
    WorkOrderReadinessOutput,
)

__all__ = [
    # common
    "BaseSchema",
    "ErrorResponse",
    "HealthResponse",
    "PaginatedResponse",
    "TenantContext",
    # documents
    "DocumentChunkResponse",
    "DocumentResponse",
    "DocumentUploadRequest",
    # control objects
    "ControlLinkCreate",
    "ControlLinkResponse",
    "ControlObjectCreate",
    "ControlObjectResponse",
    "ControlObjectType",
    # workflows
    "CaseVerdict",
    "ContractCompileInput",
    "ContractCompileOutput",
    "IncidentDispatchInput",
    "IncidentDispatchOutput",
    "MarginDiagnosisInput",
    "MarginDiagnosisOutput",
    "MarginVerdict",
    "ReadinessVerdict",
    "WorkflowCaseCreate",
    "WorkflowCaseResponse",
    "WorkflowStatus",
    "WorkOrderReadinessInput",
    "WorkOrderReadinessOutput",
    # validation
    "ValidationResultCreate",
    "ValidationResultResponse",
    "ValidationRuleResult",
    "ValidationSeverity",
    # audit
    "AuditEventCreate",
    "AuditEventResponse",
]
