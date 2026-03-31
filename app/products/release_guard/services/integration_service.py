"""Integration service — connect GitHub, Jira, Slack."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from app.products.release_guard.domain.enums import IntegrationProvider
from app.products.release_guard.domain.models import Integration

logger = logging.getLogger(__name__)

_integrations: dict[str, Integration] = {}  # workspace_id:provider -> Integration


class IntegrationService:
    def connect(
        self,
        workspace_id: str,
        provider: IntegrationProvider,
        config: dict,
        connected_by: str,
    ) -> Integration:
        key = f"{workspace_id}:{provider.value}"
        integration = Integration(
            workspace_id=workspace_id,
            provider=provider,
            config={k: v for k, v in config.items() if k not in ("token", "secret", "password")},
            connected_by=connected_by,
            connected_at=datetime.now(UTC).isoformat(),
        )
        # Test connection
        ok, detail = self._test_connection(provider, config)
        integration.status = "connected" if ok else "error"
        integration.error_message = detail if not ok else None
        _integrations[key] = integration
        logger.info("Integration %s: %s — %s", provider.value, workspace_id[:8], integration.status)
        return integration

    def disconnect(self, workspace_id: str, provider: IntegrationProvider) -> None:
        key = f"{workspace_id}:{provider.value}"
        if key in _integrations:
            _integrations[key].status = "disconnected"

    def get(self, workspace_id: str, provider: IntegrationProvider) -> Integration | None:
        return _integrations.get(f"{workspace_id}:{provider.value}")

    def list_for_workspace(self, workspace_id: str) -> list[Integration]:
        return [v for k, v in _integrations.items() if k.startswith(f"{workspace_id}:")]

    def test(self, workspace_id: str, provider: IntegrationProvider) -> dict:
        integration = self.get(workspace_id, provider)
        if not integration:
            return {"connected": False, "detail": "Integration not configured"}
        ok, detail = self._test_connection(provider, integration.config)
        integration.status = "connected" if ok else "error"
        integration.error_message = None if ok else detail
        return {"connected": ok, "detail": detail, "provider": provider.value}

    def _test_connection(self, provider: IntegrationProvider, config: dict) -> tuple[bool, str]:
        """Test connectivity for each provider."""
        if provider == IntegrationProvider.GITHUB:
            token = config.get("token") or os.getenv("GITHUB_TOKEN", "")
            if not token:
                return False, "GitHub token not provided"
            try:
                import httpx

                r = httpx.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5,
                )
                if r.status_code == 200:
                    user = r.json().get("login", "unknown")
                    return True, f"Connected as {user}"
                return False, f"GitHub API returned {r.status_code}"
            except Exception as e:
                return False, f"Connection failed: {str(e)[:60]}"

        elif provider == IntegrationProvider.JIRA:
            base_url = config.get("base_url", "")
            if not base_url:
                return False, "Jira base URL not provided"
            try:
                import base64

                import httpx

                email = config.get("email", "")
                token = config.get("token") or os.getenv("JIRA_TOKEN", "")
                auth = base64.b64encode(f"{email}:{token}".encode()).decode()
                r = httpx.get(
                    f"{base_url}/rest/api/3/myself",
                    headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
                    timeout=5,
                )
                if r.status_code == 200:
                    name = r.json().get("displayName", "unknown")
                    return True, f"Connected as {name}"
                return False, f"Jira API returned {r.status_code}"
            except Exception as e:
                return False, f"Connection failed: {str(e)[:60]}"

        elif provider == IntegrationProvider.SLACK:
            webhook = config.get("webhook_url", "")
            if not webhook:
                return False, "Slack webhook URL not provided"
            return True, "Slack webhook configured — will be verified on first notification"

        return True, "Integration configured"


integration_service = IntegrationService()
