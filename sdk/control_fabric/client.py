"""
Control Fabric Platform Python SDK.

Usage:
    from control_fabric import ControlFabricClient

    client = ControlFabricClient(base_url="http://localhost:8000")
    client.login("admin", "admin")

    cases = client.cases.list()
    client.reconciliation.run()
"""

from __future__ import annotations

from typing import Any

import httpx


class _Resource:
    def __init__(self, client: ControlFabricClient) -> None:
        self._c = client

    def _get(self, path: str, **params: Any) -> Any:
        resp = self._c._session.get(f"{self._c.base_url}{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict | None = None) -> Any:
        resp = self._c._session.post(f"{self._c.base_url}{path}", json=data)
        resp.raise_for_status()
        return resp.json()


class CasesResource(_Resource):
    def list(self) -> dict:
        return self._get("/reconciliation/cases")

    def get(self, case_id: str) -> dict:
        return self._get(f"/reconciliation/cases/{case_id}")

    def resolve(self, case_id: str, resolved_by: str, note: str) -> dict:
        return self._post(
            f"/reconciliation/cases/{case_id}/resolve"
            f"?resolved_by={resolved_by}&resolution_note={note}"
        )


class ReconciliationResource(_Resource):
    def run(self) -> dict:
        return self._post("/reconciliation/run")

    def rules(self) -> dict:
        return self._get("/reconciliation/rules")


class IngressResource(_Resource):
    def stats(self) -> dict:
        return self._get("/ingress/stats")

    def get_object(self, object_id: str) -> dict:
        return self._get(f"/ingress/objects/{object_id}")

    def get_history(self, object_id: str) -> dict:
        return self._get(f"/ingress/objects/{object_id}/history")

    def ingest(
        self,
        source_system: str,
        content: str,
        operational_plane: str,
        format: str = "json",
        submitted_by: str = "sdk",
    ) -> dict:
        return self._post(
            "/ingress/ingest",
            {
                "source_system": source_system,
                "content": content,
                "operational_plane": operational_plane,
                "format": format,
                "submitted_by": submitted_by,
            },
        )


class ExceptionsResource(_Resource):
    def list_active(self) -> dict:
        return self._get("/exceptions/active")

    def get_audit(self, exception_id: str) -> dict:
        return self._get(f"/exceptions/{exception_id}/audit")


class AlertsResource(_Resource):
    def test(self, severity: str = "critical") -> dict:
        return self._post("/alerts/test", {"severity": severity})

    def history(self) -> dict:
        return self._get("/alerts/history")


class AuditResource(_Resource):
    def export_json(self) -> dict:
        return self._get("/audit/export/json")

    def manifest(self) -> dict:
        return self._get("/audit/export/manifest")


class ControlFabricClient:
    """
    Control Fabric Platform SDK client.

    Example:
        client = ControlFabricClient("http://localhost:8000")
        client.login("admin", "admin")
        cases = client.cases.list()
    """

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = httpx.Client(timeout=timeout)
        self.cases = CasesResource(self)
        self.reconciliation = ReconciliationResource(self)
        self.ingress = IngressResource(self)
        self.exceptions = ExceptionsResource(self)
        self.alerts = AlertsResource(self)
        self.audit = AuditResource(self)

    def login(self, username: str, password: str, tenant_id: str = "default") -> dict:
        resp = self._session.post(
            f"{self.base_url}/auth/login",
            json={
                "username": username,
                "password": password,
                "tenant_id": tenant_id,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._session.headers.update({"Authorization": f"Bearer {data['access_token']}"})
        return data

    def health(self) -> dict:
        resp = self._session.get(f"{self.base_url}/health")
        return resp.json()

    def __enter__(self) -> ControlFabricClient:
        return self

    def __exit__(self, *args: object) -> None:
        self._session.close()
