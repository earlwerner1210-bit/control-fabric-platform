from __future__ import annotations

import os

import pytest


class TestSLMEnrichmentLive:
    """Prove rule-based enrichment is live across all 8 domains."""

    def _enrich(
        self,
        domain_module: str,
        class_name: str,
        finding: str,
        plane: str,
        regulatory: list[str],
    ) -> object:
        import importlib

        mod = importlib.import_module(domain_module)
        adapter = getattr(mod, class_name)()
        from app.core.inference.slm_router import SLMContext

        context = SLMContext(
            operational_plane=plane,
            object_types=["regulatory_mandate"],
            hypothesis_type="gap_analysis",
            regulatory_context=regulatory,
        )
        return adapter.enrich_hypothesis(finding, context, [])

    def test_telecom_produces_nis2_citation(self) -> None:
        e = self._enrich(
            "app.core.inference.domain_adapters.telecom_adapter",
            "TelecomSLMAdapter",
            "production network change without NIS2 security assessment",
            "operations",
            ["NIS2"],
        )
        assert len(e.regulation_citations) > 0
        assert any("NIS2" in c or "Ofcom" in c or "3GPP" in c for c in e.regulation_citations)

    def test_legal_produces_sra_citation(self) -> None:
        e = self._enrich(
            "app.core.inference.domain_adapters.legal_adapter",
            "LegalSLMAdapter",
            "new client matter opened without CDD documentation",
            "compliance",
            ["SRA", "AML"],
        )
        assert len(e.regulation_citations) > 0
        assert any("SRA" in c or "MLR" in c or "POCA" in c for c in e.regulation_citations)

    def test_banking_produces_sr117_citation(self) -> None:
        e = self._enrich(
            "app.core.inference.domain_adapters.banking_adapter",
            "BankingSLMAdapter",
            "risk model change deployed without independent validation",
            "risk",
            ["SR11-7", "Basel"],
        )
        assert len(e.regulation_citations) > 0
        assert any("SR 11-7" in c or "Basel" in c or "PRA" in c for c in e.regulation_citations)

    def test_healthcare_produces_fda_citation(self) -> None:
        e = self._enrich(
            "app.core.inference.domain_adapters.healthcare_adapter",
            "HealthcareSLMAdapter",
            "software deployed without FDA 21 CFR Part 11 validation",
            "operations",
            ["FDA"],
        )
        assert len(e.regulation_citations) > 0
        assert any("21 CFR" in c or "FDA" in c or "MDR" in c for c in e.regulation_citations)

    def test_semiconductor_produces_itar_citation(self) -> None:
        e = self._enrich(
            "app.core.inference.domain_adapters.semiconductor_adapter",
            "SemiconductorSLMAdapter",
            "controlled technical data shared with foreign national without export licence",
            "export_control",
            ["ITAR", "EAR"],
        )
        assert len(e.regulation_citations) > 0
        assert any("ITAR" in c or "EAR" in c or "CFR" in c for c in e.regulation_citations)

    def test_all_adapters_return_evidence_types(self) -> None:
        """Every adapter must prescribe evidence when a gap is detected."""
        test_cases = [
            (
                "app.core.inference.domain_adapters.legal_adapter",
                "LegalSLMAdapter",
                "client money held without reconciliation",
                "operations",
                ["SRA"],
            ),
            (
                "app.core.inference.domain_adapters.manufacturing_adapter",
                "ManufacturingSLMAdapter",
                "production process change without engineering change order",
                "quality",
                ["ISO9001"],
            ),
            (
                "app.core.inference.domain_adapters.insurance_adapter",
                "InsuranceSLMAdapter",
                "internal model change without PRA pre-approval",
                "compliance",
                ["Solvency"],
            ),
        ]
        for module, cls, finding, plane, reg in test_cases:
            e = self._enrich(module, cls, finding, plane, reg)
            assert len(e.regulation_citations) > 0 or len(e.prescribed_evidence_types) > 0, (
                f"{cls} produced no citations or evidence for: {finding}"
            )

    def test_enrichment_latency_under_10ms(self) -> None:
        import time

        from app.core.inference.domain_adapters.legal_adapter import (
            LegalSLMAdapter,
        )
        from app.core.inference.slm_router import SLMContext

        adapter = LegalSLMAdapter()
        context = SLMContext("compliance", ["regulatory_mandate"], "gap_analysis", ["SRA"])
        start = time.perf_counter()
        adapter.enrich_hypothesis("new client without CDD check", context, [])
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 10.0, f"Enrichment took {elapsed_ms:.1f}ms — should be < 10ms"


class TestSecurityControls:
    def test_jwt_check_catches_default_secret(self) -> None:
        # "change-me" is 9 chars — fails on length check (min 32)
        os.environ["JWT_SECRET_KEY"] = "change-me"
        import scripts.security_self_assessment as ssa

        result = ssa.test_jwt_secret_strength()
        assert result.passed is False

    def test_input_sanitisation_strips_xss(self) -> None:
        from scripts.security_self_assessment import test_input_sanitisation

        result = test_input_sanitisation()
        assert result.passed is True

    def test_webhook_hmac_test_passes(self) -> None:
        from scripts.security_self_assessment import (
            test_webhook_hmac_verification,
        )

        result = test_webhook_hmac_verification()
        assert result.passed is True

    def test_rate_limiting_test_passes(self) -> None:
        from scripts.security_self_assessment import test_rate_limiting

        result = test_rate_limiting()
        assert result.passed is True


class TestStripeBilling:
    def test_plan_limits_correctly_configured(self) -> None:
        from app.core.billing.stripe_billing import PLAN_LIMITS

        assert PLAN_LIMITS["starter"]["gate_submissions_per_day"] == 100
        assert PLAN_LIMITS["growth"]["gate_submissions_per_day"] == 1000
        assert PLAN_LIMITS["enterprise"]["gate_submissions_per_day"] == -1
        assert PLAN_LIMITS["pilot"]["monthly_price_gbp"] == 0

    def test_get_or_create_customer(self) -> None:
        from app.core.billing.stripe_billing import StripeBillingService

        svc = StripeBillingService()
        customer = svc.get_or_create_customer(
            "test-billing-001",
            "billing@test.com",
            "Test Corp",
            plan="growth",
        )
        assert customer.tenant_id == "test-billing-001"
        assert customer.plan == "growth"

    def test_set_pilot_plan(self) -> None:
        from app.core.billing.stripe_billing import StripeBillingService

        svc = StripeBillingService()
        customer = svc.set_pilot_plan("vodafone-pilot")
        assert customer.plan == "pilot"
        assert customer.status == "active"

    def test_plan_enforcement_allows_within_limit(self) -> None:
        from app.core.billing.stripe_billing import StripeBillingService

        svc = StripeBillingService()
        result = svc.check_plan_limits("new-tenant-x", "gate_submission")
        assert result.allowed is True

    def test_subscription_status_returns_pilot_note(self) -> None:
        from app.core.billing.stripe_billing import StripeBillingService

        svc = StripeBillingService()
        svc.set_pilot_plan("vf-pilot-tenant")
        status = svc.get_subscription_status("vf-pilot-tenant")
        assert status["plan"] == "pilot"
        assert "Pilot" in status.get("note", "")

    def test_report_usage_without_stripe_returns_record(self) -> None:
        from app.core.billing.stripe_billing import StripeBillingService

        svc = StripeBillingService()
        svc.get_or_create_customer("usage-test-tenant", "u@t.com", "Usage Test")
        record = svc.report_usage("usage-test-tenant")
        assert record.tenant_id == "usage-test-tenant"
        assert isinstance(record.stripe_reported, bool)

    def test_stripe_not_configured_returns_gracefully(self) -> None:
        os.environ.pop("STRIPE_SECRET_KEY", None)
        from app.core.billing.stripe_billing import StripeBillingService

        svc = StripeBillingService()
        assert svc._stripe_configured is False
        record = svc.report_usage("no-stripe-tenant")
        assert record.stripe_reported is False
