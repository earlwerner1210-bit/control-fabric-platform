"""API routes for the Pack Management System."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.pack_management import PackInstallRequest, PackRegistry

router = APIRouter(prefix="/packs", tags=["packs"])

_registry = PackRegistry()


@router.get("/")
async def list_packs() -> list[dict[str, object]]:
    """List all available domain packs."""
    return _registry.list_packs()


@router.get("/{pack_id}")
async def get_pack(pack_id: str) -> dict[str, object]:
    """Get pack manifest."""
    manifest = _registry.get_manifest(pack_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Pack not found")
    return {
        **manifest.model_dump(),
        "status": (_registry.get_status(pack_id) or "unknown"),
        "version": str(manifest.version),
    }


@router.post("/install")
async def install_pack(request: PackInstallRequest) -> dict[str, str]:
    """Install a domain pack."""
    try:
        return _registry.install(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{pack_id}/uninstall")
async def uninstall_pack(pack_id: str, requested_by: str = "system") -> dict[str, str]:
    """Uninstall a domain pack."""
    try:
        return _registry.uninstall(pack_id, requested_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/log/history")
async def install_log() -> list[dict[str, str]]:
    """Return the full install/uninstall log."""
    return _registry.get_install_log()
