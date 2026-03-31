"""SLM Router API — inspect registered domain adapters and test enrichment."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.inference.domain_adapters.finserv_adapter import FinServSLMAdapter
from app.core.inference.domain_adapters.telecom_adapter import TelecomSLMAdapter
from app.core.inference.slm_router import SLMContext, slm_router

router = APIRouter(prefix="/slm", tags=["slm"])

# Register domain adapters at startup
slm_router.register(TelecomSLMAdapter())
slm_router.register(FinServSLMAdapter())


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
