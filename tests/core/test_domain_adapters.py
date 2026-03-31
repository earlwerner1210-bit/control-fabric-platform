"""Tests for all domain SLM adapters — routing, enrichment, and registration."""

from __future__ import annotations

from app.core.inference.slm_router import SLMContext, SLMRouter


def make_context(plane: str, regulatory: list[str] | None = None) -> SLMContext:
    return SLMContext(
        operational_plane=plane,
        object_types=["regulatory_mandate"],
        hypothesis_type="gap_analysis",
        regulatory_context=regulatory or [],
    )


class TestLegalAdapter:
    def test_routes_for_compliance_plane(self) -> None:
        from app.core.inference.domain_adapters.legal_adapter import LegalSLMAdapter

        router = SLMRouter()
        router.register(LegalSLMAdapter())
        adapter = router.route(make_context("compliance", ["SRA"]))
        assert adapter.adapter_id == "legal-v1"

    def test_enriches_aml_gap(self) -> None:
        from app.core.inference.domain_adapters.legal_adapter import LegalSLMAdapter

        router = SLMRouter()
        router.register(LegalSLMAdapter())
        enrichment = router.enrich(
            "new client matter opened without completed aml check and CDD documentation",
            make_context("compliance", ["SRA", "AML"]),
            [],
        )
        assert len(enrichment.regulation_citations) > 0
        assert any("MLR" in c or "POCA" in c or "SRA" in c for c in enrichment.regulation_citations)

    def test_client_money_gap_produces_high_confidence(self) -> None:
        from app.core.inference.domain_adapters.legal_adapter import LegalSLMAdapter

        adapter = LegalSLMAdapter()
        enrichment = adapter.enrich_hypothesis(
            "client money held without proper client account reconciliation",
            make_context("operations"),
            [],
        )
        assert enrichment.confidence_boost > 0
        assert len(enrichment.prescribed_evidence_types) > 0


class TestHealthcareAdapter:
    def test_routes_for_fda_context(self) -> None:
        from app.core.inference.domain_adapters.healthcare_adapter import (
            HealthcareSLMAdapter,
        )

        router = SLMRouter()
        router.register(HealthcareSLMAdapter())
        adapter = router.route(make_context("compliance", ["FDA"]))
        assert adapter.adapter_id == "healthcare-v1"

    def test_enriches_software_validation_gap(self) -> None:
        from app.core.inference.domain_adapters.healthcare_adapter import (
            HealthcareSLMAdapter,
        )

        adapter = HealthcareSLMAdapter()
        enrichment = adapter.enrich_hypothesis(
            "software release deployed without 21 CFR Part 11 validation documentation",
            make_context("operations", ["FDA"]),
            [],
        )
        assert any("21 CFR" in c for c in enrichment.regulation_citations)
        assert "validation_protocol" in enrichment.prescribed_evidence_types

    def test_hipaa_phi_gap_detected(self) -> None:
        from app.core.inference.domain_adapters.healthcare_adapter import (
            HealthcareSLMAdapter,
        )

        adapter = HealthcareSLMAdapter()
        enrichment = adapter.enrich_hypothesis(
            "PHI patient data shared with vendor without BAA business associate agreement",
            make_context("security", ["HIPAA"]),
            [],
        )
        assert any("HIPAA" in c for c in enrichment.regulation_citations)


class TestBankingAdapter:
    def test_routes_for_sr117_context(self) -> None:
        from app.core.inference.domain_adapters.banking_adapter import BankingSLMAdapter

        router = SLMRouter()
        router.register(BankingSLMAdapter())
        adapter = router.route(make_context("risk", ["SR11-7"]))
        assert adapter.adapter_id == "banking-v1"

    def test_model_change_gap_detected(self) -> None:
        from app.core.inference.domain_adapters.banking_adapter import BankingSLMAdapter

        adapter = BankingSLMAdapter()
        enrichment = adapter.enrich_hypothesis(
            "risk model change deployed to production without independent validation report",
            make_context("risk", ["SR11-7", "Basel"]),
            [],
        )
        assert any("SR 11-7" in c for c in enrichment.regulation_citations)
        assert "independent_validation_report" in enrichment.prescribed_evidence_types

    def test_bcbs239_data_gap_detected(self) -> None:
        from app.core.inference.domain_adapters.banking_adapter import BankingSLMAdapter

        adapter = BankingSLMAdapter()
        enrichment = adapter.enrich_hypothesis(
            "risk report submitted with unreconciled data quality issues",
            make_context("compliance", ["BCBS"]),
            [],
        )
        assert any("BCBS 239" in c for c in enrichment.regulation_citations)


class TestInsuranceAdapter:
    def test_routes_for_solvency_context(self) -> None:
        from app.core.inference.domain_adapters.insurance_adapter import (
            InsuranceSLMAdapter,
        )

        router = SLMRouter()
        router.register(InsuranceSLMAdapter())
        adapter = router.route(make_context("risk", ["Solvency"]))
        assert adapter.adapter_id == "insurance-v1"

    def test_internal_model_change_flagged(self) -> None:
        from app.core.inference.domain_adapters.insurance_adapter import (
            InsuranceSLMAdapter,
        )

        adapter = InsuranceSLMAdapter()
        enrichment = adapter.enrich_hypothesis(
            "internal model change deployed without PRA pre-approval for major change",
            make_context("compliance", ["Solvency"]),
            [],
        )
        assert any("Solvency II" in c for c in enrichment.regulation_citations)
        assert enrichment.confidence_boost > 0.20

    def test_lloyds_delegated_gap_detected(self) -> None:
        from app.core.inference.domain_adapters.insurance_adapter import (
            InsuranceSLMAdapter,
        )

        adapter = InsuranceSLMAdapter()
        enrichment = adapter.enrich_hypothesis(
            "syndicate delegated authority arrangement changed without Lloyd's approval",
            make_context("compliance", ["Lloyd's"]),
            [],
        )
        assert any("Lloyd's" in c for c in enrichment.regulation_citations)


class TestManufacturingAdapter:
    def test_routes_for_quality_plane(self) -> None:
        from app.core.inference.domain_adapters.manufacturing_adapter import (
            ManufacturingSLMAdapter,
        )

        router = SLMRouter()
        router.register(ManufacturingSLMAdapter())
        adapter = router.route(make_context("quality", ["ISO9001"]))
        assert adapter.adapter_id == "manufacturing-v1"

    def test_process_change_gap_detected(self) -> None:
        from app.core.inference.domain_adapters.manufacturing_adapter import (
            ManufacturingSLMAdapter,
        )

        adapter = ManufacturingSLMAdapter()
        enrichment = adapter.enrich_hypothesis(
            "production change implemented without engineering change order and PFMEA update",
            make_context("quality", ["ISO9001", "IATF"]),
            [],
        )
        assert any("ISO 9001" in c or "IATF" in c for c in enrichment.regulation_citations)
        assert "engineering_change_order" in enrichment.prescribed_evidence_types

    def test_ics_security_gap_detected(self) -> None:
        from app.core.inference.domain_adapters.manufacturing_adapter import (
            ManufacturingSLMAdapter,
        )

        adapter = ManufacturingSLMAdapter()
        enrichment = adapter.enrich_hypothesis(
            "ICS patch deployed to industrial control system network without security assessment",
            make_context("security", ["IEC62443"]),
            [],
        )
        assert any("IEC 62443" in c for c in enrichment.regulation_citations)


class TestSemiconductorAdapter:
    def test_routes_for_export_control_plane(self) -> None:
        from app.core.inference.domain_adapters.semiconductor_adapter import (
            SemiconductorSLMAdapter,
        )

        router = SLMRouter()
        router.register(SemiconductorSLMAdapter())
        adapter = router.route(make_context("export_control", ["ITAR"]))
        assert adapter.adapter_id == "semiconductor-v1"

    def test_itar_gap_produces_highest_confidence(self) -> None:
        from app.core.inference.domain_adapters.semiconductor_adapter import (
            SemiconductorSLMAdapter,
        )

        adapter = SemiconductorSLMAdapter()
        enrichment = adapter.enrich_hypothesis(
            "controlled technical data shared with foreign national without export licence",
            make_context("export_control", ["ITAR", "EAR"]),
            [],
        )
        assert any("ITAR" in c or "EAR" in c for c in enrichment.regulation_citations)
        assert enrichment.confidence_boost >= 0.20
        assert "denied_party_screening" in enrichment.prescribed_evidence_types

    def test_ip_release_gap_detected(self) -> None:
        from app.core.inference.domain_adapters.semiconductor_adapter import (
            SemiconductorSLMAdapter,
        )

        adapter = SemiconductorSLMAdapter()
        enrichment = adapter.enrich_hypothesis(
            "ip release of technical patent invention disclosed publicly"
            " before patent filing completed",
            make_context("ip_governance", []),
            [],
        )
        assert len(enrichment.regulation_citations) > 0
        assert "patent_clearance" in enrichment.prescribed_evidence_types

    def test_jedec_pcn_gap_detected(self) -> None:
        from app.core.inference.domain_adapters.semiconductor_adapter import (
            SemiconductorSLMAdapter,
        )

        adapter = SemiconductorSLMAdapter()
        enrichment = adapter.enrich_hypothesis(
            "semiconductor process change deployed without JEDEC PCN product change"
            " notification to customers",
            make_context("compliance", ["JEDEC"]),
            [],
        )
        assert any("JEDEC" in c for c in enrichment.regulation_citations)


class TestAllAdaptersRegistered:
    def test_all_eight_adapters_register_cleanly(self) -> None:
        from app.core.inference.domain_adapters.banking_adapter import BankingSLMAdapter
        from app.core.inference.domain_adapters.finserv_adapter import FinServSLMAdapter
        from app.core.inference.domain_adapters.healthcare_adapter import (
            HealthcareSLMAdapter,
        )
        from app.core.inference.domain_adapters.insurance_adapter import (
            InsuranceSLMAdapter,
        )
        from app.core.inference.domain_adapters.legal_adapter import LegalSLMAdapter
        from app.core.inference.domain_adapters.manufacturing_adapter import (
            ManufacturingSLMAdapter,
        )
        from app.core.inference.domain_adapters.semiconductor_adapter import (
            SemiconductorSLMAdapter,
        )
        from app.core.inference.domain_adapters.telecom_adapter import (
            TelecomSLMAdapter,
        )

        router = SLMRouter()
        for adapter in [
            TelecomSLMAdapter(),
            FinServSLMAdapter(),
            LegalSLMAdapter(),
            HealthcareSLMAdapter(),
            BankingSLMAdapter(),
            InsuranceSLMAdapter(),
            ManufacturingSLMAdapter(),
            SemiconductorSLMAdapter(),
        ]:
            router.register(adapter)

        assert router.adapter_count == 8
        listings = router.list_adapters()
        adapter_ids = [a["adapter_id"] for a in listings]
        for expected in [
            "telecom-v1",
            "finserv-v1",
            "legal-v1",
            "healthcare-v1",
            "banking-v1",
            "insurance-v1",
            "manufacturing-v1",
            "semiconductor-v1",
        ]:
            assert expected in adapter_ids

    def test_each_adapter_handles_its_own_context(self) -> None:
        """Each adapter's can_handle returns True for its regulatory context."""
        from app.core.inference.domain_adapters.banking_adapter import BankingSLMAdapter
        from app.core.inference.domain_adapters.healthcare_adapter import (
            HealthcareSLMAdapter,
        )
        from app.core.inference.domain_adapters.insurance_adapter import (
            InsuranceSLMAdapter,
        )
        from app.core.inference.domain_adapters.legal_adapter import LegalSLMAdapter
        from app.core.inference.domain_adapters.manufacturing_adapter import (
            ManufacturingSLMAdapter,
        )
        from app.core.inference.domain_adapters.semiconductor_adapter import (
            SemiconductorSLMAdapter,
        )
        from app.core.inference.domain_adapters.telecom_adapter import (
            TelecomSLMAdapter,
        )

        cases = [
            (TelecomSLMAdapter(), make_context("network", ["NIS2"]), "telecom-v1"),
            (LegalSLMAdapter(), make_context("compliance", ["SRA"]), "legal-v1"),
            (HealthcareSLMAdapter(), make_context("compliance", ["FDA"]), "healthcare-v1"),
            (BankingSLMAdapter(), make_context("risk", ["SR11-7"]), "banking-v1"),
            (InsuranceSLMAdapter(), make_context("risk", ["Solvency"]), "insurance-v1"),
            (ManufacturingSLMAdapter(), make_context("quality", ["ISO9001"]), "manufacturing-v1"),
            (
                SemiconductorSLMAdapter(),
                make_context("export_control", ["ITAR"]),
                "semiconductor-v1",
            ),
        ]
        for adapter, context, expected_id in cases:
            assert adapter.can_handle(context), (
                f"{expected_id} should handle {context.regulatory_context}"
            )
            assert adapter.adapter_id == expected_id

    def test_unambiguous_routing(self) -> None:
        """Adapters with unique planes route correctly."""
        from app.core.inference.domain_adapters.manufacturing_adapter import (
            ManufacturingSLMAdapter,
        )
        from app.core.inference.domain_adapters.semiconductor_adapter import (
            SemiconductorSLMAdapter,
        )
        from app.core.inference.domain_adapters.telecom_adapter import (
            TelecomSLMAdapter,
        )

        router = SLMRouter()
        for a in [
            TelecomSLMAdapter(),
            ManufacturingSLMAdapter(),
            SemiconductorSLMAdapter(),
        ]:
            router.register(a)

        # These planes are unique to their respective adapters
        assert router.route(make_context("network", [])).adapter_id == "telecom-v1"
        assert router.route(make_context("safety", [])).adapter_id == "manufacturing-v1"
        assert router.route(make_context("export_control", [])).adapter_id == "semiconductor-v1"
