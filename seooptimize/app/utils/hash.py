"""Hashing utilities for the knowledge cache."""

from __future__ import annotations

import hashlib


def sha256_of_string(text: str) -> str:
    """Return SHA-256 hex digest of a UTF-8 encoded string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_of_bytes(data: bytes) -> str:
    """Return SHA-256 hex digest of a byte sequence."""
    return hashlib.sha256(data).hexdigest()


def page_cache_key(url: str, html: str) -> str:
    """Derive a cache key from the URL and rendered HTML content.

    The key changes whenever the page content changes, triggering a fresh
    AI analysis.  Identical content returns the same key, skipping re-analysis.
    """
    combined = f"{url}::{html}"
    return sha256_of_string(combined)
