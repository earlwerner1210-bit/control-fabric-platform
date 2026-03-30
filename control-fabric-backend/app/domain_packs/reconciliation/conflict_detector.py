"""
Reconciliation Module - Conflict detection between contract, field,
and telco domains, plus margin leakage trigger identification.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Conflict and leakage models
# ---------------------------------------------------------------------------


class CrossPlaneConflict(BaseModel):
    """A conflict detected between two domain values for the same logical field."""

    field: str = Field(..., description="The logical field where the conflict exists")
    domain_a: str = Field(..., description="First domain (e.g. contract)")
    value_a: str = Field(..., description="Value in domain A")
    domain_b: str = Field(..., description="Second domain (e.g. field)")
    value_b: str = Field(..., description="Value in domain B")
    severity: str = Field("medium", description="Conflict severity: critical, high, medium, low")
    resolution: str = Field("", description="Suggested resolution or explanation")


class LeakageTrigger(BaseModel):
    """A margin leakage trigger identified during reconciliation."""

    trigger_type: str = Field(..., description="Category of leakage")
    description: str = Field("", description="Human-readable description")
    severity: str = Field("medium", description="Severity: critical, high, medium, low")
    source_ref: str = Field("", description="Reference to the source record")
    estimated_impact: str | None = Field(
        None, description="Estimated financial or operational impact"
    )


# ---------------------------------------------------------------------------
# Conflict Detector
# ---------------------------------------------------------------------------


class ConflictDetector:
    """Detects conflicts between contract, field, and telco domain data
    and identifies margin leakage triggers.
    """

    # -- Contract vs Field conflicts -----------------------------------------

    def detect_contract_field_conflict(
        self,
        contract_data: dict[str, Any],
        field_data: dict[str, Any],
    ) -> list[CrossPlaneConflict]:
        """Detect conflicts between a contract object and field work order data.

        Checks:
        - Scope mismatch (description / category alignment)
        - Rate mismatch
        - Approval / authorization mismatch
        """
        conflicts: list[CrossPlaneConflict] = []

        # -- Scope mismatch --------------------------------------------------
        contract_scope = (
            contract_data.get("description", "") or contract_data.get("scope", "")
        ).lower()
        field_desc = (field_data.get("description", "")).lower()
        field_category = field_data.get("work_category", "")

        if contract_scope and field_desc:
            # Simple heuristic: check if the field category term appears in contract scope
            if field_category and field_category.replace("_", " ") not in contract_scope:
                # Check token overlap
                contract_tokens = set(contract_scope.split())
                field_tokens = set(field_desc.split())
                overlap = contract_tokens & field_tokens
                if len(overlap) < 2:
                    conflicts.append(
                        CrossPlaneConflict(
                            field="scope",
                            domain_a="contract",
                            value_a=contract_data.get(
                                "description", contract_data.get("scope", "")
                            ),
                            domain_b="field",
                            value_b=field_data.get("description", ""),
                            severity="high",
                            resolution="Verify that field work is covered under the contract scope",
                        )
                    )

        # -- Rate mismatch ---------------------------------------------------
        contract_rate = contract_data.get("rate", contract_data.get("unit_rate"))
        field_rate = field_data.get("rate", field_data.get("unit_rate"))
        if contract_rate is not None and field_rate is not None:
            try:
                c_rate = float(contract_rate)
                f_rate = float(field_rate)
                if abs(c_rate - f_rate) > 0.01:
                    severity = (
                        "critical" if abs(c_rate - f_rate) / max(c_rate, 0.01) > 0.1 else "medium"
                    )
                    conflicts.append(
                        CrossPlaneConflict(
                            field="rate",
                            domain_a="contract",
                            value_a=str(c_rate),
                            domain_b="field",
                            value_b=str(f_rate),
                            severity=severity,
                            resolution="Reconcile rate difference between contract and field billing",
                        )
                    )
            except (ValueError, TypeError):
                pass

        # -- Rate card reference mismatch ------------------------------------
        contract_rate_ref = contract_data.get("rate_card_ref", contract_data.get("rate_ref", ""))
        field_rate_ref = field_data.get("rate_card_ref", field_data.get("rate_ref", ""))
        if contract_rate_ref and field_rate_ref:
            if contract_rate_ref.lower() != field_rate_ref.lower():
                conflicts.append(
                    CrossPlaneConflict(
                        field="rate_card_ref",
                        domain_a="contract",
                        value_a=contract_rate_ref,
                        domain_b="field",
                        value_b=field_rate_ref,
                        severity="high",
                        resolution="Rate card references do not match - verify correct schedule applied",
                    )
                )

        # -- Approval mismatch -----------------------------------------------
        contract_approval = contract_data.get("approval_status", contract_data.get("approved"))
        field_status = field_data.get("status", "")
        execution_states = {"dispatched", "in_progress", "completed"}
        if field_status in execution_states:
            if contract_approval is not None and str(contract_approval).lower() not in (
                "true",
                "approved",
                "yes",
            ):
                conflicts.append(
                    CrossPlaneConflict(
                        field="approval",
                        domain_a="contract",
                        value_a=str(contract_approval),
                        domain_b="field",
                        value_b=field_status,
                        severity="critical",
                        resolution="Field work is in execution but contract approval is not confirmed",
                    )
                )

        return conflicts

    # -- Field vs Telco (Incident) conflicts ---------------------------------

    def detect_field_service_conflict(
        self,
        field_data: dict[str, Any],
        incident_data: dict[str, Any],
    ) -> list[CrossPlaneConflict]:
        """Detect conflicts between field work order data and incident data.

        Checks:
        - Completion vs open incident (work marked complete but incident still open)
        - Timeline conflicts (work completed before incident reported)
        """
        conflicts: list[CrossPlaneConflict] = []

        field_status = field_data.get("status", "")
        inc_status = incident_data.get("status", "")

        # -- Completion vs open incident -------------------------------------
        if field_status == "completed" and inc_status in (
            "open",
            "acknowledged",
            "investigating",
            "resolving",
        ):
            conflicts.append(
                CrossPlaneConflict(
                    field="status",
                    domain_a="field",
                    value_a=field_status,
                    domain_b="telco",
                    value_b=inc_status,
                    severity="high",
                    resolution="Work order is completed but related incident is still active - verify resolution",
                )
            )

        # -- Reverse: incident resolved but work not completed ---------------
        if inc_status in ("resolved", "closed") and field_status in (
            "pending",
            "approved",
            "dispatched",
            "in_progress",
        ):
            conflicts.append(
                CrossPlaneConflict(
                    field="status",
                    domain_a="telco",
                    value_a=inc_status,
                    domain_b="field",
                    value_b=field_status,
                    severity="medium",
                    resolution="Incident is resolved but associated work order is still in progress",
                )
            )

        # -- Timeline conflicts ----------------------------------------------
        field_completed = field_data.get("completed_date", field_data.get("completed_at"))
        inc_reported = incident_data.get("reported_at")
        if field_completed and inc_reported:
            try:
                from datetime import datetime

                fc = (
                    datetime.fromisoformat(str(field_completed))
                    if isinstance(field_completed, str)
                    else field_completed
                )
                ir = (
                    datetime.fromisoformat(str(inc_reported))
                    if isinstance(inc_reported, str)
                    else inc_reported
                )
                if hasattr(fc, "timestamp") and hasattr(ir, "timestamp"):
                    if fc < ir:
                        conflicts.append(
                            CrossPlaneConflict(
                                field="timeline",
                                domain_a="field",
                                value_a=str(field_completed),
                                domain_b="telco",
                                value_b=str(inc_reported),
                                severity="medium",
                                resolution="Work was completed before incident was reported - may indicate rework",
                            )
                        )
            except (ValueError, TypeError):
                pass

        return conflicts

    # -- Margin leakage triggers ---------------------------------------------

    def detect_margin_leakage(
        self,
        contract_objects: list[dict[str, Any]],
        work_orders: list[dict[str, Any]],
        incidents: list[dict[str, Any]],
    ) -> list[LeakageTrigger]:
        """Identify margin leakage triggers across all three domains.

        Checks:
        1. Work performed but no contract approval found
        2. Work performed but out of contract scope
        3. Incident exists but no billable work order event
        4. Repeated effort (same description, multiple work orders)
        5. State mismatch between domains
        """
        triggers: list[LeakageTrigger] = []
        contract_ids = {str(co.get("contract_id", co.get("id", ""))) for co in contract_objects}
        contract_scopes: dict[str, str] = {}
        contract_approvals: dict[str, Any] = {}
        for co in contract_objects:
            cid = str(co.get("contract_id", co.get("id", "")))
            contract_scopes[cid] = (co.get("description", "") or co.get("scope", "")).lower()
            contract_approvals[cid] = co.get("approval_status", co.get("approved"))

        # -- Check 1: work but no approval -----------------------------------
        for wo in work_orders:
            wo_id = str(wo.get("work_order_id", wo.get("id", "")))
            wo_status = wo.get("status", "")
            contract_ref = wo.get("contract_ref", "")

            if wo_status in ("dispatched", "in_progress", "completed"):
                if contract_ref and contract_ref in contract_approvals:
                    approval = contract_approvals[contract_ref]
                    if approval is not None and str(approval).lower() not in (
                        "true",
                        "approved",
                        "yes",
                    ):
                        triggers.append(
                            LeakageTrigger(
                                trigger_type="work_without_approval",
                                description=f"Work order {wo_id} is {wo_status} but contract {contract_ref} approval is '{approval}'",
                                severity="critical",
                                source_ref=wo_id,
                                estimated_impact="Full work order value at risk",
                            )
                        )
                elif not contract_ref:
                    triggers.append(
                        LeakageTrigger(
                            trigger_type="work_without_approval",
                            description=f"Work order {wo_id} is {wo_status} with no contract reference",
                            severity="high",
                            source_ref=wo_id,
                            estimated_impact="Work may not be billable without contract linkage",
                        )
                    )

        # -- Check 2: work out of scope --------------------------------------
        for wo in work_orders:
            wo_id = str(wo.get("work_order_id", wo.get("id", "")))
            contract_ref = wo.get("contract_ref", "")
            wo_desc = (wo.get("description", "")).lower()

            if contract_ref and contract_ref in contract_scopes:
                scope = contract_scopes[contract_ref]
                if scope and wo_desc:
                    scope_tokens = set(scope.split())
                    wo_tokens = set(wo_desc.split())
                    overlap = scope_tokens & wo_tokens
                    # If very low overlap, flag as potentially out of scope
                    if len(wo_tokens) > 2 and len(overlap) < 2:
                        triggers.append(
                            LeakageTrigger(
                                trigger_type="work_out_of_scope",
                                description=f"Work order {wo_id} description has minimal overlap with contract {contract_ref} scope",
                                severity="medium",
                                source_ref=wo_id,
                                estimated_impact="Work may not be covered under contract terms",
                            )
                        )

        # -- Check 3: incident but no billable event -------------------------
        wo_refs_in_incidents: set[str] = set()
        for inc in incidents:
            for ref in inc.get("work_order_refs", []):
                wo_refs_in_incidents.add(str(ref))

        wo_ids = {str(wo.get("work_order_id", wo.get("id", ""))) for wo in work_orders}

        for inc in incidents:
            inc_id = str(inc.get("incident_id", inc.get("id", "")))
            inc_wo_refs = [str(r) for r in inc.get("work_order_refs", [])]
            if not inc_wo_refs:
                triggers.append(
                    LeakageTrigger(
                        trigger_type="incident_no_billable_event",
                        description=f"Incident {inc_id} has no associated work order references",
                        severity="medium",
                        source_ref=inc_id,
                        estimated_impact="Effort expended on incident may not be captured for billing",
                    )
                )
            else:
                # Check if referenced WOs exist in our dataset
                missing = [r for r in inc_wo_refs if r not in wo_ids]
                if missing:
                    triggers.append(
                        LeakageTrigger(
                            trigger_type="incident_missing_work_orders",
                            description=f"Incident {inc_id} references work orders not in dataset: {', '.join(missing)}",
                            severity="low",
                            source_ref=inc_id,
                        )
                    )

        # -- Check 4: repeated effort (duplicate descriptions) ---------------
        desc_to_wos: dict[str, list[str]] = {}
        for wo in work_orders:
            wo_id = str(wo.get("work_order_id", wo.get("id", "")))
            desc_key = wo.get("description", "").strip().lower()
            if desc_key and len(desc_key) > 10:
                desc_to_wos.setdefault(desc_key, []).append(wo_id)

        for desc_key, wo_ids_list in desc_to_wos.items():
            if len(wo_ids_list) > 1:
                triggers.append(
                    LeakageTrigger(
                        trigger_type="repeat_effort",
                        description=f"Multiple work orders with identical description: {', '.join(wo_ids_list)}",
                        severity="medium",
                        source_ref=wo_ids_list[0],
                        estimated_impact="Potential duplicate billing or rework cost",
                    )
                )

        # -- Check 5: state mismatch -----------------------------------------
        for wo in work_orders:
            wo_id = str(wo.get("work_order_id", wo.get("id", "")))
            wo_status = wo.get("status", "")
            # Find incidents referencing this WO
            for inc in incidents:
                inc_wo_refs = [str(r) for r in inc.get("work_order_refs", [])]
                if wo_id in inc_wo_refs:
                    inc_status = inc.get("status", "")
                    if wo_status == "completed" and inc_status in (
                        "open",
                        "acknowledged",
                        "investigating",
                    ):
                        triggers.append(
                            LeakageTrigger(
                                trigger_type="state_mismatch",
                                description=(
                                    f"Work order {wo_id} is completed but incident "
                                    f"{inc.get('incident_id', inc.get('id', ''))} is still '{inc_status}'"
                                ),
                                severity="high",
                                source_ref=wo_id,
                                estimated_impact="Billing may be premature if incident is not resolved",
                            )
                        )

        return triggers
