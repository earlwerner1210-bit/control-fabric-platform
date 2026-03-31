"""
Run all four competitive proof demonstrations in sequence.
Produces a summary report suitable for a buyer conversation.

Run: python demos/run_all_proofs.py
"""

import importlib
import sys
import time

sys.path.insert(0, ".")


def main():
    print("\n" + "=" * 65)
    print("  CONTROL FABRIC PLATFORM — COMPETITIVE PROOF SUITE")
    print("  Runs: 4 proofs")
    print("=" * 65)

    proofs = [
        ("Not a workflow tool", "demos.proof_not_workflow", "run"),
        ("Not AI governance only", "demos.proof_not_ai_governance", "run"),
        (
            "Not post-hoc audit logging",
            "demos.proof_not_audit_logging",
            "run",
        ),
        (
            "Semantic vs data gaps",
            "demos.proof_semantic_gap_detection",
            "run",
        ),
    ]

    results = []
    for label, module, fn_name in proofs:
        print(f"\n{'─' * 65}")
        print(f"  Running: {label}")
        print(f"{'─' * 65}")
        try:
            mod = importlib.import_module(module)
            start = time.perf_counter()
            getattr(mod, fn_name)()
            elapsed = round((time.perf_counter() - start) * 1000)
            results.append((label, "PASSED", elapsed))
        except AssertionError as e:
            results.append((label, f"FAILED: {e}", 0))
        except Exception as e:
            results.append((label, f"ERROR: {e}", 0))

    print("\n" + "=" * 65)
    print("  PROOF SUITE RESULTS")
    print("=" * 65)
    all_passed = True
    for label, result_status, ms in results:
        icon = "PASS" if result_status == "PASSED" else "FAIL"
        print(f"  [{icon}] {label:<35} {result_status}  ({ms}ms)")
        if result_status != "PASSED":
            all_passed = False

    print(
        "\n"
        + (
            "  All proofs passed."
            if all_passed
            else "  One or more proofs failed — check output above."
        )
    )
    print("=" * 65 + "\n")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
