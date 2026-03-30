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

    def test_timeline_overlap_link(self):
        from datetime import datetime, timedelta

        now = datetime(2025, 6, 15, 10, 0, 0)
        linker = WorkOrderIncidentLinker()
        links = linker.link(
            {
                "work_order_id": "WO-T1",
                "description": "alpha bravo charlie",
                "scheduled_date": now.isoformat(),
                "completed_date": (now + timedelta(days=2)).isoformat(),
            },
            [
                {
                    "incident_id": "INC-T1",
                    "description": "delta echo foxtrot",
                    "title": "unrelated title",
                    "reported_at": (now + timedelta(hours=3)).isoformat(),
                }
            ],
        )
        timeline_links = [l for l in links if l.link_type == "timeline_overlap"]
        assert len(timeline_links) >= 1

    def test_best_link_per_incident(self):
        """When multiple strategies match, only the best scoring link is kept."""
        from datetime import datetime, timedelta

        now = datetime(2025, 6, 15, 10, 0, 0)
        linker = WorkOrderIncidentLinker()
        links = linker.link(
            {
                "id": "WO-B1",
                "description": "Cable repair fault resolution HV",
                "scheduled_date": now.isoformat(),
            },
            [
                {
                    "id": "INC-B1",
                    "description": "Cable repair fault HV",
                    "title": "Cable fault",
                    "reported_at": (now + timedelta(hours=1)).isoformat(),
                }
            ],
        )
        inc_ids = [l.target_id for l in links]
        assert len(inc_ids) == len(set(inc_ids))

    def test_link_domains_field_telco(self):
        linker = WorkOrderIncidentLinker()
        links = linker.link(
            {"work_order_id": "WO-D1", "description": "x"},
            [{"incident_id": "INC-D1", "description": "y", "work_order_refs": ["WO-D1"]}],
        )
        for link in links:
            assert link.source_domain == "field"
            assert link.target_domain == "telco"


class TestTokenUtils:
    def test_tokenize_basic(self):
        from app.domain_packs.reconciliation.linkers import _tokenize

        tokens = _tokenize("Cable Jointing HV repair")
        assert "cable" in tokens
        assert "jointing" in tokens

    def test_tokenize_removes_stop_words(self):
        from app.domain_packs.reconciliation.linkers import _tokenize

        tokens = _tokenize("the quick brown fox and the lazy dog")
        assert "the" not in tokens
        assert "and" not in tokens

    def test_tokenize_empty(self):
        from app.domain_packs.reconciliation.linkers import _tokenize

        assert _tokenize("") == set()

    def test_token_similarity_identical(self):
        from app.domain_packs.reconciliation.linkers import _token_similarity

        a = {"cable", "jointing", "hv"}
        assert _token_similarity(a, a) == 1.0

    def test_token_similarity_disjoint(self):
        from app.domain_packs.reconciliation.linkers import _token_similarity

        a = {"cable", "jointing"}
        b = {"pole", "replacement"}
        assert _token_similarity(a, b) == 0.0

    def test_token_similarity_empty(self):
        from app.domain_packs.reconciliation.linkers import _token_similarity

        assert _token_similarity(set(), {"a"}) == 0.0
