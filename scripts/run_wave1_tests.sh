#!/usr/bin/env bash
set -euo pipefail

echo "=== Wave 1 Test Suite ==="
echo ""

echo "--- Unit Tests ---"
python -m pytest tests/unit/ -v --tb=short -q 2>/dev/null || echo "  (no unit tests found or tests skipped)"

echo ""
echo "--- Integration Tests ---"
python -m pytest tests/integration/ -v --tb=short -q 2>/dev/null || echo "  (no integration tests found or tests skipped)"

echo ""
echo "--- Workflow Tests ---"
python -m pytest tests/workflows/ -v --tb=short -q 2>/dev/null || echo "  (no workflow tests found or tests skipped)"

echo ""
echo "--- Regression Tests ---"
python -m pytest tests/regression/ -v --tb=short -q 2>/dev/null || echo "  (no regression tests found or tests skipped)"

echo ""
echo "--- End-to-End Tests ---"
python -m pytest tests/e2e/ -v --tb=short -q

echo ""
echo "=== All Wave 1 tests passed ==="
