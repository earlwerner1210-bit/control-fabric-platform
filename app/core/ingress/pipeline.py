from __future__ import annotations

import logging
from typing import Any

from app.core.graph.domain_types import ControlObject
from app.core.graph.store import ControlGraphStore
from app.core.ingress.domain_types import ArtefactFormat, RawArtefact
from app.core.ingress.normaliser import ArtefactNormaliser, NormalisationError
from app.core.registry.object_registry import ObjectRegistry

logger = logging.getLogger(__name__)


class IngestResult:
    """Result of a full ingestion pipeline run."""

    def __init__(self) -> None:
        self.ingested_objects: list[ControlObject] = []
        self.errors: list[str] = []
        self.artefact_id: str = ""

    @property
    def success(self) -> bool:
        return len(self.ingested_objects) > 0 and len(self.errors) == 0

    @property
    def object_count(self) -> int:
        return len(self.ingested_objects)


class IngestPipeline:
    """
    End-to-end ingestion pipeline: RawArtefact → ControlObject → Registry → Graph.

    Patent Claim (Theme 1 — Layer 1): The pipeline captures heterogeneous
    inputs, normalises them into typed control objects, stamps provenance,
    registers them in the Object Registry, and adds them to the Control Graph.

    This is the entry point of the entire Control Fabric Platform.
    """

    def __init__(
        self,
        registry: ObjectRegistry,
        graph: ControlGraphStore,
        normaliser: ArtefactNormaliser | None = None,
    ) -> None:
        self._registry = registry
        self._graph = graph
        self._normaliser = normaliser or ArtefactNormaliser()

    def ingest(
        self,
        artefact: RawArtefact,
        operational_plane: str,
        ingested_by: str = "ingress-pipeline",
    ) -> IngestResult:
        """
        Ingest a raw artefact through the full pipeline.

        Steps:
        1. Normalise artefact into typed ControlObjects
        2. Register each object in the Object Registry
        3. Add each object to the Control Graph
        4. Return IngestResult with all ingested objects
        """
        result = IngestResult()
        result.artefact_id = artefact.artefact_id

        logger.info(
            "Ingesting artefact: %s from %s into plane=%s",
            artefact.artefact_id[:8],
            artefact.source_system,
            operational_plane,
        )

        # Step 1: Normalise
        try:
            objects = self._normaliser.normalise_to_objects(artefact, operational_plane)
        except NormalisationError as e:
            result.errors.append(f"Normalisation failed: {e}")
            return result

        # Step 2 + 3: Register and add to graph
        for obj in objects:
            try:
                registered = self._registry.register(
                    obj,
                    registered_by=ingested_by,
                    reason=f"Ingested from {artefact.source_system}",
                )
                self._graph.add_object(registered)
                result.ingested_objects.append(registered)
                logger.info(
                    "Ingested: %s (%s)",
                    registered.object_id[:8],
                    registered.object_type.value,
                )
            except Exception as e:
                result.errors.append(f"Failed to register {obj.name}: {e}")

        return result

    def ingest_batch(
        self,
        artefacts: list[RawArtefact],
        operational_plane: str,
        ingested_by: str = "ingress-pipeline",
    ) -> list[IngestResult]:
        """Ingest multiple artefacts — returns result per artefact."""
        return [self.ingest(a, operational_plane, ingested_by) for a in artefacts]
