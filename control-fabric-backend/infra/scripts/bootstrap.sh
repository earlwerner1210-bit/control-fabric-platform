#!/usr/bin/env bash
# bootstrap.sh – Set up the local development environment from scratch.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "==> Control Fabric Backend – Bootstrap"
echo "    Project root: $PROJECT_ROOT"

# ── 1. Check Python ──────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is not installed or not on PATH."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "    Python version: $PYTHON_VERSION"

REQUIRED_MAJOR=3
REQUIRED_MINOR=12
ACTUAL_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
ACTUAL_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$ACTUAL_MAJOR" -lt "$REQUIRED_MAJOR" ] || { [ "$ACTUAL_MAJOR" -eq "$REQUIRED_MAJOR" ] && [ "$ACTUAL_MINOR" -lt "$REQUIRED_MINOR" ]; }; then
    echo "WARNING: Python >= $REQUIRED_MAJOR.$REQUIRED_MINOR recommended (found $PYTHON_VERSION)."
fi

# ── 2. Install dependencies ─────────────────────────────────────────────────
echo "==> Installing Python dependencies..."
cd "$PROJECT_ROOT"
pip install --upgrade pip
pip install -e ".[dev]" 2>/dev/null || pip install -e .
pip install pytest pytest-asyncio pytest-cov httpx ruff mypy

# ── 3. Copy .env if missing ─────────────────────────────────────────────────
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "==> Copying .env.example -> .env"
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
else
    echo "    .env already exists, skipping copy."
fi

# ── 4. Start infrastructure via Docker Compose ───────────────────────────────
echo "==> Starting Docker Compose services..."
docker compose -f "$PROJECT_ROOT/docker-compose.yml" up -d postgres redis temporal temporal-ui

# ── 5. Wait for Postgres ────────────────────────────────────────────────────
echo "==> Waiting for PostgreSQL to become ready..."
MAX_WAIT=30
WAITED=0
until docker compose -f "$PROJECT_ROOT/docker-compose.yml" exec -T postgres pg_isready -U postgres &>/dev/null; do
    sleep 1
    WAITED=$((WAITED + 1))
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        echo "ERROR: PostgreSQL did not become ready within ${MAX_WAIT}s."
        exit 1
    fi
done
echo "    PostgreSQL is ready (waited ${WAITED}s)."

# ── 6. Run migrations ───────────────────────────────────────────────────────
echo "==> Running Alembic migrations..."
cd "$PROJECT_ROOT"
alembic upgrade head

# ── 7. Seed data ────────────────────────────────────────────────────────────
echo "==> Seeding sample data..."
python3 "$PROJECT_ROOT/infra/scripts/seed_data.py"

echo ""
echo "==> Bootstrap complete!"
echo "    API:         http://localhost:8000"
echo "    Temporal UI: http://localhost:8088"
echo "    Postgres:    localhost:5432"
echo "    Redis:       localhost:6379"
