#!/usr/bin/env bash
###############################################################################
# Run the full Control Fabric Platform test suite with coverage
###############################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "============================================================"
echo " Control Fabric Platform - Full Test Suite"
echo "============================================================"
echo ""

# ── Unit Tests ─────────────────────────────────────────────────────────
echo "▸ Running unit tests..."
python -m pytest tests/unit/ -v --tb=short \
    --cov=app \
    --cov-report=term-missing \
    --junitxml=reports/junit-unit.xml \
    || { echo "✗ Unit tests failed"; exit 1; }
echo ""

# ── API Tests ──────────────────────────────────────────────────────────
echo "▸ Running API tests..."
python -m pytest tests/api/ -v --tb=short \
    --junitxml=reports/junit-api.xml \
    || { echo "✗ API tests failed"; exit 1; }
echo ""

# ── Integration Tests ─────────────────────────────────────────────────
echo "▸ Running integration tests..."
python -m pytest tests/integration/ -v --tb=short \
    --junitxml=reports/junit-integration.xml \
    || { echo "✗ Integration tests failed"; exit 1; }
echo ""

# ── Workflow Tests ─────────────────────────────────────────────────────
echo "▸ Running workflow tests..."
python -m pytest tests/workflows/ -v --tb=short \
    --junitxml=reports/junit-workflows.xml \
    || { echo "✗ Workflow tests failed"; exit 1; }
echo ""

# ── E2E Tests ──────────────────────────────────────────────────────────
echo "▸ Running e2e tests..."
python -m pytest tests/e2e/ -v --tb=short \
    --junitxml=reports/junit-e2e.xml \
    || { echo "✗ E2E tests failed"; exit 1; }
echo ""

# ── Regression Tests ──────────────────────────────────────────────────
echo "▸ Running regression tests..."
python -m pytest tests/regression/ -v --tb=short \
    --junitxml=reports/junit-regression.xml \
    || { echo "✗ Regression tests failed"; exit 1; }
echo ""

# ── Combined Coverage ─────────────────────────────────────────────────
echo "============================================================"
echo "▸ Running all tests with combined coverage..."
python -m pytest tests/ -v \
    --cov=app \
    --cov-report=term-missing \
    --cov-report=html:reports/htmlcov \
    --cov-report=xml:reports/coverage.xml \
    --junitxml=reports/junit-all.xml

echo ""
echo "============================================================"
echo " ✓ All test suites passed"
echo " Coverage report: reports/htmlcov/index.html"
echo "============================================================"
