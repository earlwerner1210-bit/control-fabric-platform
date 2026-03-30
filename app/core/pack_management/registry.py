"""Pack Management Registry — install, uninstall, upgrade, diff."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from .domain_types import (
    PackDiff,
    PackInstallRequest,
    PackManifest,
    PackStatus,
    PackVersion,
)

logger = logging.getLogger(__name__)


def _build_builtin_manifests() -> list[PackManifest]:
    """Return manifests for built-in domain packs."""
    return [
        PackManifest(
            pack_id="telco-ops",
            pack_name="Telco Operations",
            version=PackVersion(major=1, minor=0, patch=0),
            description="Telecom operational controls and reconciliation rules",
            namespaces=["telco.network", "telco.billing", "telco.provisioning"],
            rule_count=5,
            schema_count=3,
        ),
        PackManifest(
            pack_id="contract-margin",
            pack_name="Contract Margin Assurance",
            version=PackVersion(major=1, minor=0, patch=0),
            description="Contract lifecycle and margin drift detection",
            namespaces=["contract.terms", "contract.pricing", "contract.obligations"],
            rule_count=4,
            schema_count=3,
        ),
        PackManifest(
            pack_id="release-governance",
            pack_name="Release Governance",
            version=PackVersion(major=1, minor=0, patch=0),
            description="Release gate and evidence-based governance",
            namespaces=[
                "release.pipeline",
                "release.evidence",
                "release.approval",
            ],
            rule_count=3,
            schema_count=3,
        ),
    ]


class PackRegistry:
    """Manages domain pack lifecycle."""

    def __init__(self) -> None:
        self._manifests: dict[str, PackManifest] = {}
        self._status: dict[str, PackStatus] = {}
        self._install_log: list[dict[str, str]] = []

        for m in _build_builtin_manifests():
            self._manifests[m.pack_id] = m
            self._status[m.pack_id] = PackStatus.AVAILABLE

    # ── queries ─────────────────────────────────────────────

    def list_packs(self) -> list[dict[str, object]]:
        return [
            {
                "pack_id": pid,
                "pack_name": m.pack_name,
                "version": str(m.version),
                "status": self._status[pid].value,
                "rule_count": m.rule_count,
            }
            for pid, m in self._manifests.items()
        ]

    def get_manifest(self, pack_id: str) -> PackManifest | None:
        return self._manifests.get(pack_id)

    def get_status(self, pack_id: str) -> PackStatus | None:
        return self._status.get(pack_id)

    # ── lifecycle ───────────────────────────────────────────

    def install(self, request: PackInstallRequest) -> dict[str, str]:
        manifest = self._manifests.get(request.pack_id)
        if not manifest:
            raise ValueError(f"Unknown pack: {request.pack_id}")

        current = self._status.get(request.pack_id)
        if current == PackStatus.INSTALLED and not request.force:
            raise ValueError(
                f"Pack {request.pack_id} already installed. Use force=True to reinstall"
            )

        # Check dependencies
        for dep in manifest.dependencies:
            if self._status.get(dep) != PackStatus.INSTALLED:
                raise ValueError(f"Dependency not installed: {dep}")

        self._status[request.pack_id] = PackStatus.INSTALLED
        entry = {
            "action": "install",
            "pack_id": request.pack_id,
            "version": str(manifest.version),
            "environment": request.target_environment,
            "requested_by": request.requested_by,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._install_log.append(entry)
        logger.info("Installed pack %s v%s", request.pack_id, manifest.version)
        return entry

    def uninstall(self, pack_id: str, requested_by: str = "system") -> dict[str, str]:
        if self._status.get(pack_id) != PackStatus.INSTALLED:
            raise ValueError(f"Pack {pack_id} is not installed")

        # Check reverse dependencies
        for pid, m in self._manifests.items():
            if pack_id in m.dependencies and self._status.get(pid) == PackStatus.INSTALLED:
                raise ValueError(f"Cannot uninstall: pack {pid} depends on {pack_id}")

        self._status[pack_id] = PackStatus.AVAILABLE
        entry = {
            "action": "uninstall",
            "pack_id": pack_id,
            "requested_by": requested_by,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._install_log.append(entry)
        return entry

    def upgrade(self, pack_id: str, new_manifest: PackManifest) -> PackDiff:
        old = self._manifests.get(pack_id)
        if not old:
            raise ValueError(f"Unknown pack: {pack_id}")

        if not new_manifest.version.is_compatible_with(old.version):
            self._status[pack_id] = PackStatus.INCOMPATIBLE
            raise ValueError(f"Incompatible major version: {old.version} → {new_manifest.version}")

        diff = PackDiff(
            pack_id=pack_id,
            from_version=str(old.version),
            to_version=str(new_manifest.version),
            breaking=not new_manifest.version.is_compatible_with(old.version),
        )
        self._manifests[pack_id] = new_manifest
        self._status[pack_id] = PackStatus.INSTALLED
        logger.info("Upgraded pack %s: %s → %s", pack_id, old.version, new_manifest.version)
        return diff

    def check_compatibility(self, pack_id: str, target_version: PackVersion) -> bool:
        current = self._manifests.get(pack_id)
        if not current:
            return False
        return target_version.is_compatible_with(current.version)

    def get_install_log(self) -> list[dict[str, str]]:
        return list(self._install_log)
