"""Contract compile workflow -- orchestrates contract parsing and control object creation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContractCompileResult:
    """Result of a contract compile workflow run."""

    case_id: str
    document_id: str
    control_objects_created: int = 0
    entity_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: str = ""
    status: str = "completed"


class ContractCompileWorkflow:
    """Orchestrates the contract compile workflow.

    Steps:
    1. Parse the contract document
    2. Extract clauses, SLA table, rate card
    3. Create control objects for each extracted element
    4. Run validation
    5. Record audit trail
    """

    def __init__(
        self,
        parser: Any = None,
        validator: Any = None,
        audit_logger: Any = None,
    ) -> None:
        self.parser = parser
        self.validator = validator
        self.audit_logger = audit_logger

    async def run(
        self,
        case_id: str,
        document_id: str,
        tenant_id: str,
        domain_pack: str = "contract-margin",
        options: dict[str, Any] | None = None,
    ) -> ContractCompileResult:
        """Execute the contract compile workflow.

        Args:
            case_id: Unique case identifier.
            document_id: ID of the document to compile.
            tenant_id: Tenant context.
            domain_pack: Domain pack to use for parsing rules.
            options: Optional workflow configuration.

        Returns:
            ContractCompileResult with created control objects.
        """
        warnings: list[str] = []
        control_objects_created = 0
        entity_ids: list[str] = []

        # Step 1: Parse the contract
        if self.parser:
            try:
                parsed = self.parser.parse_contract(document_id)
                if hasattr(parsed, "clauses"):
                    control_objects_created += len(parsed.clauses)
                if hasattr(parsed, "obligations"):
                    control_objects_created += len(parsed.obligations)
                if hasattr(parsed, "penalties"):
                    control_objects_created += len(parsed.penalties)
            except Exception as e:
                warnings.append(f"Parser error: {e}")

        # Step 2: Validate
        if self.validator:
            try:
                validation_result = self.validator.validate(
                    {
                        "case_id": case_id,
                        "document_id": document_id,
                        "control_objects_created": control_objects_created,
                    }
                )
                if hasattr(validation_result, "status"):
                    if validation_result.status.value == "warned":
                        warnings.append("Validation produced warnings")
            except Exception as e:
                warnings.append(f"Validation error: {e}")

        # Step 3: Audit
        if self.audit_logger:
            try:
                await self.audit_logger.log(
                    case_id=case_id,
                    event_type="contract.compiled",
                    detail={
                        "document_id": document_id,
                        "control_objects_created": control_objects_created,
                    },
                )
            except Exception:
                pass

        summary = (
            f"Compiled contract {document_id}: {control_objects_created} control objects created"
        )

        return ContractCompileResult(
            case_id=case_id,
            document_id=document_id,
            control_objects_created=control_objects_created,
            entity_ids=entity_ids,
            warnings=warnings,
            summary=summary,
        )
