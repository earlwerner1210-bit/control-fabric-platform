from __future__ import annotations


class TestDataGovernanceManager:
    def test_classify_entity(self) -> None:
        from app.core.data_governance.classification import (
            ClassificationLevel,
            DataCategory,
        )
        from app.core.data_governance.manager import DataGovernanceManager

        mgr = DataGovernanceManager()
        rec = mgr.classify(
            entity_type="evidence",
            entity_id="ev-001",
            classification=ClassificationLevel.CONFIDENTIAL,
            data_category=DataCategory.EVIDENCE,
            classified_by="admin@test.com",
            tenant_id="t1",
        )
        assert rec.classification == ClassificationLevel.CONFIDENTIAL
        assert rec.record_hash  # SHA-256 hash generated
        assert mgr.get_classification("evidence", "ev-001") is rec

    def test_default_classification(self) -> None:
        from app.core.data_governance.classification import (
            ClassificationLevel,
            DataCategory,
        )
        from app.core.data_governance.manager import DataGovernanceManager

        mgr = DataGovernanceManager()
        assert (
            mgr.get_default_classification(DataCategory.USER_DATA) == ClassificationLevel.RESTRICTED
        )
        assert (
            mgr.get_default_classification(DataCategory.AUDIT_LOG) == ClassificationLevel.INTERNAL
        )

    def test_legal_hold_placed(self) -> None:
        from app.core.data_governance.manager import DataGovernanceManager

        mgr = DataGovernanceManager()
        hold = mgr.place_hold(
            hold_name="Litigation-2026-Q1",
            description="Preserve all Q1 evidence",
            entity_ids=["ev-001", "ev-002"],
            entity_types=["evidence"],
            placed_by="legal@test.com",
            legal_contact="counsel@firm.com",
            tenant_id="t1",
        )
        assert hold.is_active
        assert mgr.is_on_hold("ev-001")
        assert mgr.is_on_hold("ev-002")

    def test_legal_hold_blocks_deletion(self) -> None:
        from app.core.data_governance.manager import DataGovernanceManager

        mgr = DataGovernanceManager()
        mgr.place_hold(
            hold_name="Hold-1",
            description="Test",
            entity_ids=["ev-100"],
            entity_types=["evidence"],
            placed_by="legal@test.com",
            legal_contact="counsel@firm.com",
            tenant_id="t1",
        )
        can, reason = mgr.can_delete("ev-100")
        assert can is False
        assert "legal hold" in reason.lower()

    def test_legal_hold_release(self) -> None:
        from app.core.data_governance.manager import DataGovernanceManager

        mgr = DataGovernanceManager()
        hold = mgr.place_hold(
            hold_name="Hold-release-test",
            description="Will be released",
            entity_ids=["ev-200"],
            entity_types=["evidence"],
            placed_by="legal@test.com",
            legal_contact="counsel@firm.com",
            tenant_id="t1",
        )
        released = mgr.release_hold(hold.hold_id, released_by="legal@test.com")
        assert not released.is_active
        assert released.released_at is not None
        can, _ = mgr.can_delete("ev-200")
        assert can is True

    def test_redaction_by_classification(self) -> None:
        from app.core.data_governance.classification import ClassificationLevel
        from app.core.data_governance.manager import DataGovernanceManager

        mgr = DataGovernanceManager()
        data = {"email": "user@co.com", "finding": "Gap detected", "phone": "+1234567890"}
        redacted = mgr.redact_for_export(data, ClassificationLevel.RESTRICTED)
        assert "REDACTED" in redacted["email"]
        assert "REDACTED" in redacted["phone"]
        assert redacted["finding"] == "Gap detected"  # not in redaction list

    def test_platform_admin_sees_everything(self) -> None:
        from app.core.data_governance.classification import ClassificationLevel
        from app.core.data_governance.manager import DataGovernanceManager

        mgr = DataGovernanceManager()
        data = {"email": "secret@co.com", "ssn": "123-45-6789"}
        result = mgr.redact_for_export(
            data, ClassificationLevel.RESTRICTED, requesting_role="platform_admin"
        )
        assert result["email"] == "secret@co.com"
        assert result["ssn"] == "123-45-6789"

    def test_bulk_classify(self) -> None:
        from app.core.data_governance.classification import (
            ClassificationLevel,
            DataCategory,
        )
        from app.core.data_governance.manager import DataGovernanceManager

        mgr = DataGovernanceManager()
        records = mgr.bulk_classify(
            entity_ids=["a1", "a2", "a3"],
            entity_type="audit_log",
            classification=ClassificationLevel.INTERNAL,
            data_category=DataCategory.AUDIT_LOG,
            classified_by="system",
            tenant_id="t1",
        )
        assert len(records) == 3
        assert all(r.classification == ClassificationLevel.INTERNAL for r in records)


class TestPackTestHarness:
    def test_runs_on_release_governance_pack(self) -> None:
        from app.core.pack_management.test_harness import PackTestHarness
        from app.domain_packs.release_governance.pack import RELEASE_GOVERNANCE_PACK

        harness = PackTestHarness()
        report = harness.run(RELEASE_GOVERNANCE_PACK)
        assert report.total_tests == 8
        assert report.overall_passed  # release governance pack should pass all tests
        assert report.grade == "A"

    def test_fails_empty_pack(self) -> None:
        from app.core.domain_pack_loader import DomainPack
        from app.core.pack_management.test_harness import PackTestHarness

        harness = PackTestHarness()
        empty = DomainPack(pack_id="", name="", version="", description="")
        report = harness.run(empty)
        assert report.failed > 0
        assert report.grade != "A"

    def test_duration_recorded(self) -> None:
        from app.core.pack_management.test_harness import PackTestHarness
        from app.domain_packs.release_governance.pack import RELEASE_GOVERNANCE_PACK

        harness = PackTestHarness()
        report = harness.run(RELEASE_GOVERNANCE_PACK)
        assert report.duration_ms >= 0
        assert all(r.duration_ms >= 0 for r in report.results)


class TestCompatibilityMatrix:
    def test_same_pack_collision(self) -> None:
        from app.core.pack_management.compatibility import PackCompatibilityMatrix
        from app.domain_packs.release_governance.pack import RELEASE_GOVERNANCE_PACK

        compat = PackCompatibilityMatrix()
        report = compat.check(RELEASE_GOVERNANCE_PACK, RELEASE_GOVERNANCE_PACK)
        # Same pack has same namespaces — should show collisions
        assert not report.compatible or len(report.issues) > 0 or len(report.warnings) > 0

    def test_different_domain_packs_compatible(self) -> None:
        from app.core.domain_pack_loader import DomainPack
        from app.core.pack_management.compatibility import PackCompatibilityMatrix

        compat = PackCompatibilityMatrix()
        pack_a = DomainPack(pack_id="test-a", name="Test A", version="1.0", description="A")
        pack_b = DomainPack(pack_id="test-b", name="Test B", version="1.0", description="B")
        report = compat.check(pack_a, pack_b)
        assert report.compatible
        assert len(report.issues) == 0

    def test_build_matrix_for_all_packs(self) -> None:
        from app.core.domain_pack_loader import DomainPack
        from app.core.pack_management.compatibility import PackCompatibilityMatrix

        compat = PackCompatibilityMatrix()
        packs = [
            DomainPack(pack_id=f"p{i}", name=f"Pack {i}", version="1.0", description="test")
            for i in range(4)
        ]
        matrix = compat.build_matrix(packs)
        # 4 packs → C(4,2) = 6 pairs
        assert len(matrix) == 6
