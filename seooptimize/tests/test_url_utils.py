"""Unit tests for URL utility functions."""

import pytest
from app.utils.url import (
    is_crawlable_page_url,
    normalise_url,
    is_same_origin,
    resolve_url,
    url_depth,
    get_root_url,
)


class TestNormaliseUrl:
    def test_strips_trailing_slash(self):
        assert normalise_url("https://example.com/page/") == "https://example.com/page"

    def test_lowercases_netloc(self):
        assert normalise_url("https://EXAMPLE.COM/page") == "https://example.com/page"

    def test_strips_fragment(self):
        assert normalise_url("https://example.com/page#section") == "https://example.com/page"

    def test_preserves_query(self):
        result = normalise_url("https://example.com/page?q=1")
        assert "q=1" in result

    def test_root_becomes_slash(self):
        assert normalise_url("https://example.com") == "https://example.com/"


class TestIsSameOrigin:
    def test_same_domain(self):
        assert is_same_origin("https://example.com", "https://example.com/page") is True

    def test_different_domain(self):
        assert is_same_origin("https://example.com", "https://other.com") is False

    def test_case_insensitive(self):
        assert is_same_origin("https://EXAMPLE.COM", "https://example.com/page") is True

    def test_different_subdomain(self):
        assert is_same_origin("https://example.com", "https://www.example.com") is False


class TestResolveUrl:
    def test_relative_path(self):
        result = resolve_url("https://example.com/page/", "/about")
        assert result == "https://example.com/about"

    def test_mailto_returns_none(self):
        assert resolve_url("https://example.com", "mailto:info@example.com") is None

    def test_tel_returns_none(self):
        assert resolve_url("https://example.com", "tel:+491234567") is None

    def test_javascript_returns_none(self):
        assert resolve_url("https://example.com", "javascript:void(0)") is None

    def test_absolute_url_preserved(self):
        result = resolve_url("https://example.com", "https://other.com/page")
        assert result == "https://other.com/page"

    def test_empty_href_returns_none(self):
        assert resolve_url("https://example.com", "") is None


class TestUrlDepth:
    def test_root_is_depth_zero(self):
        assert url_depth("https://example.com", "https://example.com") == 0

    def test_one_level_deep(self):
        assert url_depth("https://example.com", "https://example.com/about") == 1

    def test_two_levels_deep(self):
        assert url_depth("https://example.com", "https://example.com/a/b") == 2


class TestGetRootUrl:
    def test_extracts_root(self):
        assert get_root_url("https://example.com/path/to/page") == "https://example.com"

    def test_preserves_scheme(self):
        assert get_root_url("http://example.com/page") == "http://example.com"


class TestIsCrawlablePageUrl:
    def test_html_page_allowed(self):
        assert is_crawlable_page_url("https://example.com/leistungen") is True

    def test_image_rejected(self):
        assert is_crawlable_page_url("https://example.com/photo.jpg") is False

    def test_wp_uploads_rejected(self):
        assert (
            is_crawlable_page_url(
                "https://example.com/wp-content/uploads/collage-49.jpg"
            )
            is False
        )

    def test_mp3_rejected(self):
        assert (
            is_crawlable_page_url(
                "https://example.com/wp-content/uploads/audio.mp3"
            )
            is False
        )

    def test_root_allowed(self):
        assert is_crawlable_page_url("https://example.com/") is True
