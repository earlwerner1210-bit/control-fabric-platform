"""
Input sanitisation for the Control Fabric Platform.

Prevents:
  - XSS via HTML injection in text fields
  - Oversized payloads causing resource exhaustion
  - Control characters in identifiers
  - Path traversal in file references
  - SSRF via URL fields

Used as a FastAPI dependency or called directly in route handlers.
"""

from __future__ import annotations

import ipaddress
import os
import re
import unicodedata
from typing import Any
from urllib.parse import urlparse

# Maximum lengths per field type
MAX_LENGTHS = {
    "default": 2048,
    "description": 4096,
    "title": 512,
    "identifier": 128,
    "url": 2048,
    "justification": 4096,
    "free_text": 8192,
}

# Patterns that should never appear in identifiers
DANGEROUS_PATTERNS = [
    re.compile(r"[<>\"'%;()&+]"),  # XSS chars
    re.compile(r"\.\./"),  # Path traversal
    re.compile(r"javascript:", re.IGNORECASE),  # JS injection
    re.compile(r"data:", re.IGNORECASE),  # Data URI injection
]


def sanitise_string(
    value: str,
    field_type: str = "default",
    allow_html: bool = False,
) -> str:
    """Sanitise a string value for safe storage and display."""
    if not isinstance(value, str):
        return str(value)

    # Strip null bytes and control characters
    value = "".join(
        ch
        for ch in value
        if unicodedata.category(ch) not in ("Cc", "Cs") or ch in ("\n", "\r", "\t")
    )

    # Strip HTML unless explicitly allowed
    if not allow_html:
        try:
            import bleach

            value = bleach.clean(value, tags=[], strip=True)
        except ImportError:
            # bleach not available — use basic regex strip
            value = re.sub(r"<[^>]+>", "", value)

    # Truncate to maximum length
    max_len = MAX_LENGTHS.get(field_type, MAX_LENGTHS["default"])
    if len(value) > max_len:
        value = value[:max_len]

    return value.strip()


def sanitise_identifier(value: str) -> str:
    """
    Sanitise an identifier (tenant ID, pack ID, user ID).
    Allows only alphanumeric, hyphens, and underscores.
    """
    if not isinstance(value, str):
        return ""
    # Allow only safe identifier characters
    sanitised = re.sub(r"[^a-zA-Z0-9\-_.]", "", value)
    return sanitised[: MAX_LENGTHS["identifier"]]


def sanitise_dict(data: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    """
    Recursively sanitise all string values in a dict.
    Limits recursion to 5 levels deep to prevent stack overflow.
    """
    if depth > 5:
        return {}
    result = {}
    for key, value in data.items():
        safe_key = sanitise_identifier(str(key))
        if isinstance(value, str):
            result[safe_key] = sanitise_string(value)
        elif isinstance(value, dict):
            result[safe_key] = sanitise_dict(value, depth + 1)
        elif isinstance(value, list):
            result[safe_key] = [
                sanitise_string(v)
                if isinstance(v, str)
                else sanitise_dict(v, depth + 1)
                if isinstance(v, dict)
                else v
                for v in value[:100]  # cap list length
            ]
        else:
            result[safe_key] = value
    return result


def validate_url(url: str, allowed_schemes: list[str] | None = None) -> tuple[bool, str]:
    """Validate a URL is safe (not SSRF, not javascript:)."""
    if not url:
        return True, ""
    url_lower = url.lower().strip()
    # Block dangerous schemes
    dangerous = ["javascript:", "data:", "file:", "ftp:", "gopher:"]
    for scheme in dangerous:
        if url_lower.startswith(scheme):
            return False, f"URL scheme not allowed: {scheme}"
    # Block private/internal addresses in production
    if os.getenv("ENVIRONMENT", "development") == "production":
        try:
            parsed = urlparse(url)
            host = parsed.hostname or ""
            # Block localhost and private IPs
            private_hosts = ["localhost", "127.0.0.1", "0.0.0.0", "::1"]
            if host in private_hosts:
                return False, f"Internal host not permitted: {host}"
            try:
                addr = ipaddress.ip_address(host)
                if addr.is_private or addr.is_loopback or addr.is_link_local:
                    return False, f"Private IP not permitted: {host}"
            except ValueError:
                pass  # Not an IP address — allow
        except Exception:
            pass
    return True, ""
