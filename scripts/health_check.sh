#!/usr/bin/env bash
###############################################################################
# Health check script for Control Fabric Platform
###############################################################################
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
MAX_RETRIES=10
RETRY_DELAY=3

echo "Checking Control Fabric Platform health..."
echo "API URL: $API_URL"
echo ""

# ── Health endpoint ────────────────────────────────────────────────────
for i in $(seq 1 $MAX_RETRIES); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/health" 2>/dev/null || echo "000")
    if [ "$STATUS" = "200" ]; then
        echo "✓ Health check passed (attempt $i)"
        BODY=$(curl -s "$API_URL/health")
        echo "  Response: $BODY"
        break
    fi
    echo "  Attempt $i/$MAX_RETRIES: status=$STATUS, retrying in ${RETRY_DELAY}s..."
    sleep $RETRY_DELAY
done

if [ "$STATUS" != "200" ]; then
    echo "✗ Health check failed after $MAX_RETRIES attempts"
    exit 1
fi

# ── Readiness endpoint ────────────────────────────────────────────────
echo ""
READY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/ready" 2>/dev/null || echo "000")
if [ "$READY_STATUS" = "200" ]; then
    READY_BODY=$(curl -s "$API_URL/ready")
    echo "✓ Readiness check passed"
    echo "  Response: $READY_BODY"
else
    echo "⚠ Readiness check returned: $READY_STATUS"
fi

# ── Metrics endpoint ──────────────────────────────────────────────────
echo ""
METRICS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/metrics" 2>/dev/null || echo "000")
if [ "$METRICS_STATUS" = "200" ]; then
    echo "✓ Metrics endpoint accessible"
else
    echo "⚠ Metrics endpoint returned: $METRICS_STATUS"
fi

echo ""
echo "Health check complete."
