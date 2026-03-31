"""
Jira Evidence Connector

Fetches Jira issues, epics, and change requests as governance evidence.
Supports: change requests, incident tickets, approval records.

Authentication: API token (basic auth) or OAuth 2.0.
"""

from __future__ import annotations

import base64
import logging
import os

from app.core.connectors.framework import BaseConnector, ConnectorHealth, ConnectorResult
from app.core.ingress.domain_types import ArtefactFormat

logger = logging.getLogger(__name__)


class JiraConnector(BaseConnector):
    """
    Fetches Jira issues as governance evidence artefacts.
    Change requests become evidence for release governance.
    Incident tickets become evidence for emergency overrides.
    """

    def __init__(
        self,
        connector_id: str,
        base_url: str,
        email: str | None = None,
        api_token: str | None = None,
        project_key: str = "",
        issue_types: list[str] | None = None,
        statuses: list[str] | None = None,
        max_results: int = 50,
    ) -> None:
        super().__init__(connector_id, f"jira/{base_url}", "jira")
        self.base_url = base_url.rstrip("/")
        self.email = email or os.getenv("JIRA_EMAIL", "")
        self.api_token = api_token or os.getenv("JIRA_TOKEN", "")
        self.project_key = project_key
        self.issue_types = issue_types or ["Change Request", "Story", "Epic"]
        self.statuses = statuses or ["Done", "Approved", "Closed"]
        self.max_results = max_results

    def _auth_header(self) -> dict:
        if not self.email or not self.api_token:
            return {}
        token = base64.b64encode(f"{self.email}:{self.api_token}".encode()).decode()
        return {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def fetch(self) -> ConnectorResult:
        if not self.api_token:
            return ConnectorResult(
                artefacts=[],
                errors=["JIRA_TOKEN not configured"],
                source_id=self.connector_id,
            )
        try:
            import httpx

            type_filter = " OR ".join([f'issuetype = "{t}"' for t in self.issue_types])
            status_filter = " OR ".join([f'status = "{s}"' for s in self.statuses])
            if self.project_key:
                jql = (
                    f"project = {self.project_key} AND ({type_filter})"
                    f" AND ({status_filter}) ORDER BY updated DESC"
                )
            else:
                jql = f"({type_filter}) AND ({status_filter}) ORDER BY updated DESC"

            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{self.base_url}/rest/api/3/issue/search",
                    headers=self._auth_header(),
                    json={
                        "jql": jql,
                        "maxResults": self.max_results,
                        "fields": [
                            "summary",
                            "status",
                            "assignee",
                            "reporter",
                            "issuetype",
                            "priority",
                            "created",
                            "updated",
                            "resolutiondate",
                            "labels",
                            "description",
                        ],
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            artefacts = []
            for issue in data.get("issues", []):
                fields = issue.get("fields", {})
                issue_type = fields.get("issuetype", {}).get("name", "")
                issue_type_lower = issue_type.lower()
                obj_type = "operational_policy" if "change" in issue_type_lower else "asset"
                if "change" in issue_type_lower:
                    evidence_type = "change_request"
                elif "incident" in issue_type_lower:
                    evidence_type = "incident_ticket"
                else:
                    evidence_type = "approval_record"

                payload = {
                    "name": (f"Jira {issue.get('key')}: {fields.get('summary', '')[:80]}"),
                    "object_type": obj_type,
                    "description": evidence_type,
                    "issue_key": issue.get("key"),
                    "issue_type": issue_type,
                    "status": fields.get("status", {}).get("name", ""),
                    "priority": fields.get("priority", {}).get("name", ""),
                    "assignee": (fields.get("assignee") or {}).get("displayName", "unassigned"),
                    "reporter": (fields.get("reporter") or {}).get("displayName", "unknown"),
                    "created_at": fields.get("created", ""),
                    "updated_at": fields.get("updated", ""),
                    "resolved_at": fields.get("resolutiondate", ""),
                    "labels": fields.get("labels", []),
                    "evidence_type": evidence_type,
                    "jira_url": f"{self.base_url}/browse/{issue.get('key')}",
                }
                artefacts.append(
                    self._make_artefact(
                        payload,
                        format=ArtefactFormat.JSON,
                        metadata={
                            "evidence_type": evidence_type,
                            "source": "jira",
                            "issue_key": issue.get("key", ""),
                        },
                    )
                )

            logger.info(
                "Jira connector %s fetched %d issues",
                self.connector_id,
                len(artefacts),
            )
            return ConnectorResult(artefacts=artefacts, errors=[], source_id=self.connector_id)
        except Exception as e:
            self._health = ConnectorHealth.DEGRADED
            logger.error("Jira connector %s failed: %s", self.connector_id, e)
            return ConnectorResult(artefacts=[], errors=[str(e)], source_id=self.connector_id)
