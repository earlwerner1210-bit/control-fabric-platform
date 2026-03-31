"""
ServiceNow Evidence Connector

Fetches change requests, incidents, and problem records from ServiceNow
as governance evidence for the release gate.

Authentication: Basic auth or OAuth 2.0.
"""

from __future__ import annotations

import logging
import os

from app.core.connectors.framework import BaseConnector, ConnectorHealth, ConnectorResult
from app.core.ingress.domain_types import ArtefactFormat

logger = logging.getLogger(__name__)

TABLE_EVIDENCE_MAP = {
    "change_request": "change_request",
    "incident": "incident_ticket",
    "problem": "problem_record",
    "sc_req_item": "service_request",
    "sn_si_incident": "security_incident",
}


class ServiceNowConnector(BaseConnector):
    """
    Fetches ServiceNow records as governance evidence.
    Change requests → release gate evidence.
    Incidents → emergency override evidence.
    """

    def __init__(
        self,
        connector_id: str,
        instance: str,
        username: str | None = None,
        password: str | None = None,
        tables: list[str] | None = None,
        state_filter: list[str] | None = None,
        max_records: int = 50,
    ) -> None:
        super().__init__(connector_id, f"servicenow/{instance}", "servicenow")
        self.instance = instance.replace("https://", "").replace("http://", "")
        self.username = username or os.getenv("SNOW_USER", "")
        self.password = password or os.getenv("SNOW_PASS", "")
        self.tables = tables or ["change_request", "incident"]
        self.state_filter = state_filter or ["3", "4"]
        self.max_records = max_records

    def fetch(self) -> ConnectorResult:
        if not self.username:
            return ConnectorResult(
                artefacts=[],
                errors=["SNOW_USER not configured"],
                source_id=self.connector_id,
            )
        try:
            import httpx

            auth = (self.username, self.password)
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            artefacts = []

            for table in self.tables:
                url = f"https://{self.instance}/api/now/table/{table}"
                query = (
                    "^".join([f"state={s}" for s in self.state_filter]) if self.state_filter else ""
                )
                params = {
                    "sysparm_limit": self.max_records,
                    "sysparm_fields": (
                        "sys_id,number,short_description,state,priority,"
                        "assigned_to,opened_by,opened_at,closed_at,"
                        "close_notes,approval"
                    ),
                    "sysparm_query": query,
                }
                with httpx.Client(timeout=30, auth=auth) as client:
                    resp = client.get(url, headers=headers, params=params)
                    if resp.status_code == 401:
                        return ConnectorResult(
                            artefacts=[],
                            errors=["ServiceNow authentication failed"],
                            source_id=self.connector_id,
                        )
                    resp.raise_for_status()
                    records = resp.json().get("result", [])

                evidence_type = TABLE_EVIDENCE_MAP.get(table, "governance_record")
                for rec in records:
                    assigned = rec.get("assigned_to", "")
                    if isinstance(assigned, dict):
                        assigned = assigned.get("display_value", "unassigned")
                    payload = {
                        "name": (
                            f"ServiceNow"
                            f" {rec.get('number', rec.get('sys_id', '')[:8])}:"
                            f" {rec.get('short_description', '')[:80]}"
                        ),
                        "object_type": (
                            "operational_policy" if table == "change_request" else "asset"
                        ),
                        "description": evidence_type,
                        "record_number": rec.get("number", ""),
                        "sys_id": rec.get("sys_id", ""),
                        "table": table,
                        "state": rec.get("state", ""),
                        "priority": rec.get("priority", ""),
                        "approval": rec.get("approval", ""),
                        "assigned_to": assigned,
                        "opened_at": rec.get("opened_at", ""),
                        "closed_at": rec.get("closed_at", ""),
                        "evidence_type": evidence_type,
                        "snow_url": (
                            f"https://{self.instance}/nav_to.do"
                            f"?uri={table}.do?sys_id={rec.get('sys_id', '')}"
                        ),
                    }
                    artefacts.append(
                        self._make_artefact(
                            payload,
                            format=ArtefactFormat.JSON,
                            metadata={
                                "evidence_type": evidence_type,
                                "source": "servicenow",
                                "table": table,
                            },
                        )
                    )

            logger.info(
                "ServiceNow connector %s fetched %d records",
                self.connector_id,
                len(artefacts),
            )
            return ConnectorResult(artefacts=artefacts, errors=[], source_id=self.connector_id)
        except Exception as e:
            self._health = ConnectorHealth.DEGRADED
            logger.error("ServiceNow connector %s failed: %s", self.connector_id, e)
            return ConnectorResult(artefacts=[], errors=[str(e)], source_id=self.connector_id)
