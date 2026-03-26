"""Unit tests for cross-domain linkers."""

from __future__ import annotations

import pytest

from app.domain_packs.reconciliation.linkers import (
    ContractWorkOrderLinker,
    CrossPlaneLink,
    WorkOrderIncidentLinker,
)


class TestContractWorkOrderLinker:
    def test_ref_match(self):
        linker = ContractWorkOrderLinker()
        links = linker.link(
            [{"id": "CO-1", "description": "HV maintenance"}],
            {"work_order_id": "WO-1", "contract_ref": "CO-1", "description": "HV work"},
        )
        assert len(links) == 1
        assert links[0].link_type == "ref_match"
        assert links[0].confidence == 1.0

    def test_activity_match(self):
        linker = ContractWorkOrderLinker()
        links = linker.link(
            [{"id": "CO-1", "description": "HV switching maintenance scheduled"}],
            {"work_order_id": "WO-1", "description": "HV switching maintenance at Glasgow"},
        )
        assert len(links) >= 1
        assert any(l.link_type in ("activity_match", "description_similarity") for l in links)

    def test_no_match(self):
        linker = ContractWorkOrderLinker()
        links = linker.link(
            [{"id": "CO-1", "description": "Cable jointing"}],
            {"work_order_id": "WO-1", "description": "Completely unrelated xyz abc"},
        )
        assert len(links) == 0

    def test_rate_card_ref_match(self):
        linker = ContractWorkOrderLinker()
        links = linker.link(
            [{"id": "CO-1", "description": "work", "rate_card_ref": "RC-001"}],
            {"work_order_id": "WO-1", "description": "work", "rate_card_ref": "RC-001"},
        )
        rate_links = [l for l in links if l.link_type == "rate_card"]
        assert len(rate_links) == 1

    def test_obligation_ref_match(self):
        linker = ContractWorkOrderLinker()
        links = linker.link(
            [{"id": "CO-1", "description": "work", "obligation_refs": ["OBL-001"]}],
            {"work_order_id": "WO-1", "description": "work", "obligation_refs": ["OBL-001"]},
        )
        obl_links = [l for l in links if l.link_type == "obligation_match"]
        assert len(obl_links) == 1

    def test_multiple_contract_objects(self):
        linker = ContractWorkOrderLinker()
        links = linker.link(
            [
                {"id": "CO-1", "description": "HV switching maintenance"},
                {"id": "CO-2", "description": "Cable jointing repairs"},
            ],
            {"work_order_id": "WO-1", "description": "HV switching maintenance Glasgow"},
        )
        assert len(links) >= 1

    def test_cross_plane_link_fields(self):
        linker = ContractWorkOrderLinker()
        links = linker.link(
            [{"id": "CO-1", "description": "HV switching"}],
            {"work_order_id": "WO-1", "contract_ref": "CO-1", "description": "HV"},
        )
        assert len(links) >= 1
        link = links[0]
        assert isinstance(link, CrossPlaneLink)
        assert link.source_domain == "contract"
        assert link.target_domain == "field"


class TestWorkOrderIncidentLinker:
    def test_ref_match(self):
        linker = WorkOrderIncidentLinker()
        links = linker.link(
            {"work_order_id": "WO-1", "description": "HV maintenance"},
            [{"incident_id": "INC-1", "description": "Power outage", "work_order_refs": ["WO-1"]}],
        )
        assert len(links) == 1
        assert links[0].link_type == "ref_match"

    def test_description_similarity(self):
        linker = WorkOrderIncidentLinker()
        links = linker.link(
            {"work_order_id": "WO-1", "description": "HV switching maintenance Glasgow substation"},
            [{"incident_id": "INC-1", "description": "HV switching fault Glasgow substation area"}],
        )
        assert len(links) >= 1

    def test_no_match(self):
        linker = WorkOrderIncidentLinker()
        links = linker.link(
            {"work_order_id": "WO-1", "description": "Cable jointing"},
            [{"incident_id": "INC-1", "description": "Completely unrelated xyz"}],
        )
        assert len(links) == 0
