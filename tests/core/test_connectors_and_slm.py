"""Tests for real connectors, SLM router, domain adapters, and pack certification."""

from __future__ import annotations


class TestGitHubConnector:
    def test_connector_init(self) -> None:
        from app.core.connectors.github_connector import GitHubActionsConnector

        c = GitHubActionsConnector("gh-test", "myorg", "myrepo")
        assert c.owner == "myorg"
        assert c.repo == "myrepo"
        assert c.source_system == "github/myorg/myrepo"

    def test_connector_no_token_returns_error(self) -> None:
        from app.core.connectors.github_connector import GitHubActionsConnector

        c = GitHubActionsConnector("gh-test", "myorg", "myrepo", token="")
        result = c.fetch()
        assert not result.success
        assert len(result.errors) > 0


class TestJiraConnector:
    def test_connector_init(self) -> None:
        from app.core.connectors.jira_connector import JiraConnector

        c = JiraConnector("jira-test", "https://myorg.atlassian.net", project_key="CR")
        assert c.project_key == "CR"

    def test_connector_no_token_returns_error(self) -> None:
        from app.core.connectors.jira_connector import JiraConnector

        c = JiraConnector("jira-test", "https://myorg.atlassian.net", api_token="")
        result = c.fetch()
        assert not result.success


class TestServiceNowConnector:
    def test_connector_no_credentials_returns_error(self) -> None:
        from app.core.connectors.servicenow_connector import ServiceNowConnector

        c = ServiceNowConnector("snow-test", "myorg.service-now.com", username="")
        result = c.fetch()
        assert not result.success


class TestSLMRouter:
    def test_router_registers_adapters(self) -> None:
        from app.core.inference.domain_adapters.telecom_adapter import (
            TelecomSLMAdapter,
        )
        from app.core.inference.slm_router import SLMRouter

        router = SLMRouter()
        router.register(TelecomSLMAdapter())
        assert router.adapter_count == 1

    def test_telecom_adapter_routes_for_operations_plane(self) -> None:
        from app.core.inference.domain_adapters.telecom_adapter import (
            TelecomSLMAdapter,
        )
        from app.core.inference.slm_router import SLMContext, SLMRouter

        router = SLMRouter()
        router.register(TelecomSLMAdapter())
        context = SLMContext(
            operational_plane="operations",
            object_types=["domain_pack_extension"],
            hypothesis_type="gap_analysis",
        )
        adapter = router.route(context)
        assert adapter.adapter_id == "telecom-v1"

    def test_generic_fallback_for_unknown_plane(self) -> None:
        from app.core.inference.domain_adapters.telecom_adapter import (
            TelecomSLMAdapter,
        )
        from app.core.inference.slm_router import SLMContext, SLMRouter

        router = SLMRouter()
        router.register(TelecomSLMAdapter())
        context = SLMContext(
            operational_plane="completely_unknown_plane",
            object_types=[],
            hypothesis_type="gap_analysis",
        )
        adapter = router.route(context)
        assert adapter.adapter_id == "base"

    def test_telecom_enrichment_produces_nis2_citations(self) -> None:
        from app.core.inference.domain_adapters.telecom_adapter import (
            TelecomSLMAdapter,
        )
        from app.core.inference.slm_router import SLMContext, SLMRouter

        router = SLMRouter()
        router.register(TelecomSLMAdapter())
        context = SLMContext(
            operational_plane="operations",
            object_types=["domain_pack_extension"],
            hypothesis_type="gap_analysis",
        )
        enrichment = router.enrich(
            "production release has no network_change evidence and no security scan",
            context,
            [],
        )
        assert len(enrichment.regulation_citations) > 0
        assert any("NIS2" in c for c in enrichment.regulation_citations)

    def test_finserv_enrichment_produces_fca_citations(self) -> None:
        from app.core.inference.domain_adapters.finserv_adapter import (
            FinServSLMAdapter,
        )
        from app.core.inference.slm_router import SLMContext, SLMRouter

        router = SLMRouter()
        router.register(FinServSLMAdapter())
        context = SLMContext(
            operational_plane="compliance",
            object_types=["regulatory_mandate"],
            hypothesis_type="gap_analysis",
            regulatory_context=["FCA"],
        )
        enrichment = router.enrich(
            "production release without change approval and impact assessment",
            context,
            [],
        )
        assert len(enrichment.regulation_citations) > 0

    def test_enrichment_provides_remediation_precision(self) -> None:
        from app.core.inference.domain_adapters.telecom_adapter import (
            TelecomSLMAdapter,
        )
        from app.core.inference.slm_router import SLMContext, SLMRouter

        router = SLMRouter()
        router.register(TelecomSLMAdapter())
        context = SLMContext(
            operational_plane="operations",
            object_types=["domain_pack_extension"],
            hypothesis_type="gap_analysis",
        )
        enrichment = router.enrich(
            "production release missing security scan and network change evidence",
            context,
            [],
        )
        if enrichment.regulation_citations:
            assert len(enrichment.remediation_precision) > 0


class TestPackCertification:
    def test_valid_pack_certifies(self) -> None:
        from app.core.pack_management.certification import PackCertifier
        from app.domain_packs.release_governance.pack import RELEASE_GOVERNANCE_PACK

        certifier = PackCertifier()
        result = certifier.certify(RELEASE_GOVERNANCE_PACK)
        assert result.certified is True
        assert len(result.checks_passed) > 0
        assert len(result.certificate_id) == 16

    def test_invalid_version_fails_certification(self) -> None:
        from app.core.domain_pack_loader import DomainPack
        from app.core.pack_management.certification import PackCertifier

        bad_pack = DomainPack(
            pack_id="test-bad",
            name="Test Pack",
            version="not-semver",
            description=(
                "A test pack with a description that is long enough to pass the metadata check"
            ),
        )
        certifier = PackCertifier()
        result = certifier.certify(bad_pack)
        assert result.certified is False
        assert any("semver" in f for f in result.checks_failed)

    def test_empty_pack_fails_certification(self) -> None:
        from app.core.domain_pack_loader import DomainPack
        from app.core.pack_management.certification import PackCertifier

        empty = DomainPack(
            pack_id="empty",
            name="Empty",
            version="1.0.0",
            description=(
                "An empty pack that has no namespaces or rules"
                " and this description is now long enough"
            ),
        )
        certifier = PackCertifier()
        result = certifier.certify(empty)
        assert result.certified is False

    def test_breaking_change_detected(self) -> None:
        from app.core.domain_pack_loader import DomainPack, build_telco_ops_pack
        from app.core.pack_management.certification import PackCertifier

        original = build_telco_ops_pack()
        stripped = DomainPack(
            pack_id=original.pack_id,
            name=original.name,
            version="2.0.0",
            description=(original.description + " updated version with changes applied"),
        )
        certifier = PackCertifier()
        result = certifier.certify(stripped, previous_version=original)
        assert any("breaking" in f.lower() for f in result.checks_failed + result.warnings)

    def test_connector_registry_lists_all_types(self) -> None:
        from app.core.connectors.framework import (
            ConnectorRegistry,
            SimulatedCICDConnector,
        )

        registry = ConnectorRegistry()
        registry.register(SimulatedCICDConnector("ci-1"))
        assert registry.connector_count == 1
        health = registry.health_status()
        assert "ci-1" in health
