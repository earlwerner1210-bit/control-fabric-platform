"""
Evidence Source Connector Framework

Provides a standard interface for ingesting evidence from external sources.
Every connector produces RawArtefacts that flow through the standard
ingestion pipeline — provenance is established at source connection time.

Built-in connectors:
  - API connector (REST/GraphQL evidence sources)
  - File drop connector (CSV, JSON, PDF uploads)
  - Webhook connector (CI/CD push events)
  - Log/event connector (structured log evidence)

Author: Control Fabric Platform
Date: March 2026
"""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import random
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from app.core.ingress.domain_types import ArtefactFormat, RawArtefact

logger = logging.getLogger(__name__)


class ConnectorHealth:
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class ConnectorResult:
    def __init__(
        self,
        artefacts: list[RawArtefact],
        errors: list[str],
        source_id: str,
    ) -> None:
        self.artefacts = artefacts
        self.errors = errors
        self.source_id = source_id
        self.fetched_at = datetime.now(UTC)

    @property
    def success(self) -> bool:
        return len(self.artefacts) > 0 and len(self.errors) == 0

    @property
    def artefact_count(self) -> int:
        return len(self.artefacts)


class BaseConnector(ABC):
    """
    Base class for all evidence source connectors.
    Every connector produces RawArtefacts with source provenance.
    """

    def __init__(
        self,
        connector_id: str,
        source_system: str,
        submitted_by: str,
    ) -> None:
        self.connector_id = connector_id
        self.source_system = source_system
        self.submitted_by = submitted_by
        self._health = ConnectorHealth.HEALTHY

    @abstractmethod
    def fetch(self) -> ConnectorResult:
        """Fetch evidence from the source and return as RawArtefacts."""

    def _make_artefact(
        self,
        content: Any,
        format: ArtefactFormat = ArtefactFormat.JSON,
        metadata: dict | None = None,
    ) -> RawArtefact:
        raw = json.dumps(content) if isinstance(content, (dict, list)) else str(content)
        return RawArtefact(
            source_system=self.source_system,
            format=format,
            raw_content=raw,
            submitted_by=self.submitted_by,
            metadata=metadata or {},
        )

    @property
    def health(self) -> str:
        return self._health


class ApiConnector(BaseConnector):
    """
    REST API evidence connector.
    Fetches evidence from a REST endpoint and ingests as typed control objects.
    """

    def __init__(
        self,
        connector_id: str,
        source_system: str,
        submitted_by: str,
        endpoint_url: str,
        headers: dict | None = None,
        payload_path: str | None = None,
    ) -> None:
        super().__init__(connector_id, source_system, submitted_by)
        self.endpoint_url = endpoint_url
        self.headers = headers or {}
        self.payload_path = payload_path

    def fetch(self) -> ConnectorResult:
        try:
            import httpx

            response = httpx.get(self.endpoint_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            if self.payload_path:
                for key in self.payload_path.split("."):
                    data = data[key]
            items = data if isinstance(data, list) else [data]
            artefacts = [
                self._make_artefact(item, metadata={"source_url": self.endpoint_url})
                for item in items
            ]
            logger.info(
                "API connector %s fetched %d items",
                self.connector_id,
                len(artefacts),
            )
            return ConnectorResult(artefacts=artefacts, errors=[], source_id=self.connector_id)
        except Exception as e:
            logger.error("API connector %s failed: %s", self.connector_id, e)
            self._health = ConnectorHealth.DEGRADED
            return ConnectorResult(artefacts=[], errors=[str(e)], source_id=self.connector_id)


class FileDropConnector(BaseConnector):
    """
    File-based evidence connector.
    Ingests JSON or CSV files as evidence artefacts.
    """

    def __init__(
        self,
        connector_id: str,
        source_system: str,
        submitted_by: str,
        file_path: str,
    ) -> None:
        super().__init__(connector_id, source_system, submitted_by)
        self.file_path = file_path

    def fetch(self) -> ConnectorResult:
        try:
            path = pathlib.Path(self.file_path)
            if not path.exists():
                return ConnectorResult(
                    artefacts=[],
                    errors=[f"File not found: {self.file_path}"],
                    source_id=self.connector_id,
                )
            content = path.read_text()
            fmt = ArtefactFormat.JSON if path.suffix == ".json" else ArtefactFormat.CSV
            artefact = self._make_artefact(
                content,
                format=fmt,
                metadata={
                    "file_path": str(path),
                    "file_size": path.stat().st_size,
                },
            )
            return ConnectorResult(artefacts=[artefact], errors=[], source_id=self.connector_id)
        except Exception as e:
            return ConnectorResult(artefacts=[], errors=[str(e)], source_id=self.connector_id)


class WebhookConnector(BaseConnector):
    """
    Webhook/push evidence connector.
    Accepts pushed payloads from CI/CD systems (GitHub Actions, Jenkins, etc.)
    """

    def __init__(
        self,
        connector_id: str,
        source_system: str,
        submitted_by: str,
    ) -> None:
        super().__init__(connector_id, source_system, submitted_by)
        self._buffer: list[dict] = []

    def receive(self, payload: dict, signature: str | None = None) -> None:
        """Receive a pushed payload. Called by webhook handler."""
        self._buffer.append(
            {
                "payload": payload,
                "received_at": datetime.now(UTC).isoformat(),
                "signature": signature,
            }
        )

    def fetch(self) -> ConnectorResult:
        if not self._buffer:
            return ConnectorResult(artefacts=[], errors=[], source_id=self.connector_id)
        artefacts = [
            self._make_artefact(
                item["payload"],
                metadata={"received_at": item["received_at"]},
            )
            for item in self._buffer
        ]
        self._buffer.clear()
        return ConnectorResult(artefacts=artefacts, errors=[], source_id=self.connector_id)


class SimulatedCICDConnector(BaseConnector):
    """
    Simulated CI/CD evidence connector for demos and tests.
    Generates realistic CI/CD evidence payloads without a real CI system.
    """

    def __init__(
        self,
        connector_id: str = "simulated-cicd",
        pass_rate: float = 0.8,
    ) -> None:
        super().__init__(connector_id, "simulated-ci-cd", "ci-system")
        self.pass_rate = pass_rate
        self._run_counter = 0

    def fetch(self) -> ConnectorResult:
        self._run_counter += 1
        passed = random.random() < self.pass_rate  # noqa: S311
        payload = {
            "name": f"CI Run #{self._run_counter}",
            "object_type": "asset",
            "description": (f"CI/CD evidence {'test_results' if passed else 'test_failure'}"),
            "run_id": f"run-{self._run_counter:04d}",
            "status": "passed" if passed else "failed",
            "test_coverage_pct": (
                round(random.uniform(70, 99), 1)  # noqa: S311
                if passed
                else round(random.uniform(20, 60), 1)  # noqa: S311
            ),
            "duration_seconds": random.randint(45, 300),  # noqa: S311
            "branch": "main",
            "commit_sha": hashlib.sha256(f"commit-{self._run_counter}".encode()).hexdigest()[:12],
        }
        artefact = self._make_artefact(payload, metadata={"evidence_type": "ci_result"})
        return ConnectorResult(artefacts=[artefact], errors=[], source_id=self.connector_id)


class ConnectorRegistry:
    """Registry of all configured evidence source connectors."""

    def __init__(self) -> None:
        self._connectors: dict[str, BaseConnector] = {}

    def register(self, connector: BaseConnector) -> None:
        self._connectors[connector.connector_id] = connector
        logger.info(
            "Connector registered: %s (%s)",
            connector.connector_id,
            connector.source_system,
        )

    def get(self, connector_id: str) -> BaseConnector | None:
        return self._connectors.get(connector_id)

    def fetch_all(self) -> dict[str, ConnectorResult]:
        results = {}
        for cid, connector in self._connectors.items():
            results[cid] = connector.fetch()
        return results

    def health_status(self) -> dict[str, str]:
        return {cid: c.health for cid, c in self._connectors.items()}

    @property
    def connector_count(self) -> int:
        return len(self._connectors)
