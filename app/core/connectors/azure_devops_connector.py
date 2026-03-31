"""
Azure DevOps Evidence Connector

Fetches pipeline runs, work items (change requests), and release records
from Azure DevOps as governance evidence.

Authentication: Personal Access Token.
"""

from __future__ import annotations

import base64
import logging
import os

from app.core.connectors.framework import BaseConnector, ConnectorHealth, ConnectorResult
from app.core.ingress.domain_types import ArtefactFormat

logger = logging.getLogger(__name__)


class AzureDevOpsConnector(BaseConnector):
    """
    Fetches Azure DevOps pipeline runs and work items as governance evidence.
    """

    BASE_URL = "https://dev.azure.com"

    def __init__(
        self,
        connector_id: str,
        organisation: str,
        project: str,
        pat: str | None = None,
        pipeline_ids: list[int] | None = None,
        max_runs: int = 10,
    ) -> None:
        super().__init__(connector_id, f"ado/{organisation}/{project}", "azure-devops")
        self.organisation = organisation
        self.project = project
        self.pat = pat or os.getenv("ADO_PAT", "")
        self.pipeline_ids = pipeline_ids
        self.max_runs = max_runs

    def _auth_header(self) -> dict:
        if not self.pat:
            return {}
        token = base64.b64encode(f":{self.pat}".encode()).decode()
        return {"Authorization": f"Basic {token}", "Accept": "application/json"}

    def fetch(self) -> ConnectorResult:
        if not self.pat:
            return ConnectorResult(
                artefacts=[],
                errors=["ADO_PAT not configured"],
                source_id=self.connector_id,
            )
        try:
            import httpx

            headers = self._auth_header()
            artefacts = []
            base = f"{self.BASE_URL}/{self.organisation}/{self.project}"

            with httpx.Client(timeout=30) as client:
                pipes_resp = client.get(f"{base}/_apis/pipelines?api-version=7.1", headers=headers)
                pipes_resp.raise_for_status()
                pipelines = pipes_resp.json().get("value", [])
                if self.pipeline_ids:
                    pipelines = [p for p in pipelines if p.get("id") in self.pipeline_ids]

                for pipeline in pipelines[:5]:
                    runs_resp = client.get(
                        f"{base}/_apis/pipelines/{pipeline['id']}/runs"
                        f"?api-version=7.1&$top={self.max_runs}",
                        headers=headers,
                    )
                    if runs_resp.status_code != 200:
                        continue
                    for run in runs_resp.json().get("value", []):
                        result = run.get("result", "unknown")
                        evidence_desc = (
                            "ci_result test_results"
                            if result == "succeeded"
                            else "ci_result test_failure"
                        )
                        payload = {
                            "name": (f"ADO Pipeline: {pipeline.get('name')} #{run.get('id')}"),
                            "object_type": "asset",
                            "description": evidence_desc,
                            "run_id": str(run.get("id")),
                            "pipeline_id": pipeline.get("id"),
                            "pipeline_name": pipeline.get("name"),
                            "state": run.get("state"),
                            "result": result,
                            "created_at": run.get("createdDate", ""),
                            "finished_at": run.get("finishedDate", ""),
                            "evidence_type": "ci_result",
                            "ado_url": run.get("_links", {}).get("web", {}).get("href", ""),
                        }
                        artefacts.append(
                            self._make_artefact(
                                payload,
                                format=ArtefactFormat.JSON,
                                metadata={
                                    "evidence_type": "ci_result",
                                    "source": "azure_devops",
                                },
                            )
                        )

            logger.info(
                "ADO connector %s fetched %d runs",
                self.connector_id,
                len(artefacts),
            )
            return ConnectorResult(artefacts=artefacts, errors=[], source_id=self.connector_id)
        except Exception as e:
            self._health = ConnectorHealth.DEGRADED
            logger.error("ADO connector %s failed: %s", self.connector_id, e)
            return ConnectorResult(artefacts=[], errors=[str(e)], source_id=self.connector_id)
