"""Unit tests for hashing utilities."""

import pytest
from app.utils.hash import sha256_of_string, sha256_of_bytes, page_cache_key


class TestSha256OfString:
    def test_returns_64_char_hex(self):
        result = sha256_of_string("hello")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self):
        assert sha256_of_string("test") == sha256_of_string("test")

    def test_different_inputs_different_hash(self):
        assert sha256_of_string("a") != sha256_of_string("b")


class TestSha256OfBytes:
    def test_returns_64_char_hex(self):
        result = sha256_of_bytes(b"hello")
        assert len(result) == 64

    def test_matches_string_version(self):
        # Same content should produce same hash
        assert sha256_of_bytes("test".encode("utf-8")) == sha256_of_string("test")


class TestPageCacheKey:
    def test_deterministic(self):
        key1 = page_cache_key("https://example.com", "<html>content</html>")
        key2 = page_cache_key("https://example.com", "<html>content</html>")
        assert key1 == key2

    def test_different_url_different_key(self):
        key1 = page_cache_key("https://example.com", "<html></html>")
        key2 = page_cache_key("https://other.com", "<html></html>")
        assert key1 != key2

    def test_different_html_different_key(self):
        key1 = page_cache_key("https://example.com", "<html>v1</html>")
        key2 = page_cache_key("https://example.com", "<html>v2</html>")
        assert key1 != key2

    def test_returns_64_char_hex(self):
        key = page_cache_key("https://example.com", "<html></html>")
        assert len(key) == 64
