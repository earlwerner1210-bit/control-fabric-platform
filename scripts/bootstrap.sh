#!/usr/bin/env bash
###############################################################################
# Control Fabric Platform -- Bootstrap Script
#
# Sets up the complete local development environment:
#   1. Checks prerequisites (Python, Docker, pip/poetry)
#   2. Installs Python dependencies
#   3. Creates .env from .env.example if needed
#   4. Starts infrastructure containers (postgres, redis, temporal)
#   5. Waits for PostgreSQL to be ready
#   6. Runs database migrations
#   7. Seeds sample data
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

echo ""
echo "======================================"
echo " Control Fabric Platform -- Bootstrap"
echo "======================================"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Check prerequisites
# ---------------------------------------------------------------------------
info "Checking prerequisites..."

# Python 3.11+
if ! command -v python3 &>/dev/null; then
    fail "Python 3 is required but not found. Install Python 3.11+ from https://python.org"
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]; }; then
    fail "Python 3.11+ required (found $PYTHON_VERSION)"
fi
ok "Python $PYTHON_VERSION"

# Docker
if ! command -v docker &>/dev/null; then
    fail "Docker is required but not found. Install from https://docker.com"
fi
ok "Docker $(docker --version | grep -oP '\d+\.\d+\.\d+' | head -1)"

# Docker Compose
if ! docker compose version &>/dev/null; then
    fail "Docker Compose v2 is required. Update Docker or install docker-compose-plugin."
fi
ok "Docker Compose $(docker compose version --short 2>/dev/null || echo 'v2')"

echo ""

# ---------------------------------------------------------------------------
# Step 2: Install Python dependencies
# ---------------------------------------------------------------------------
info "[1/5] Installing Python dependencies..."

if command -v poetry &>/dev/null; then
    poetry install --no-interaction
    ok "Dependencies installed via Poetry"
else
    pip install -e ".[dev]" 2>/dev/null || pip install -e . 2>/dev/null || {
        warn "Could not install via pip, installing key packages directly"
        pip install fastapi uvicorn pydantic sqlalchemy alembic httpx \
            pydantic-settings pytest pytest-asyncio pytest-cov
    }
    ok "Dependencies installed via pip"
fi

echo ""

# ---------------------------------------------------------------------------
# Step 3: Create .env file
# ---------------------------------------------------------------------------
info "[2/5] Setting up environment..."

if [ ! -f .env ]; then
    cp .env.example .env
    ok "Created .env from .env.example"
    warn "Edit .env and fill in your API keys and secrets before running services."
else
    ok ".env already exists -- skipping"
fi

echo ""

# ---------------------------------------------------------------------------
# Step 4: Start infrastructure containers
# ---------------------------------------------------------------------------
info "[3/5] Starting infrastructure containers (postgres, redis, temporal)..."

docker compose up -d postgres redis temporal temporal-ui

ok "Infrastructure containers started"

echo ""

# ---------------------------------------------------------------------------
# Step 5: Wait for PostgreSQL
# ---------------------------------------------------------------------------
info "[4/5] Waiting for PostgreSQL to be ready..."

MAX_RETRIES=30
RETRY_COUNT=0

while ! docker compose exec -T postgres pg_isready -U postgres &>/dev/null; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        fail "PostgreSQL did not become ready within ${MAX_RETRIES}s"
    fi
    sleep 1
done

ok "PostgreSQL is ready"

echo ""

# ---------------------------------------------------------------------------
# Step 6: Run migrations
# ---------------------------------------------------------------------------
info "[5/5] Running database migrations..."

if command -v alembic &>/dev/null || python3 -m alembic --help &>/dev/null 2>&1; then
    alembic upgrade head 2>/dev/null || python3 -m alembic upgrade head 2>/dev/null || {
        warn "Alembic migrations not available yet (need alembic.ini + versions). Skipping."
    }
else
    warn "Alembic not installed. Skipping migrations."
fi

echo ""

# ---------------------------------------------------------------------------
# Step 7: Seed data
# ---------------------------------------------------------------------------
info "Seeding sample data..."

python3 data/seed/seed_data.py 2>/dev/null || {
    warn "Seed script failed (database tables may not exist yet). Run 'make seed' after migrations."
}

echo ""

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo "======================================"
echo ""
ok "Bootstrap complete!"
echo ""
echo "  Next steps:"
echo "    1. Edit .env with your API keys"
echo "    2. Run 'make dev' to start all services"
echo "    3. Open http://localhost:8000/docs for API docs"
echo "    4. Open http://localhost:8088 for Temporal UI"
echo "    5. Run 'make test' to verify everything works"
echo ""
echo "======================================"
