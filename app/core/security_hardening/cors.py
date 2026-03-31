"""
CORS configuration for the Control Fabric Platform API.

Production: Restrict to known frontend origins only.
Development: Allow localhost variants.
Enterprise: Configured per deployment via environment variables.
"""

from __future__ import annotations

import os


def get_cors_origins() -> list[str]:
    """
    Returns allowed CORS origins.
    Override with CORS_ALLOWED_ORIGINS env var (comma-separated).
    """
    env_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if env_origins:
        return [o.strip() for o in env_origins.split(",") if o.strip()]

    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        # Production: only the configured console origin
        console_url = os.getenv("CONSOLE_URL", "")
        origins = ["https://console.control-fabric.io"]
        if console_url:
            origins.append(console_url)
        return origins

    # Development / staging: allow localhost variants
    return [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://0.0.0.0:3000",
    ]


CORS_CONFIG = {
    "allow_origins": get_cors_origins(),
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    "allow_headers": [
        "Authorization",
        "Content-Type",
        "X-Tenant-ID",
        "X-Request-ID",
        "X-Hub-Signature-256",
        "X-GitHub-Event",
        "X-Atlassian-Token",
    ],
    "expose_headers": ["X-Tenant-ID", "X-Request-ID"],
    "max_age": 600,
}
