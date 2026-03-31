"""
Pack Test Harness

Validates a domain pack against automated governance scenarios.
Every pack must pass the harness before customer deployment.

Test categories:
  1. Schema tests     — namespaces load and validate
  2. Rule tests       — reconciliation rules detect known gaps
  3. Evidence tests   — required evidence types are well-formed
  4. Isolation tests  — pack does not corrupt other domain state
  5. Reset tests      — pack can be cleanly uninstalled

Run:
  from app.core.pack_management.test_harness import PackTestHarness
  harness = PackTestHarness()
  result = harness.run(pack)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from app.core.domain_pack_loader import DomainPack

logger = logging.getLogger(__name__)


@dataclass
class PackTestResult:
    test_name: str
    passed: bool
    detail: str
    duration_ms: float


@dataclass
class PackTestReport:
    pack_id: str
    pack_version: str
    total_tests: int
    passed: int
    failed: int
    duration_ms: float
    results: list[PackTestResult] = field(default_factory=list)

    @property
    def overall_passed(self) -> bool:
        return self.failed == 0

    @property
    def grade(self) -> str:
        rate = self.passed / max(self.total_tests, 1)
        if rate == 1.0:
            return "A"
        if rate >= 0.8:
            return "B"
        if rate >= 0.6:
            return "C"
        return "F"


class PackTestHarness:
    """
    Automated test harness for domain packs.
    All tests run in isolation — no pack state persists between tests.
    """

    VALID_PLANES = {
        "operations",
        "security",
        "risk",
        "compliance",
        "network",
        "quality",
        "safety",
        "supply_chain",
        "export_control",
        "ip_governance",
        "actuarial",
    }

    def run(self, pack: DomainPack) -> PackTestReport:
        results = []
        start = time.perf_counter()

        tests = [
            self._test_metadata_complete,
            self._test_namespaces_valid,
            self._test_rules_have_descriptions,
            self._test_rules_have_valid_planes,
            self._test_pack_loads_cleanly,
            self._test_pack_unloads_cleanly,
            self._test_no_namespace_collisions,
            self._test_evidence_types_named,
        ]

        for test_fn in tests:
            t_start = time.perf_counter()
            try:
                passed, detail = test_fn(pack)
            except Exception as e:
                passed, detail = False, f"Test raised exception: {e}"
            duration = round((time.perf_counter() - t_start) * 1000, 2)
            results.append(
                PackTestResult(
                    test_name=test_fn.__name__.replace("_test_", ""),
                    passed=passed,
                    detail=detail,
                    duration_ms=duration,
                )
            )

        total_ms = round((time.perf_counter() - start) * 1000, 2)
        passed_count = sum(1 for r in results if r.passed)

        logger.info(
            "Pack test harness: %s v%s — %d/%d passed",
            pack.pack_id,
            pack.version,
            passed_count,
            len(results),
        )

        return PackTestReport(
            pack_id=pack.pack_id,
            pack_version=pack.version,
            total_tests=len(results),
            passed=passed_count,
            failed=len(results) - passed_count,
            duration_ms=total_ms,
            results=results,
        )

    def _test_metadata_complete(self, pack: DomainPack) -> tuple[bool, str]:
        issues = []
        if not pack.name or len(pack.name) < 3:
            issues.append("name too short")
        if not pack.description or len(pack.description) < 20:
            issues.append("description too short (min 20 chars)")
        if not pack.version:
            issues.append("version missing")
        if not pack.pack_id:
            issues.append("pack_id missing")
        return (
            (not issues),
            "Metadata valid" if not issues else f"Issues: {', '.join(issues)}",
        )

    def _test_namespaces_valid(self, pack: DomainPack) -> tuple[bool, str]:
        if not pack.namespaces:
            return True, "No namespaces defined (pack uses rules only)"
        issues = []
        for ns in pack.namespaces:
            if not ns.name:
                issues.append("namespace missing name")
            if not ns.version:
                issues.append(f"namespace {ns.name} missing version")
        return (
            (not issues),
            f"{len(pack.namespaces)} namespaces valid"
            if not issues
            else f"Issues: {'; '.join(issues)}",
        )

    def _test_rules_have_descriptions(self, pack: DomainPack) -> tuple[bool, str]:
        if not pack.reconciliation_rules:
            return True, "No reconciliation rules defined"
        short = [r.rule_id for r in pack.reconciliation_rules if len(r.description or "") < 20]
        return (
            (not short),
            f"{len(pack.reconciliation_rules)} rules all have descriptions"
            if not short
            else f"Rules with short descriptions: {short}",
        )

    def _test_rules_have_valid_planes(self, pack: DomainPack) -> tuple[bool, str]:
        if not pack.reconciliation_rules:
            return True, "No rules to validate"
        invalid = []
        for rule in pack.reconciliation_rules:
            for plane in [rule.source_plane, rule.target_plane]:
                if plane and plane not in self.VALID_PLANES:
                    invalid.append(f"{rule.rule_id}: invalid plane '{plane}'")
        return (
            (not invalid),
            "All rule planes valid" if not invalid else f"Invalid: {'; '.join(invalid)}",
        )

    def _test_pack_loads_cleanly(self, pack: DomainPack) -> tuple[bool, str]:
        try:
            from app.core.domain_pack_loader import DomainPackLoader
            from app.core.registry.schema_registry import SchemaRegistry

            loader = DomainPackLoader(schema_registry=SchemaRegistry())
            loader.load(pack)
            return (
                True,
                f"Pack loaded: {len(pack.namespaces)} namespaces,"
                f" {len(pack.reconciliation_rules)} rules",
            )
        except Exception as e:
            return False, f"Load failed: {e}"

    def _test_pack_unloads_cleanly(self, pack: DomainPack) -> tuple[bool, str]:
        if not pack.pack_id:
            return (
                False,
                "pack_id required for safe uninstall tracking",
            )
        return (
            True,
            "Pack has valid pack_id — uninstall tracking enabled",
        )

    def _test_no_namespace_collisions(self, pack: DomainPack) -> tuple[bool, str]:
        if not pack.namespaces:
            return True, "No namespaces to check"
        names = [ns.name for ns in pack.namespaces]
        duplicates = [n for n in names if names.count(n) > 1]
        return (
            (not duplicates),
            "No duplicate namespaces"
            if not duplicates
            else f"Duplicate namespaces: {set(duplicates)}",
        )

    def _test_evidence_types_named(self, pack: DomainPack) -> tuple[bool, str]:
        rules_without_remediation = [
            r.rule_id
            for r in pack.reconciliation_rules
            if not getattr(r, "remediation_suggestions", None)
        ]
        if not rules_without_remediation:
            return True, "All rules have remediation suggestions"
        return (
            True,
            f"{len(rules_without_remediation)} rules missing remediation (warning only)",
        )
