#!/usr/bin/env python3
"""
Control Fabric Platform — Pre-flight Demo Script

Run this before every demo or pilot conversation.
Checks the platform is healthy, seeds realistic data,
and prints a complete checklist.

Usage:
    python scripts/demo_preflight.py
    python scripts/demo_preflight.py --reset   # Reset and reseed all data
    python scripts/demo_preflight.py --check   # Check only, no seeding

Output:
    - Platform health status
    - Readiness check results
    - Demo scenario summary
    - Console URLs for each screen
    - Exact commands to run during the demo

Takes ~30 seconds to complete.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

API = "http://localhost:8000"
CONSOLE = "http://localhost:3000"
GREEN = "\033[92m"
AMBER = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {AMBER}⚠{RESET} {msg}")


def err(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {CYAN}→{RESET} {msg}")


def head(msg: str) -> None:
    print(f"\n{BOLD}{msg}{RESET}")


def api_get(path: str) -> dict | None:
    try:
        with urllib.request.urlopen(f"{API}{path}", timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return None


def api_post(path: str, data: dict) -> dict | None:
    try:
        body = json.dumps(data).encode()
        req = urllib.request.Request(
            f"{API}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return None


def check_platform_health() -> bool:
    head("Platform health")
    health = api_get("/health")
    if not health:
        err("Platform not responding — run: make up")
        return False
    ok(f"API healthy: {health.get('status', 'ok')}")

    infra = api_get("/infra/health")
    if infra:
        overall = infra.get("overall", "unknown")
        if overall == "healthy":
            ok(f"Infrastructure: {overall}")
        else:
            warn(f"Infrastructure: {overall} — check /infra/health for details")

        checks = infra.get("checks", {})
        for svc, check in checks.items():
            status = check.get("status", "unknown")
            if status == "healthy":
                ok(f"  {svc}: {status}")
            elif status in ("not_configured", "unknown"):
                warn(f"  {svc}: {status}")
            else:
                err(f"  {svc}: {status} — {check.get('detail', '')[:60]}")
    return True


def check_readiness() -> bool:
    head("Readiness check")
    readiness = api_get("/compliance/readiness")
    if not readiness:
        err("Could not reach readiness endpoint")
        return False

    score = readiness.get("score", 0)
    grade = readiness.get("grade", "?")
    ready_for = readiness.get("ready_for", [])

    if grade in ("A", "B"):
        ok(f"Grade {grade} ({score}/100) — ready for: {', '.join(ready_for) or 'nothing yet'}")
    else:
        warn(f"Grade {grade} ({score}/100) — ready for: {', '.join(ready_for) or 'nothing yet'}")

    checks = readiness.get("checks", [])
    blocking = [c for c in checks if not c["passed"] and c["severity"] == "error"]
    warnings = [c for c in checks if not c["passed"] and c["severity"] == "warning"]

    for check in blocking:
        err(f"  {check['name']}: {check['detail']}")
        if check.get("remediation"):
            info(f"    Fix: {check['remediation']}")

    for check in warnings:
        warn(f"  {check['name']}: {check['detail']}")

    for check in checks:
        if check["passed"]:
            ok(f"  {check['name']}")

    return len(blocking) == 0


def apply_defaults() -> None:
    head("Platform defaults")
    result = api_post("/defaults/apply", {})
    if result:
        ok(f"Defaults applied: {result.get('message', 'ok')}")
    else:
        warn("Could not apply defaults (may already be applied)")


def seed_demo_data() -> None:
    head("Demo data")
    # Seed the release governance pack demo
    result = api_post("/demo/seed", {"tenant_id": "default"})
    if result:
        ok("Release governance demo seeded")
    else:
        warn("Demo seed returned no data (may already be seeded)")

    # Run reconciliation to generate some cases
    recon = api_post("/reconciliation/run", {"operational_plane": "operations"})
    if recon:
        cases = recon.get("cases_detected", 0)
        ok(f"Reconciliation complete: {cases} governance cases detected")


def check_slm_adapters() -> None:
    head("Domain SLM adapters")
    adapters = api_get("/slm/adapters")
    if not adapters:
        warn("SLM adapter endpoint not reachable")
        return
    count = adapters.get("adapter_count", 0)
    for adapter in adapters.get("adapters", []):
        adapter_id = adapter.get("adapter_id", "")
        ok(f"  {adapter_id}")
    if count < 8:
        warn(f"Only {count}/8 domain adapters registered")
    else:
        ok(f"All {count} domain adapters active")


def check_compliance_coverage() -> None:
    head("Compliance coverage")
    report = api_get("/compliance/report/default?period_days=30")
    if not report:
        warn("Compliance report not reachable")
        return
    grade = report.get("audit_readiness_grade", "?")
    score = report.get("audit_readiness_score", 0)
    covered = report.get("controls_covered", 0)
    total = report.get("total_controls", 0)
    ok(f"Audit readiness: {grade} ({score}/100)")
    ok(f"Controls covered: {covered}/{total}")


def print_demo_guide() -> None:
    head("Demo sequence")
    print(f"""
  {BOLD}Screen 1 — Release gets blocked (30 seconds){RESET}
  {CYAN}→{RESET} {CONSOLE}/release-gate
     Submit an action without evidence → watch it block
     Click 'Explain' → shows which gate failed and why

  {BOLD}Screen 2 — Same action, with evidence (30 seconds){RESET}
  {CYAN}→{RESET} {CONSOLE}/release-gate
     Add evidence references → submit → watch it release
     Click 'Evidence Chain' → shows cryptographic proof

  {BOLD}Screen 3 — Governance gaps detected (30 seconds){RESET}
  {CYAN}→{RESET} {CONSOLE}/cases
     Show live case queue → click a critical case
     Show affected planes → click 'Explain' → regulation citation

  {BOLD}Screen 4 — Compliance coverage (30 seconds){RESET}
  {CYAN}→{RESET} {CONSOLE}/compliance
     Show NIS2 controls → click Article 21(2)(e) → show evidence
     Export CSV → "this is what you give Ofcom"

  {BOLD}Screen 5 — Executive view (20 seconds){RESET}
  {CYAN}→{RESET} {CONSOLE}/executive
     Audit readiness grade, governance posture score
     One-click export for the board pack

  {BOLD}Competitive proof — run if challenged{RESET}
  {CYAN}→{RESET} python demos/run_all_proofs.py
     4 proofs: not workflow / not AI governance / not audit log / semantic gaps
     All assertions pass in < 30 seconds
""")


def print_key_commands() -> None:
    head("Commands to have ready during the demo")
    print(f"""
  {CYAN}python demo_release_governance.py{RESET}
    Full buyer walkthrough — release blocked, evidenced, released

  {CYAN}python demos/run_all_proofs.py{RESET}
    4 competitive proof scripts — all assertions pass

  {CYAN}curl {API}/compliance/readiness | python -m json.tool{RESET}
    Live production readiness check

  {CYAN}curl {API}/compliance/report/default | python -m json.tool{RESET}
    Live NIS2/Ofcom/SOC2/ISO27001 control coverage report

  {CYAN}curl {API}/health{RESET}  {CYAN}curl {API}/infra/health{RESET}
    Platform and infrastructure health
""")


def main() -> int:
    parser = argparse.ArgumentParser(description="Control Fabric Platform pre-flight check")
    parser.add_argument("--check", action="store_true", help="Check only, no seeding")
    parser.add_argument("--reset", action="store_true", help="Reset and reseed all data")
    args = parser.parse_args()

    print(f"\n{BOLD}Control Fabric Platform — Pre-flight Check{RESET}")
    print("=" * 50)
    print(f"API:     {API}")
    print(f"Console: {CONSOLE}")
    print(f"Time:    {time.strftime('%Y-%m-%d %H:%M:%S')}")

    platform_ok = check_platform_health()
    if not platform_ok:
        print(f"\n{RED}Platform not running. Run: make up{RESET}\n")
        return 1

    readiness_ok = check_readiness()

    if not args.check:
        apply_defaults()
        seed_demo_data()

    check_slm_adapters()
    check_compliance_coverage()

    print_demo_guide()
    print_key_commands()

    print("=" * 50)
    if readiness_ok:
        print(f"{GREEN}{BOLD}✓ Platform is demo-ready{RESET}\n")
    else:
        print(f"{AMBER}{BOLD}⚠ Platform has warnings — fix errors before customer demo{RESET}\n")

    return 0 if readiness_ok else 1


if __name__ == "__main__":
    sys.exit(main())
