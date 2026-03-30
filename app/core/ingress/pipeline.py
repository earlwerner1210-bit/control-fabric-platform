from __future__ import annotations

import logging
from typing import Any

from app.core.graph.domain_types import ControlObject
from app.core.graph.store import ControlGraphStore
from app.core.ingress.domain_types import ArtefactFormat, RawArtefact
from app.core.ingress.normaliser import ArtefactNormaliser, NormalisationError
from app.core.platform_action_release_gate import ActionStatus, PlatformActionReleaseGate
from app.core.platform_validation_chain import ActionOrigin
from app.core.registry.object_registry import ObjectRegistry

logger = logging.getLogger(__name__)


class IngestResult:
    def __init__(self) -> None:
        self.ingested_objects: list[ControlObject] = []
        self.errors: list[str] = []
        self.artefact_id: str = ""
        self.evidence_package_ids: list[str] = []

    @property
    def success(self) -> bool:
        return len(self.ingested_objects) > 0 and len(self.errors) == 0

    @property
    def object_count(self) -> int:
        return len(self.ingested_objects)


class IngestPipeline:
    def __init__(
        self,
        registry: ObjectRegistry,
        graph: ControlGraphStore,
        normaliser: ArtefactNormaliser | None = None,
        release_gate: PlatformActionReleaseGate | None = None,
    ) -> None:
        self._registry = registry
        self._graph = graph
        self._normaliser = normaliser or ArtefactNormaliser()
        self._release_gate = release_gate

    def ingest(
        self,
        artefact: RawArtefact,
        operational_plane: str,
        ingested_by: str = "ingress-pipeline",
    ) -> IngestResult:
        result = IngestResult()
        result.artefact_id = artefact.artefact_id

        try:
            objects = self._normaliser.normalise_to_objects(artefact, operational_plane)
        except NormalisationError as e:
            result.errors.append(f"Normalisation failed: {e}")
            return result

        for obj in objects:
            try:
                # If gate is present, validate ingestion through it
                if self._release_gate is not None:
                    gate_result = self._release_gate.submit(
                        action_type="ingest_control_object",
                        proposed_payload={
                            "object_type": obj.object_type.value,
                            "name": obj.name,
                            "operational_plane": operational_plane,
                            "source_system": artefact.source_system,
                        },
                        requested_by=ingested_by,
                        origin=ActionOrigin.API_REQUEST,
                        evidence_references=[artefact.content_hash],
                        provenance_chain=[artefact.artefact_id],
                    )
                    if gate_result.status == ActionStatus.BLOCKED:
                        result.errors.append(
                            f"Gate blocked ingestion of '{obj.name}': {gate_result.failure_reason}"
                        )
                        continue
                    result.evidence_package_ids.append(gate_result.package_id)

                registered = self._registry.register(
                    obj,
                    registered_by=ingested_by,
                    reason=f"Ingested from {artefact.source_system}",
                )
                self._graph.add_object(registered)
                result.ingested_objects.append(registered)

            except Exception as e:
                result.errors.append(f"Failed to register {obj.name}: {e}")

        return result

    def ingest_batch(
        self,
        artefacts: list[RawArtefact],
        operational_plane: str,
        ingested_by: str = "ingress-pipeline",
    ) -> list[IngestResult]:
        return [self.ingest(a, operational_plane, ingested_by) for a in artefacts]
