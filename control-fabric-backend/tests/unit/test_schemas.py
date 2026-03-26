"""Unit tests for Pydantic schema creation and validation."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.schemas.common import BaseSchema, ErrorResponse, HealthResponse, PaginatedResponse
from app.schemas.documents import DocumentUploadResponse, ParseResponse
from app.schemas.workflows import (
    ContractCompileInput,
    ContractCompileOutput,
    MarginDiagnosisInput,
    WorkflowCaseCreate,
    WorkflowStatusEnum,
)
from app.schemas.validation import ValidationResultResponse
from app.schemas.control_objects import ControlObjectCreate, ControlObjectTypeEnum


class TestBaseSchema:
    def test_base_schema_orm_mode(self):
        class Sample(BaseSchema):
            name: str

        obj = Sample(name="test")
        assert obj.name == "test"


class TestHealthResponse:
    def test_health_response_creation(self):
        resp = HealthResponse(status="ok", version="0.1.0", environment="dev")
        assert resp.status == "ok"
        assert resp.version == "0.1.0"


class TestErrorResponse:
    def test_error_response_creation(self):
        resp = ErrorResponse(detail="Not found", code="NOT_FOUND")
        assert resp.detail == "Not found"
        assert resp.code == "NOT_FOUND"
        assert resp.timestamp is not None

    def test_error_response_with_extra(self):
        resp = ErrorResponse(detail="Bad", code="BAD", extra={"field": "value"})
        assert resp.extra == {"field": "value"}


class TestPaginatedResponse:
    def test_paginated_response(self):
        resp = PaginatedResponse[str](items=["a", "b"], total=2, page=1, page_size=10)
        assert len(resp.items) == 2
        assert resp.total == 2


class TestDocumentSchemas:
    def test_document_upload_response(self):
        now = datetime.now(timezone.utc)
        resp = DocumentUploadResponse(
            id=uuid4(),
            filename="contract.pdf",
            content_type="application/pdf",
            file_size_bytes=1024,
            checksum_sha256="a" * 64,
            status="uploaded",
            created_at=now,
        )
        assert resp.filename == "contract.pdf"

    def test_parse_response(self):
        resp = ParseResponse(
            document_id=uuid4(),
            document_type="contract",
            status="parsed",
            chunk_count=5,
        )
        assert resp.status == "parsed"


class TestWorkflowSchemas:
    def test_contract_compile_input(self):
        inp = ContractCompileInput(contract_document_id=uuid4())
        assert inp.sla_document_ids == []

    def test_contract_compile_output(self):
        out = ContractCompileOutput(
            case_id=uuid4(),
            status=WorkflowStatusEnum.COMPLETED,
        )
        assert out.obligation_count == 0

    def test_margin_diagnosis_input(self):
        inp = MarginDiagnosisInput(contract_document_id=uuid4())
        assert inp.work_order_document_id is None

    def test_workflow_case_create(self):
        wf = WorkflowCaseCreate(workflow_type="contract_compile")
        assert wf.workflow_type == "contract_compile"


class TestValidationSchema:
    def test_validation_result_response(self):
        now = datetime.now(timezone.utc)
        resp = ValidationResultResponse(
            id=uuid4(),
            target_type="contract_compile",
            target_id=uuid4(),
            rule_name="has_clauses",
            passed=True,
            severity="info",
            created_at=now,
        )
        assert resp.passed is True


class TestControlObjectSchemas:
    def test_control_object_create(self):
        obj = ControlObjectCreate(
            control_type=ControlObjectTypeEnum.OBLIGATION,
            domain="contract-margin",
            label="Test obligation",
        )
        assert obj.control_type == ControlObjectTypeEnum.OBLIGATION

    def test_control_object_type_enum(self):
        assert ControlObjectTypeEnum.OBLIGATION.value == "obligation"
        assert ControlObjectTypeEnum.SLA_TARGET.value == "sla_target"
        assert ControlObjectTypeEnum.RATE_CARD_ITEM.value == "rate_card_item"
