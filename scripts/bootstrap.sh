#!/usr/bin/env bash
set -euo pipefail

echo "=== Control Fabric Platform Bootstrap ==="

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "Python 3.11+ required"; exit 1; }
command -v poetry >/dev/null 2>&1 || { echo "Poetry required — install from https://python-poetry.org"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "Docker required"; exit 1; }

# Install Python dependencies
echo "[1/4] Installing Python dependencies..."
poetry install

# Copy env file
if [ ! -f .env ]; then
  echo "[2/4] Creating .env from .env.example..."
  cp .env.example .env
  echo "  ⚠️  Please edit .env and fill in your API keys and secrets."
else
  echo "[2/4] .env already exists — skipping."
fi

# Start infrastructure services
echo "[3/4] Starting infrastructure (postgres, redis)..."
docker compose up -d db redis

# Wait for postgres
echo "  Waiting for PostgreSQL..."
until docker compose exec db pg_isready -U postgres >/dev/null 2>&1; do
  sleep 1
done

# Run migrations
echo "[4/4] Running database migrations..."
poetry run alembic upgrade head

echo ""
echo "=== Bootstrap complete ==="
echo "Run 'make dev' to start all services."
