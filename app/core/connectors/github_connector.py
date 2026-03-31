"""
GitHub Actions Evidence Connector

Fetches CI/CD workflow run results from GitHub Actions and converts
them into RawArtefacts for the ingestion pipeline.

Supports: workflow runs, check runs, deployment statuses.
Authentication: GitHub Personal Access Token or GitHub App.

Usage:
    connector = GitHubActionsConnector(
        connector_id="github-prod",
        owner="myorg",
        repo="myrepo",
        token=os.getenv("GITHUB_TOKEN"),
    )
    result = connector.fetch()
"""

from __future__ import annotations

import logging
import os

from app.core.connectors.framework import BaseConnector, ConnectorHealth, ConnectorResult
from app.core.ingress.domain_types import ArtefactFormat

logger = logging.getLogger(__name__)


class GitHubActionsConnector(BaseConnector):
    """
    Fetches GitHub Actions workflow run results as governance evidence.
    Each workflow run becomes a RawArtefact with:
    - run_id, status (completed/in_progress), conclusion (success/failure)
    - test_coverage_pct (if available from artifacts)
    - branch, commit_sha, triggered_by
    """

    BASE_URL = "https://api.github.com"

    def __init__(
        self,
        connector_id: str,
        owner: str,
        repo: str,
        token: str | None = None,
        workflow_id: str | None = None,
        branch: str = "main",
        max_runs: int = 10,
    ) -> None:
        super().__init__(connector_id, f"github/{owner}/{repo}", "github-actions")
        self.owner = owner
        self.repo = repo
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self.workflow_id = workflow_id
        self.branch = branch
        self.max_runs = max_runs

    def fetch(self) -> ConnectorResult:
        if not self.token:
            logger.warning("GitHubActionsConnector: no token configured — returning empty result")
            return ConnectorResult(
                artefacts=[],
                errors=["GITHUB_TOKEN not configured"],
                source_id=self.connector_id,
            )
        try:
            import httpx

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            path = f"/repos/{self.owner}/{self.repo}/actions/runs"
            params: dict = {
                "branch": self.branch,
                "per_page": self.max_runs,
                "status": "completed",
            }
            if self.workflow_id:
                params["workflow_id"] = self.workflow_id

            with httpx.Client(timeout=30) as client:
                resp = client.get(f"{self.BASE_URL}{path}", headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()

            artefacts = []
            for run in data.get("workflow_runs", []):
                conclusion = run.get("conclusion", "unknown")
                evidence_desc = (
                    "ci_result test_results"
                    if conclusion == "success"
                    else "ci_result test_failure"
                )
                payload = {
                    "name": (
                        f"GitHub Actions: {run.get('name', 'workflow')} #{run.get('run_number')}"
                    ),
                    "object_type": "asset",
                    "description": evidence_desc,
                    "run_id": str(run.get("id")),
                    "run_number": run.get("run_number"),
                    "workflow_name": run.get("name"),
                    "status": run.get("status"),
                    "conclusion": conclusion,
                    "branch": run.get("head_branch"),
                    "commit_sha": run.get("head_sha", "")[:12],
                    "triggered_by": run.get("triggering_actor", {}).get("login", "unknown"),
                    "started_at": run.get("run_started_at", ""),
                    "completed_at": run.get("updated_at", ""),
                    "run_url": run.get("html_url", ""),
                    "evidence_type": "ci_result",
                }
                artefacts.append(
                    self._make_artefact(
                        payload,
                        format=ArtefactFormat.JSON,
                        metadata={
                            "evidence_type": "ci_result",
                            "source": "github_actions",
                            "repo": f"{self.owner}/{self.repo}",
                        },
                    )
                )

            logger.info(
                "GitHub connector %s fetched %d runs",
                self.connector_id,
                len(artefacts),
            )
            return ConnectorResult(artefacts=artefacts, errors=[], source_id=self.connector_id)

        except Exception as e:
            self._health = ConnectorHealth.DEGRADED
            logger.error("GitHub connector %s failed: %s", self.connector_id, e)
            return ConnectorResult(artefacts=[], errors=[str(e)], source_id=self.connector_id)

    def get_deployment_status(self, environment: str = "production") -> ConnectorResult:
        """Fetch deployment statuses for a specific environment."""
        if not self.token:
            return ConnectorResult(
                artefacts=[],
                errors=["GITHUB_TOKEN not configured"],
                source_id=self.connector_id,
            )
        try:
            import httpx

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
            }
            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    f"{self.BASE_URL}/repos/{self.owner}/{self.repo}/deployments",
                    headers=headers,
                    params={"environment": environment, "per_page": 5},
                )
                resp.raise_for_status()
                deployments = resp.json()

            artefacts = []
            for dep in deployments:
                payload = {
                    "name": (f"GitHub Deployment: {dep.get('environment')} #{dep.get('id')}"),
                    "object_type": "asset",
                    "description": "deployment_evidence",
                    "deployment_id": str(dep.get("id")),
                    "environment": dep.get("environment"),
                    "ref": dep.get("ref"),
                    "sha": dep.get("sha", "")[:12],
                    "deployed_by": dep.get("creator", {}).get("login", "unknown"),
                    "created_at": dep.get("created_at", ""),
                    "evidence_type": "deployment_evidence",
                }
                artefacts.append(
                    self._make_artefact(
                        payload,
                        format=ArtefactFormat.JSON,
                        metadata={"evidence_type": "deployment_evidence"},
                    )
                )
            return ConnectorResult(artefacts=artefacts, errors=[], source_id=self.connector_id)
        except Exception as e:
            return ConnectorResult(artefacts=[], errors=[str(e)], source_id=self.connector_id)
