"""Tests for rate limit middleware."""

from __future__ import annotations

import pytest

from app.api.middleware.rate_limit import RateLimitMiddleware, _Bucket


class TestBucket:
    """Token bucket unit tests."""

    def test_consume_success(self):
        bucket = _Bucket(tokens=10.0, max_tokens=10.0, refill_rate=1.0)
        assert bucket.consume() is True
        assert bucket.tokens < 10.0

    def test_consume_exhausted(self):
        bucket = _Bucket(tokens=0.0, max_tokens=10.0, refill_rate=0.0)
        assert bucket.consume() is False

    def test_consume_multiple(self):
        bucket = _Bucket(tokens=3.0, max_tokens=10.0, refill_rate=0.0)
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is False

    def test_refill(self):
        import time
        bucket = _Bucket(tokens=0.0, max_tokens=10.0, refill_rate=1000.0)
        # Wait a tiny bit for refill
        time.sleep(0.01)
        assert bucket.consume() is True

    def test_max_cap(self):
        bucket = _Bucket(tokens=10.0, max_tokens=10.0, refill_rate=1000.0)
        import time
        time.sleep(0.01)
        bucket.consume()
        # Tokens should not exceed max
        assert bucket.tokens <= bucket.max_tokens


class TestRateLimitMiddleware:
    """Rate limit middleware tests."""

    def test_exempt_paths(self):
        middleware = RateLimitMiddleware(app=None, exempt_paths={"/health", "/ready"})
        assert "/health" in middleware.exempt_paths
        assert "/ready" in middleware.exempt_paths

    def test_default_config(self):
        middleware = RateLimitMiddleware(app=None)
        assert middleware.max_tokens == 100.0
        assert middleware.refill_rate == 10.0

    def test_custom_config(self):
        middleware = RateLimitMiddleware(app=None, max_tokens=50.0, refill_rate=5.0)
        assert middleware.max_tokens == 50.0
        assert middleware.refill_rate == 5.0
