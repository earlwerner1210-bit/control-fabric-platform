"""Simple Prometheus-compatible metrics collector."""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager

from prometheus_client import Counter, Histogram, Info

# ── Application info ───────────────────────────────────────────────────

APP_INFO = Info("control_fabric", "Control Fabric Platform build information")


# ── Counters ───────────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

LLM_CALL_COUNT = Counter(
    "llm_calls_total",
    "Total LLM inference calls",
    ["provider", "model"],
)

VALIDATION_COUNT = Counter(
    "validations_total",
    "Total validation runs",
    ["target_type", "status"],
)


# ── Histograms ─────────────────────────────────────────────────────────

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

LLM_LATENCY = Histogram(
    "llm_call_duration_seconds",
    "LLM call latency in seconds",
    ["provider", "model"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)


class RequestMetrics:
    """Convenience wrapper for recording HTTP request metrics."""

    @staticmethod
    def record_request(
        method: str,
        endpoint: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        """Record a completed HTTP request."""
        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code),
        ).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration_seconds)

    @staticmethod
    @contextmanager
    def track(method: str, endpoint: str) -> Generator[None, None, None]:
        """Context manager that times a request and records metrics.

        Usage::

            with RequestMetrics.track("GET", "/api/v1/health"):
                ...
        """
        start = time.perf_counter()
        status_code = 200
        try:
            yield
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start
            RequestMetrics.record_request(method, endpoint, status_code, duration)

    @staticmethod
    def record_llm_call(
        provider: str,
        model: str,
        duration_seconds: float,
    ) -> None:
        """Record a completed LLM inference call."""
        LLM_CALL_COUNT.labels(provider=provider, model=model).inc()
        LLM_LATENCY.labels(provider=provider, model=model).observe(duration_seconds)
