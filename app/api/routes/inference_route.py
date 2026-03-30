from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

# inference-gateway uses hyphens — not a valid Python package name
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "services" / "inference-gateway"))

from core.engine import BoundedInferenceEngine  # noqa: E402
from models.domain_types import InferenceRequest, InferenceResponse  # noqa: E402

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inference", tags=["inference"])

_engine = BoundedInferenceEngine(simulation_mode=True)


@router.post(
    "/infer",
    response_model=InferenceResponse,
    summary="Submit bounded inference request",
)
def infer(request: InferenceRequest) -> InferenceResponse:
    """
    Patent Claim (Theme 3): Policy-gated, scope-bounded AI inference.
    AI cannot produce executable output. Every session produces evidence record.
    """
    return _engine.infer(request)


@router.get("/audit/{session_id}", summary="Retrieve evidence records for a session")
def get_audit(session_id: str) -> dict:
    """Patent Claim (Theme 4): Full evidence chain for every inference session."""
    records = _engine.evidence_logger.get_session_records(session_id)
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No records for session {session_id}",
        )
    return {
        "session_id": session_id,
        "record_count": len(records),
        "records": [r.model_dump(mode="json") for r in records],
    }


@router.get("/audit/integrity/verify", summary="Verify evidence chain integrity")
def verify_integrity() -> dict:
    """Patent Claim (Theme 4): Cryptographic integrity verification of evidence chain."""
    return {
        "chain_valid": _engine.evidence_logger.verify_chain_integrity(),
        "total_records": _engine.evidence_logger.record_count,
    }
