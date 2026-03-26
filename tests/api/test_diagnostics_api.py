"""API tests for diagnostics routes."""

from __future__ import annotations

from app.api.routes.diagnostics import (
    DatabaseHealth,
    ServiceHealth,
    SystemInfo,
)


class TestDiagnosticsSchemas:
    """Test diagnostics response schemas."""

    def test_system_info(self):
        info = SystemInfo(
            app_name="Control Fabric Platform",
            app_version="0.1.0",
            environment="dev",
            python_version="3.11.0",
            platform="Linux",
            timestamp="2026-03-25T12:00:00Z",
        )
        assert info.app_name == "Control Fabric Platform"
        assert info.environment == "dev"

    def test_database_health_connected(self):
        health = DatabaseHealth(connected=True, pool_size=20, pool_checked_out=5)
        assert health.connected is True
        assert health.pool_size == 20

    def test_database_health_disconnected(self):
        health = DatabaseHealth(connected=False)
        assert health.connected is False
        assert health.pool_size == 0

    def test_service_health(self):
        health = ServiceHealth(
            system=SystemInfo(
                app_name="CFP",
                app_version="0.1.0",
                environment="dev",
                python_version="3.11",
                platform="Linux",
                timestamp="2026-03-25T12:00:00Z",
            ),
            database=DatabaseHealth(connected=True, pool_size=20),
            metrics_snapshot={"requests_total": 1000},
            domain_packs=["contract_margin", "utilities_field", "telco_ops"],
        )
        assert health.database.connected is True
        assert len(health.domain_packs) == 3
        assert "contract_margin" in health.domain_packs

    def test_service_health_defaults(self):
        health = ServiceHealth(
            system=SystemInfo(
                app_name="CFP",
                app_version="0.1.0",
                environment="dev",
                python_version="3.11",
                platform="Linux",
                timestamp="2026-03-25T12:00:00Z",
            ),
            database=DatabaseHealth(connected=True),
        )
        assert health.metrics_snapshot == {}
        assert health.domain_packs == []
