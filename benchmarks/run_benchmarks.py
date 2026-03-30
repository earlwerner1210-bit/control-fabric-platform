"""
Performance benchmark suite for Control Fabric Platform.

Measures throughput and latency of core operations at scale.

Usage:
    python benchmarks/run_benchmarks.py --quick
    python benchmarks/run_benchmarks.py --full --out results.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.platform_action_release_gate import PlatformActionReleaseGate
from app.core.platform_validation_chain import ActionOrigin
from app.core.reconciliation.cross_plane_engine import CrossPlaneReconciliationEngine
from app.core.severity.domain_types import SeverityInput
from app.core.severity.engine import SeverityEngine
from app.domain_packs.release_governance.seed_data import build_demo_platform


@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    total_seconds: float
    ops_per_second: float
    avg_ms: float
    p99_ms: float = 0.0


@dataclass
class BenchmarkSuite:
    timestamp: str = ""
    mode: str = "quick"
    results: list[BenchmarkResult] = field(default_factory=list)
    total_seconds: float = 0.0

    def add(self, r: BenchmarkResult) -> None:
        self.results.append(r)
        print(
            f"  {r.name}: {r.iterations} ops in {r.total_seconds:.2f}s "
            f"({r.ops_per_second:.0f} ops/s, avg {r.avg_ms:.2f}ms)"
        )


def _time_ops(fn, n: int) -> BenchmarkResult:
    """Time a function over n iterations."""
    times: list[float] = []
    start = time.perf_counter()
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    total = time.perf_counter() - start
    times.sort()
    p99_idx = max(0, int(len(times) * 0.99) - 1)
    return BenchmarkResult(
        name="",
        iterations=n,
        total_seconds=round(total, 4),
        ops_per_second=round(n / total, 1) if total > 0 else 0,
        avg_ms=round((total / n) * 1000, 3) if n > 0 else 0,
        p99_ms=round(times[p99_idx] * 1000, 3) if times else 0,
    )


def bench_release_gate_pass(n: int) -> BenchmarkResult:
    gate = PlatformActionReleaseGate()

    def op():
        gate.submit(
            "production_release",
            {"release": "bench"},
            "engineer",
            ActionOrigin.HUMAN_OPERATOR,
            evidence_references=["ci-001", "scan-001"],
        )

    r = _time_ops(op, n)
    r.name = "release_gate_pass"
    return r


def bench_release_gate_block(n: int) -> BenchmarkResult:
    gate = PlatformActionReleaseGate()

    def op():
        gate.submit(
            "production_release",
            {"release": "bench"},
            "ai-agent",
            ActionOrigin.AI_INFERENCE,
            evidence_references=[],
        )

    r = _time_ops(op, n)
    r.name = "release_gate_block"
    return r


def bench_reconciliation(n: int) -> BenchmarkResult:
    platform = build_demo_platform()

    def op():
        engine = CrossPlaneReconciliationEngine(graph=platform["graph"])
        engine.run_full_reconciliation()

    r = _time_ops(op, n)
    r.name = "reconciliation"
    return r


def bench_severity_scoring(n: int) -> BenchmarkResult:
    engine = SeverityEngine()
    inp = SeverityInput(
        case_id="bench-sev",
        case_type="gap",
        severity_raw="high",
        financial_impact=500_000.0,
        affected_objects=3,
        rule_criticality="high",
    )

    def op():
        engine.score(inp)

    r = _time_ops(op, n)
    r.name = "severity_scoring"
    return r


def bench_explainability(n: int) -> BenchmarkResult:
    from app.core.explainability.engine import ExplainabilityEngine

    engine = ExplainabilityEngine()
    audit_result = {
        "dispatch_id": "bench-001",
        "action_type": "production_release",
        "origin": "human_operator",
        "requested_by": "engineer",
        "dispatched_at": datetime.now(UTC).isoformat(),
        "failure_reason": "evidence_sufficiency: No evidence references provided",
    }

    def op():
        engine.explain_block(audit_result)

    r = _time_ops(op, n)
    r.name = "explainability"
    return r


QUICK_SCALE = {"gate_pass": 100, "gate_block": 100, "recon": 10, "severity": 500, "explain": 200}
FULL_SCALE = {
    "gate_pass": 1000,
    "gate_block": 1000,
    "recon": 100,
    "severity": 10000,
    "explain": 1000,
}


def run(mode: str = "quick") -> BenchmarkSuite:
    scale = QUICK_SCALE if mode == "quick" else FULL_SCALE
    suite = BenchmarkSuite(timestamp=datetime.now(UTC).isoformat(), mode=mode)

    print(f"\nControl Fabric Platform — Benchmark Suite ({mode})")
    print("=" * 60)

    suite.add(bench_release_gate_pass(scale["gate_pass"]))
    suite.add(bench_release_gate_block(scale["gate_block"]))
    suite.add(bench_reconciliation(scale["recon"]))
    suite.add(bench_severity_scoring(scale["severity"]))
    suite.add(bench_explainability(scale["explain"]))

    suite.total_seconds = round(sum(r.total_seconds for r in suite.results), 2)
    print(f"\nTotal: {suite.total_seconds}s")
    print("=" * 60)
    return suite


def main() -> None:
    parser = argparse.ArgumentParser(description="Run platform benchmarks")
    parser.add_argument("--quick", action="store_true", help="Quick run (smaller scale)")
    parser.add_argument("--full", action="store_true", help="Full run (larger scale)")
    parser.add_argument("--out", type=str, help="Output JSON file path")
    args = parser.parse_args()

    mode = "full" if args.full else "quick"
    suite = run(mode)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(
                {
                    "timestamp": suite.timestamp,
                    "mode": suite.mode,
                    "total_seconds": suite.total_seconds,
                    "results": [asdict(r) for r in suite.results],
                },
                f,
                indent=2,
            )
        print(f"Results written to {out_path}")


if __name__ == "__main__":
    main()
