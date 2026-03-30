from __future__ import annotations

import json
import logging
from typing import Any

from app.core.graph.domain_types import (
    ControlObject,
    ControlObjectProvenance,
    ControlObjectState,
    ControlObjectType,
)
from app.core.ingress.domain_types import (
    ArtefactFormat,
    NormalisationResult,
    NormalisationStatus,
    RawArtefact,
)

logger = logging.getLogger(__name__)


class NormalisationError(Exception):
    pass


class ArtefactNormaliser:
    """
    Converts raw enterprise artefacts into typed ControlObjects.

    Patent Claim (Theme 1 — Layer 1): The Ingress Layer parses
    unstructured or semi-structured data and maps it to rigidly defined
    schemas. Disparate artefacts are transformed into standardised,
    first-class, typed control objects.

    Patent Claim: A cryptographic hash of the source document is generated
    at ingestion and bound to the new object — establishing an unbreakable
    provenance chain from the exact moment of ingestion.
    """

    # Mapping of hint keywords to ControlObjectType
    _TYPE_HINTS: dict[str, ControlObjectType] = {
        "regulation": ControlObjectType.REGULATORY_MANDATE,
        "mandate": ControlObjectType.REGULATORY_MANDATE,
        "gdpr": ControlObjectType.REGULATORY_MANDATE,
        "compliance": ControlObjectType.COMPLIANCE_REQUIREMENT,
        "requirement": ControlObjectType.COMPLIANCE_REQUIREMENT,
        "risk": ControlObjectType.RISK_CONTROL,
        "control": ControlObjectType.RISK_CONTROL,
        "vulnerability": ControlObjectType.VULNERABILITY,
        "vuln": ControlObjectType.VULNERABILITY,
        "cve": ControlObjectType.VULNERABILITY,
        "security": ControlObjectType.SECURITY_CONTROL,
        "policy": ControlObjectType.OPERATIONAL_POLICY,
        "technical": ControlObjectType.TECHNICAL_CONTROL,
        "asset": ControlObjectType.ASSET,
        "process": ControlObjectType.PROCESS,
    }

    def normalise(self, artefact: RawArtefact) -> NormalisationResult:
        """
        Normalise a raw artefact into typed control objects.
        Returns NormalisationResult — never raises.
        """
        logger.info(
            "Normalising artefact: %s format=%s source=%s",
            artefact.artefact_id[:8],
            artefact.format.value,
            artefact.source_system,
        )

        try:
            if artefact.format == ArtefactFormat.JSON:
                extracted = self._normalise_json(artefact)
            elif artefact.format == ArtefactFormat.TEXT:
                extracted = self._normalise_text(artefact)
            elif artefact.format == ArtefactFormat.API_RESPONSE:
                extracted = self._normalise_api_response(artefact)
            else:
                extracted = self._normalise_generic(artefact)

            return NormalisationResult(
                artefact_id=artefact.artefact_id,
                status=NormalisationStatus.NORMALISED,
                extracted_objects=extracted,
            )

        except Exception as e:
            logger.error("Normalisation failed: %s — %s", artefact.artefact_id[:8], e)
            return NormalisationResult(
                artefact_id=artefact.artefact_id,
                status=NormalisationStatus.FAILED,
                extraction_errors=[str(e)],
            )

    def normalise_to_objects(
        self, artefact: RawArtefact, operational_plane: str
    ) -> list[ControlObject]:
        """
        Normalise artefact directly to ControlObject instances.
        """
        result = self.normalise(artefact)
        if result.status != NormalisationStatus.NORMALISED:
            raise NormalisationError(f"Normalisation failed: {result.extraction_errors}")

        objects = []
        provenance = ControlObjectProvenance.create(
            source_system=artefact.source_system,
            source_content=artefact.raw_content,
            ingested_by=artefact.submitted_by,
            source_uri=artefact.source_uri,
        )

        for extracted in result.extracted_objects:
            obj = ControlObject(
                object_type=extracted.get("object_type", ControlObjectType.RISK_CONTROL),
                name=extracted.get("name", f"Artefact-{artefact.artefact_id[:8]}"),
                description=extracted.get("description", ""),
                schema_namespace=extracted.get("schema_namespace", "core"),
                provenance=provenance,
                operational_plane=operational_plane,
                attributes=extracted.get("attributes", {}),
                tags=extracted.get("tags", []),
            )
            objects.append(obj)

        return objects

    def _normalise_json(self, artefact: RawArtefact) -> list[dict[str, Any]]:
        content = (
            artefact.raw_content
            if isinstance(artefact.raw_content, str)
            else artefact.raw_content.decode()
        )
        data = json.loads(content)

        if isinstance(data, list):
            return [
                self._extract_from_dict(item, artefact) for item in data if isinstance(item, dict)
            ]
        elif isinstance(data, dict):
            return [self._extract_from_dict(data, artefact)]
        return []

    def _normalise_text(self, artefact: RawArtefact) -> list[dict[str, Any]]:
        content = (
            artefact.raw_content
            if isinstance(artefact.raw_content, str)
            else artefact.raw_content.decode()
        )
        object_type = self._infer_type_from_text(content, artefact.metadata)
        return [
            {
                "name": artefact.metadata.get("title", f"Artefact-{artefact.artefact_id[:8]}"),
                "description": content[:500],
                "object_type": object_type,
                "schema_namespace": "core",
                "attributes": artefact.metadata,
                "tags": artefact.metadata.get("tags", []),
            }
        ]

    def _normalise_api_response(self, artefact: RawArtefact) -> list[dict[str, Any]]:
        return self._normalise_json(artefact)

    def _normalise_generic(self, artefact: RawArtefact) -> list[dict[str, Any]]:
        return [
            {
                "name": artefact.metadata.get("title", f"Artefact-{artefact.artefact_id[:8]}"),
                "description": f"Ingested from {artefact.source_system}",
                "object_type": ControlObjectType.ASSET,
                "schema_namespace": "core",
                "attributes": artefact.metadata,
                "tags": [],
            }
        ]

    def _extract_from_dict(self, data: dict[str, Any], artefact: RawArtefact) -> dict[str, Any]:
        object_type = self._infer_type_from_text(
            f"{data.get('name', '')} {data.get('type', '')} {data.get('description', '')}",
            data,
        )
        return {
            "name": data.get("name", data.get("title", f"Object-{artefact.artefact_id[:8]}")),
            "description": data.get("description", data.get("summary", "")),
            "object_type": object_type,
            "schema_namespace": data.get("schema_namespace", "core"),
            "attributes": {
                k: v for k, v in data.items() if k not in ("name", "title", "description", "type")
            },
            "tags": data.get("tags", []),
        }

    def _infer_type_from_text(self, text: str, metadata: dict[str, Any]) -> ControlObjectType:
        text_lower = text.lower()
        if "object_type" in metadata:
            try:
                return ControlObjectType(metadata["object_type"])
            except ValueError:
                pass
        for hint, obj_type in self._TYPE_HINTS.items():
            if hint in text_lower:
                return obj_type
        return ControlObjectType.ASSET
