#!/usr/bin/env python3
"""
Control Fabric Platform — SLM Enrichment Live Demo

Proves that domain-specific regulation citations are live today
via rule-based enrichment across all 8 domain adapters.

Run: python scripts/slm_enrichment_demo.py
Run: python scripts/slm_enrichment_demo.py --domain legal
Run: python scripts/slm_enrichment_demo.py --export  # writes demo_enrichment_results.json

Output:
  - Per-domain: input finding → regulation citations → evidence required
  - Latency per enrichment
  - Overall capability summary

This is the script you run during a demo when asked:
"Show me the AI/domain intelligence working right now"
"""

from __future__ import annotations

import argparse
import json
import sys
import time

GREEN = "\033[92m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


DEMO_SCENARIOS = {
    "telecom": {
        "finding": (
            "Production network change deployed without NIS2 security assessment or NOA approval"
        ),
        "plane": "operations",
        "regulatory_context": ["NIS2", "Ofcom"],
    },
    "legal": {
        "finding": (
            "New client matter opened without completed CDD documentation"
            " and AML source of funds check"
        ),
        "plane": "compliance",
        "regulatory_context": ["SRA", "AML", "MLR"],
    },
    "healthcare": {
        "finding": (
            "Software release deployed to clinical data system without"
            " FDA 21 CFR Part 11 validation report"
        ),
        "plane": "operations",
        "regulatory_context": ["FDA", "HIPAA"],
    },
    "banking": {
        "finding": (
            "Risk model change deployed to production without independent"
            " validation report or Model Risk Committee approval"
        ),
        "plane": "risk",
        "regulatory_context": ["SR11-7", "Basel", "BCBS"],
    },
    "insurance": {
        "finding": (
            "Internal model change deployed without PRA pre-approval for major model change"
        ),
        "plane": "compliance",
        "regulatory_context": ["Solvency"],
    },
    "manufacturing": {
        "finding": (
            "Production process change implemented without engineering change order or PFMEA update"
        ),
        "plane": "quality",
        "regulatory_context": ["ISO9001", "IATF"],
    },
    "semiconductor": {
        "finding": (
            "Controlled technical data shared with foreign national"
            " without export licence or denied party screening"
        ),
        "plane": "export_control",
        "regulatory_context": ["ITAR", "EAR"],
    },
    "finserv": {
        "finding": (
            "Production release with no change request or four-eyes"
            " approval for regulated financial system"
        ),
        "plane": "operations",
        "regulatory_context": ["FCA", "DORA"],
    },
}


def run_enrichment(domain: str, scenario: dict) -> dict:
    """Run rule-based enrichment for a domain and return results."""
    sys.path.insert(0, ".")
    adapter_map = {
        "telecom": (
            "app.core.inference.domain_adapters.telecom_adapter",
            "TelecomSLMAdapter",
        ),
        "legal": (
            "app.core.inference.domain_adapters.legal_adapter",
            "LegalSLMAdapter",
        ),
        "healthcare": (
            "app.core.inference.domain_adapters.healthcare_adapter",
            "HealthcareSLMAdapter",
        ),
        "banking": (
            "app.core.inference.domain_adapters.banking_adapter",
            "BankingSLMAdapter",
        ),
        "insurance": (
            "app.core.inference.domain_adapters.insurance_adapter",
            "InsuranceSLMAdapter",
        ),
        "manufacturing": (
            "app.core.inference.domain_adapters.manufacturing_adapter",
            "ManufacturingSLMAdapter",
        ),
        "semiconductor": (
            "app.core.inference.domain_adapters.semiconductor_adapter",
            "SemiconductorSLMAdapter",
        ),
        "finserv": (
            "app.core.inference.domain_adapters.finserv_adapter",
            "FinServSLMAdapter",
        ),
    }
    import importlib

    module_path, class_name = adapter_map[domain]
    mod = importlib.import_module(module_path)
    adapter_class = getattr(mod, class_name)
    adapter = adapter_class()

    from app.core.inference.slm_router import SLMContext

    context = SLMContext(
        operational_plane=scenario["plane"],
        object_types=["regulatory_mandate"],
        hypothesis_type="gap_analysis",
        regulatory_context=scenario["regulatory_context"],
    )

    start = time.perf_counter()
    enrichment = adapter.enrich_hypothesis(scenario["finding"], context, [])
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    return {
        "domain": domain,
        "finding": scenario["finding"],
        "plane": scenario["plane"],
        "regulatory_context": scenario["regulatory_context"],
        "regulation_citations": enrichment.regulation_citations,
        "specific_clause": enrichment.specific_clause,
        "domain_specific_risk": enrichment.domain_specific_risk,
        "prescribed_evidence_types": enrichment.prescribed_evidence_types,
        "remediation_precision": enrichment.remediation_precision,
        "confidence_boost": enrichment.confidence_boost,
        "latency_ms": latency_ms,
        "adapter_type": "rule_based",
    }


def print_result(result: dict) -> None:
    domain = result["domain"]
    citations = result["regulation_citations"]
    evidence = result["prescribed_evidence_types"]
    latency = result["latency_ms"]

    print(f"\n{BOLD}{'─' * 60}{RESET}")
    print(f"{BOLD}{domain.upper()}{RESET} {DIM}({result['plane']}){RESET}")

    print(f"\n  {DIM}Finding:{RESET}")
    print(f"  {result['finding'][:100]}...")

    if citations:
        print(f"\n  {GREEN}Regulation citations ({len(citations)}):{RESET}")
        for c in citations[:3]:
            print(f"    {CYAN}·{RESET} {c[:90]}")
    else:
        print("\n  ⚠ No citations produced — check adapter configuration")

    if evidence:
        print("\n  Required evidence:")
        for e in evidence[:4]:
            print(f"    · {e.replace('_', ' ')}")

    if result["domain_specific_risk"]:
        risk_preview = result["domain_specific_risk"][:120]
        print(f"\n  Risk: {DIM}{risk_preview}...{RESET}")

    print(f"\n  {DIM}Latency: {latency}ms · Adapter: rule-based{RESET}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", help="Run single domain only")
    parser.add_argument("--export", action="store_true", help="Export results to JSON")
    parser.add_argument("--quiet", action="store_true", help="Summary only")
    args = parser.parse_args()

    print(f"\n{BOLD}Control Fabric Platform — Domain SLM Enrichment Demo{RESET}")
    print("Proving: rule-based regulation citations are live across all 8 domains\n")

    domains = [args.domain] if args.domain else list(DEMO_SCENARIOS.keys())
    results = []
    passed = 0
    failed = 0

    for domain in domains:
        if domain not in DEMO_SCENARIOS:
            print(f"Unknown domain: {domain}")
            continue
        try:
            result = run_enrichment(domain, DEMO_SCENARIOS[domain])
            results.append(result)
            if result["regulation_citations"]:
                passed += 1
                if not args.quiet:
                    print_result(result)
            else:
                failed += 1
                print(f"  ✗ {domain}: no citations produced")
        except Exception as e:
            failed += 1
            print(f"  ✗ {domain}: {e}")
            results.append({"domain": domain, "error": str(e)})

    # Summary
    print(f"\n{'=' * 60}")
    print(f"{BOLD}Summary{RESET}")
    print(f"  Domains with live citations: {passed}/{len(domains)}")
    avg_latency = round(
        sum(r.get("latency_ms", 0) for r in results if "latency_ms" in r) / max(passed, 1),
        2,
    )
    print(f"  Average enrichment latency: {avg_latency}ms")
    total_citations = sum(len(r.get("regulation_citations", [])) for r in results)
    print(f"  Total regulation citations produced: {total_citations}")

    if passed == len(domains):
        print(
            f"\n  {GREEN}✓ All {len(domains)} domain adapters producing"
            f" live regulation citations{RESET}"
        )
        print(
            f"  {GREEN}✓ Rule-based enrichment active —"
            f" no GPU training required for citations{RESET}"
        )
    else:
        print(f"\n  ⚠ {failed} domains not producing citations — check adapter imports")

    # Export
    if args.export:
        export = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "adapter_type": "rule_based",
            "domains_tested": len(domains),
            "domains_with_citations": passed,
            "avg_latency_ms": avg_latency,
            "total_citations": total_citations,
            "results": results,
        }
        with open("demo_enrichment_results.json", "w") as f:
            json.dump(export, f, indent=2)
        print("\n  Results exported to: demo_enrichment_results.json")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
