"""SLM Router API — inspect registered domain adapters and test enrichment."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.inference.domain_adapters.banking_adapter import BankingSLMAdapter
from app.core.inference.domain_adapters.finserv_adapter import FinServSLMAdapter
from app.core.inference.domain_adapters.healthcare_adapter import HealthcareSLMAdapter
from app.core.inference.domain_adapters.insurance_adapter import InsuranceSLMAdapter
from app.core.inference.domain_adapters.legal_adapter import LegalSLMAdapter
from app.core.inference.domain_adapters.manufacturing_adapter import ManufacturingSLMAdapter
from app.core.inference.domain_adapters.semiconductor_adapter import SemiconductorSLMAdapter
from app.core.inference.domain_adapters.telecom_adapter import TelecomSLMAdapter
from app.core.inference.slm_router import SLMContext, slm_router

router = APIRouter(prefix="/slm", tags=["slm"])

# Register all domain adapters at startup
for _adapter in [
    TelecomSLMAdapter(),
    FinServSLMAdapter(),
    LegalSLMAdapter(),
    HealthcareSLMAdapter(),
    BankingSLMAdapter(),
    InsuranceSLMAdapter(),
    ManufacturingSLMAdapter(),
    SemiconductorSLMAdapter(),
]:
    slm_router.register(_adapter)


class EnrichRequest(BaseModel):
    hypothesis_text: str
    operational_plane: str
    object_types: list[str] = []
    regulatory_context: list[str] = []
    hypothesis_type: str = "gap_analysis"


@router.get("/adapters")
def list_adapters() -> dict:
    return {
        "adapter_count": slm_router.adapter_count,
        "adapters": slm_router.list_adapters(),
    }


@router.post("/enrich")
def enrich_hypothesis(req: EnrichRequest) -> dict:
    """Test domain SLM enrichment for a given hypothesis and context."""
    context = SLMContext(
        operational_plane=req.operational_plane,
        object_types=req.object_types,
        hypothesis_type=req.hypothesis_type,
        regulatory_context=req.regulatory_context,
    )
    adapter = slm_router.route(context)
    enrichment = slm_router.enrich(req.hypothesis_text, context, [])
    return {
        "adapter_used": adapter.adapter_id,
        "domain": adapter.domain_name,
        "regulation_citations": enrichment.regulation_citations,
        "specific_clause": enrichment.specific_clause,
        "domain_specific_risk": enrichment.domain_specific_risk,
        "prescribed_evidence_types": enrichment.prescribed_evidence_types,
        "remediation_precision": enrichment.remediation_precision,
        "confidence_boost": enrichment.confidence_boost,
        "enriched": len(enrichment.regulation_citations) > 0,
    }


DEMO_SCENARIOS = {
    "telecom": {
        "finding": "Production network change deployed without NIS2 security assessment",
        "plane": "operations",
        "regulatory_context": ["NIS2", "Ofcom"],
    },
    "legal": {
        "finding": "New client matter opened without completed CDD and AML checks",
        "plane": "compliance",
        "regulatory_context": ["SRA", "AML"],
    },
    "healthcare": {
        "finding": "Software release to clinical system without FDA 21 CFR Part 11 validation",
        "plane": "operations",
        "regulatory_context": ["FDA", "HIPAA"],
    },
    "banking": {
        "finding": "Risk model deployed without independent validation or MRC approval",
        "plane": "risk",
        "regulatory_context": ["SR11-7", "Basel"],
    },
    "insurance": {
        "finding": "Internal model change without PRA pre-approval",
        "plane": "compliance",
        "regulatory_context": ["Solvency"],
    },
    "manufacturing": {
        "finding": "Production process change without engineering change order",
        "plane": "quality",
        "regulatory_context": ["ISO9001", "IATF"],
    },
    "semiconductor": {
        "finding": "Controlled technical data shared with foreign national without export licence",
        "plane": "export_control",
        "regulatory_context": ["ITAR", "EAR"],
    },
    "finserv": {
        "finding": "Production release without change request or four-eyes approval",
        "plane": "operations",
        "regulatory_context": ["FCA", "DORA"],
    },
}


def _enrich_domain(domain: str, scenario: dict) -> dict:
    import time

    context = SLMContext(
        operational_plane=scenario["plane"],
        object_types=["regulatory_mandate"],
        hypothesis_type="gap_analysis",
        regulatory_context=scenario["regulatory_context"],
    )
    start = time.perf_counter()
    enrichment = slm_router.enrich(scenario["finding"], context, [])
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    adapter = slm_router.route(context)
    return {
        "domain": domain,
        "adapter_type": "rule_based",
        "finding": scenario["finding"],
        "regulation_citations": enrichment.regulation_citations,
        "specific_clause": enrichment.specific_clause,
        "domain_specific_risk": enrichment.domain_specific_risk,
        "prescribed_evidence_types": enrichment.prescribed_evidence_types,
        "remediation_precision": enrichment.remediation_precision,
        "latency_ms": latency_ms,
    }


@router.get("/demo")
def run_full_demo() -> dict:
    """Run enrichment demo across all 8 domains — live regulation citations."""
    results = []
    for domain, scenario in DEMO_SCENARIOS.items():
        try:
            results.append(_enrich_domain(domain, scenario))
        except Exception as e:
            results.append({"domain": domain, "error": str(e)})

    domains_with_citations = sum(1 for r in results if r.get("regulation_citations"))
    avg_latency = round(sum(r.get("latency_ms", 0) for r in results) / max(len(results), 1), 2)
    return {
        "status": "live",
        "adapter_type": "rule_based",
        "note": (
            "Rule-based enrichment active across all 8 domains."
            " GPU fine-tuned weights upgrade citation precision when loaded."
        ),
        "domains_tested": len(results),
        "domains_with_citations": domains_with_citations,
        "avg_latency_ms": avg_latency,
        "results": results,
    }


@router.get("/demo/{domain}")
def run_domain_demo(domain: str) -> dict:
    """Run enrichment demo for a single domain."""
    if domain not in DEMO_SCENARIOS:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Domain {domain} not found")
    try:
        return _enrich_domain(domain, DEMO_SCENARIOS[domain])
    except Exception as e:
        return {"domain": domain, "error": str(e)}


@router.get("/route")
def get_route(operational_plane: str, object_type: str = "") -> dict:
    """Show which domain adapter would be selected for a given context."""
    context = SLMContext(
        operational_plane=operational_plane,
        object_types=[object_type] if object_type else [],
        hypothesis_type="gap_analysis",
    )
    adapter = slm_router.route(context)
    return {
        "selected_adapter": adapter.adapter_id,
        "domain": adapter.domain_name,
        "regulatory_context": adapter.get_regulatory_context(operational_plane, [object_type]),
    }
