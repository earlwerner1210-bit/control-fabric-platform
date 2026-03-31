"""
Pack ecosystem API — test harness, compatibility matrix, migration validator.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from app.core.pack_management.compatibility import PackCompatibilityMatrix
from app.core.pack_management.registry import PackRegistry
from app.core.pack_management.test_harness import PackTestHarness
from app.core.registry.schema_registry import SchemaRegistry

router = APIRouter(prefix="/pack-ecosystem", tags=["pack-ecosystem"])
_registry = PackRegistry(SchemaRegistry())
_harness = PackTestHarness()
_compat = PackCompatibilityMatrix()


@router.post("/test/{pack_id}")
def run_pack_tests(pack_id: str) -> dict:
    """Run the full test harness against a registered pack."""
    try:
        _registry.get_pack(pack_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    pack_obj = _registry._pack_objects.get(pack_id)
    if not pack_obj:
        raise HTTPException(
            status_code=404,
            detail=f"Pack object for {pack_id} not found",
        )

    report = _harness.run(pack_obj)
    return {
        "pack_id": pack_id,
        "overall_passed": report.overall_passed,
        "grade": report.grade,
        "passed": report.passed,
        "failed": report.failed,
        "total_tests": report.total_tests,
        "duration_ms": report.duration_ms,
        "results": [asdict(r) for r in report.results],
    }


@router.get("/compatibility")
def get_compatibility_matrix() -> dict:
    """Get full compatibility matrix for all registered packs."""
    packs = [
        _registry._pack_objects[entry.pack_id]
        for entry in _registry.list_packs()
        if entry.pack_id in _registry._pack_objects
    ]
    matrix = _compat.build_matrix(packs)
    return {
        "pack_count": len(packs),
        "pair_count": len(matrix),
        "matrix": matrix,
    }


@router.get("/compatibility/{pack_a_id}/{pack_b_id}")
def check_compatibility(pack_a_id: str, pack_b_id: str) -> dict:
    """Check if two packs can safely coexist."""
    pack_a = _registry._pack_objects.get(pack_a_id)
    pack_b = _registry._pack_objects.get(pack_b_id)
    if not pack_a:
        raise HTTPException(status_code=404, detail=f"Pack {pack_a_id} not found")
    if not pack_b:
        raise HTTPException(status_code=404, detail=f"Pack {pack_b_id} not found")
    report = _compat.check(pack_a, pack_b)
    return asdict(report)


@router.get("/health")
def get_ecosystem_health() -> dict:
    """Overall pack ecosystem health — all packs, test status."""
    packs = _registry.list_packs()
    results = []
    for entry in packs:
        pack_obj = _registry._pack_objects.get(entry.pack_id)
        if pack_obj:
            report = _harness.run(pack_obj)
            results.append(
                {
                    "pack_id": entry.pack_id,
                    "name": entry.name,
                    "version": entry.version,
                    "status": entry.status.value,
                    "test_grade": report.grade,
                    "tests_passed": report.passed,
                    "tests_total": report.total_tests,
                }
            )
    return {
        "total_packs": len(results),
        "all_healthy": all(r["test_grade"] in ("A", "B") for r in results),
        "packs": results,
    }
