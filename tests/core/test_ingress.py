from __future__ import annotations

import json

import pytest

from app.core.graph.domain_types import ControlObjectType
from app.core.graph.store import ControlGraphStore
from app.core.ingress.domain_types import ArtefactFormat, RawArtefact
from app.core.ingress.normaliser import ArtefactNormaliser
from app.core.ingress.pipeline import IngestPipeline
from app.core.registry.object_registry import ObjectRegistry


def make_json_artefact(
    data: dict | list, source: str = "test-system", submitted_by: str = "test-user"
) -> RawArtefact:
    return RawArtefact(
        source_system=source,
        format=ArtefactFormat.JSON,
        raw_content=json.dumps(data),
        submitted_by=submitted_by,
    )


def make_text_artefact(text: str, title: str = "Test Artefact") -> RawArtefact:
    return RawArtefact(
        source_system="test",
        format=ArtefactFormat.TEXT,
        raw_content=text,
        submitted_by="test-user",
        metadata={"title": title},
    )


class TestArtefactNormaliser:
    def test_normalise_json_single_object(self) -> None:
        normaliser = ArtefactNormaliser()
        artefact = make_json_artefact(
            {"name": "GDPR Art 25", "type": "regulation", "description": "Data protection mandate"}
        )
        result = normaliser.normalise(artefact)
        assert result.object_count == 1
        assert result.extracted_objects[0]["name"] == "GDPR Art 25"

    def test_normalise_json_array(self) -> None:
        normaliser = ArtefactNormaliser()
        artefact = make_json_artefact([{"name": "Control A"}, {"name": "Control B"}])
        result = normaliser.normalise(artefact)
        assert result.object_count == 2

    def test_normalise_text_artefact(self) -> None:
        normaliser = ArtefactNormaliser()
        artefact = make_text_artefact(
            "This regulation mandates data protection controls.", "GDPR Mandate"
        )
        result = normaliser.normalise(artefact)
        assert result.object_count == 1

    def test_type_inference_regulation(self) -> None:
        normaliser = ArtefactNormaliser()
        artefact = make_json_artefact(
            {"name": "GDPR Article 25", "description": "regulation mandate"}
        )
        result = normaliser.normalise(artefact)
        assert result.extracted_objects[0]["object_type"] == ControlObjectType.REGULATORY_MANDATE

    def test_type_inference_vulnerability(self) -> None:
        normaliser = ArtefactNormaliser()
        artefact = make_json_artefact(
            {"name": "CVE-2024-001", "description": "critical vulnerability"}
        )
        result = normaliser.normalise(artefact)
        assert result.extracted_objects[0]["object_type"] == ControlObjectType.VULNERABILITY

    def test_content_hash_computed(self) -> None:
        artefact = make_json_artefact({"name": "test"})
        assert len(artefact.content_hash) == 64

    def test_normalise_to_objects_returns_control_objects(self) -> None:
        normaliser = ArtefactNormaliser()
        artefact = make_json_artefact({"name": "Risk Control A", "description": "risk control"})
        objects = normaliser.normalise_to_objects(artefact, "risk")
        assert len(objects) > 0
        assert objects[0].operational_plane == "risk"
        assert objects[0].provenance.source_hash == artefact.content_hash

    def test_provenance_hash_matches_content(self) -> None:
        """Patent Claim: Provenance hash binds object to source artefact."""
        normaliser = ArtefactNormaliser()
        artefact = make_json_artefact({"name": "Test Control"})
        objects = normaliser.normalise_to_objects(artefact, "risk")
        assert objects[0].provenance.source_hash == artefact.content_hash


class TestIngestPipeline:
    def test_ingest_creates_object_in_registry_and_graph(self) -> None:
        registry = ObjectRegistry()
        graph = ControlGraphStore()
        pipeline = IngestPipeline(registry=registry, graph=graph)
        artefact = make_json_artefact({"name": "GDPR Art 25", "description": "regulation"})
        result = pipeline.ingest(artefact, operational_plane="compliance")
        assert result.success
        assert result.object_count > 0
        assert registry.object_count > 0
        assert graph.node_count > 0

    def test_ingest_object_retrievable_from_registry(self) -> None:
        registry = ObjectRegistry()
        graph = ControlGraphStore()
        pipeline = IngestPipeline(registry=registry, graph=graph)
        artefact = make_json_artefact({"name": "Test Control", "description": "risk control"})
        result = pipeline.ingest(artefact, operational_plane="risk")
        assert result.success
        obj_id = result.ingested_objects[0].object_id
        assert registry.get(obj_id) is not None

    def test_ingest_object_retrievable_from_graph(self) -> None:
        registry = ObjectRegistry()
        graph = ControlGraphStore()
        pipeline = IngestPipeline(registry=registry, graph=graph)
        artefact = make_json_artefact({"name": "Test Control", "description": "risk control"})
        result = pipeline.ingest(artefact, operational_plane="risk")
        obj_id = result.ingested_objects[0].object_id
        assert graph.get_object(obj_id) is not None

    def test_ingest_batch(self) -> None:
        registry = ObjectRegistry()
        graph = ControlGraphStore()
        pipeline = IngestPipeline(registry=registry, graph=graph)
        artefacts = [make_json_artefact({"name": f"Control {i}"}) for i in range(3)]
        results = pipeline.ingest_batch(artefacts, operational_plane="risk")
        assert len(results) == 3
        assert registry.object_count == 3

    def test_ingest_version_history_recorded(self) -> None:
        """Patent Claim: Every ingested object has version history from moment of ingestion."""
        registry = ObjectRegistry()
        graph = ControlGraphStore()
        pipeline = IngestPipeline(registry=registry, graph=graph)
        artefact = make_json_artefact({"name": "Versioned Control"})
        result = pipeline.ingest(artefact, operational_plane="risk")
        obj_id = result.ingested_objects[0].object_id
        history = registry.get_version_history(obj_id)
        assert len(history) == 1
        assert history[0].version == 1


class TestDomainPackLoader:
    def test_load_telco_pack(self) -> None:
        from app.core.domain_pack_loader import DomainPackLoader, build_telco_ops_pack
        from app.core.registry.schema_registry import SchemaRegistry

        schema_registry = SchemaRegistry()
        loader = DomainPackLoader(schema_registry=schema_registry)
        pack = build_telco_ops_pack()
        loader.load(pack)
        assert loader.pack_count == 1

    def test_pack_registers_namespaces(self) -> None:
        from app.core.domain_pack_loader import DomainPackLoader, build_telco_ops_pack
        from app.core.registry.schema_registry import SchemaRegistry

        schema_registry = SchemaRegistry()
        initial_count = schema_registry.namespace_count
        loader = DomainPackLoader(schema_registry=schema_registry)
        loader.load(build_telco_ops_pack())
        assert schema_registry.namespace_count > initial_count

    def test_pack_exposes_reconciliation_rules(self) -> None:
        from app.core.domain_pack_loader import DomainPackLoader, build_telco_ops_pack
        from app.core.registry.schema_registry import SchemaRegistry

        loader = DomainPackLoader(schema_registry=SchemaRegistry())
        loader.load(build_telco_ops_pack())
        rules = loader.get_all_rules()
        assert len(rules) > 0
        assert rules[0].domain_pack == "telco-ops"

    def test_duplicate_pack_load_is_safe(self) -> None:
        from app.core.domain_pack_loader import DomainPackLoader, build_telco_ops_pack
        from app.core.registry.schema_registry import SchemaRegistry

        loader = DomainPackLoader(schema_registry=SchemaRegistry())
        pack = build_telco_ops_pack()
        loader.load(pack)
        loader.load(pack)  # Should not raise
        assert loader.pack_count == 1
