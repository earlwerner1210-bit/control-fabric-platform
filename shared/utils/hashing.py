"""File checksum and content fingerprinting utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path


def file_checksum(path: str | Path, algorithm: str = "sha256", chunk_size: int = 8192) -> str:
    """Compute a hex-digest checksum of a file on disk.

    Parameters
    ----------
    path:
        Path to the file.
    algorithm:
        Hash algorithm name (default ``sha256``).
    chunk_size:
        Read buffer size in bytes.

    Returns
    -------
    str
        Hex-encoded hash digest.
    """
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def content_checksum(data: bytes, algorithm: str = "sha256") -> str:
    """Compute a hex-digest checksum for in-memory bytes.

    Parameters
    ----------
    data:
        Raw bytes to hash.
    algorithm:
        Hash algorithm name.

    Returns
    -------
    str
        Hex-encoded hash digest.
    """
    return hashlib.new(algorithm, data).hexdigest()


def content_fingerprint(text: str) -> str:
    """Produce a stable fingerprint for textual content.

    The input is lowered, stripped, and whitespace-normalised before hashing
    so that trivial formatting differences do not change the fingerprint.
    """
    normalised = " ".join(text.lower().split())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()
