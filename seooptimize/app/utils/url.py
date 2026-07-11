"""URL utility functions."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse

# Static assets and media files are not HTML pages — skip during crawl/render.
_NON_HTML_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".bmp",
    ".mp3",
    ".mp4",
    ".wav",
    ".ogg",
    ".webm",
    ".pdf",
    ".zip",
    ".rar",
    ".css",
    ".js",
    ".mjs",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".xml",
)


def normalise_url(url: str) -> str:
    """Normalise a URL: lowercase scheme+host, strip trailing slash, remove fragment."""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    # Drop fragment; keep query
    normalised = urlunparse((scheme, netloc, path, "", parsed.query, ""))
    return normalised


def is_same_origin(base_url: str, candidate_url: str) -> bool:
    """Return True if candidate_url shares scheme+host with base_url."""
    base = urlparse(base_url)
    cand = urlparse(candidate_url)
    return base.netloc.lower() == cand.netloc.lower()


def resolve_url(base_url: str, href: str) -> str | None:
    """Resolve a potentially relative href against base_url.

    Returns None for non-HTTP/HTTPS URLs (mailto:, tel:, javascript:, etc.).
    """
    if not href:
        return None
    href = href.strip()
    if href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return None
    resolved = urljoin(base_url, href)
    parsed = urlparse(resolved)
    if parsed.scheme not in ("http", "https"):
        return None
    return resolved


def url_depth(base_url: str, page_url: str) -> int:
    """Calculate crawl depth of page_url relative to base_url root.

    Depth 0 = the root URL itself.
    Depth 1 = one level below root.
    """
    base_path = urlparse(base_url).path.strip("/")
    page_path = urlparse(page_url).path.strip("/")
    if not page_path:
        return 0
    base_parts = [p for p in base_path.split("/") if p]
    page_parts = [p for p in page_path.split("/") if p]
    depth = len(page_parts) - len(base_parts)
    return max(0, depth)


def get_root_url(url: str) -> str:
    """Return scheme + netloc (e.g. https://example.com)."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def is_crawlable_page_url(url: str) -> bool:
    """Return True if the URL should be crawled/rendered as an HTML page."""
    parsed = urlparse(url)
    path = parsed.path.lower().rstrip("/")

    if not path or path == "/":
        return True

    if any(path.endswith(ext) for ext in _NON_HTML_EXTENSIONS):
        return False

    # WordPress media folders and common asset paths.
    blocked_fragments = (
        "/wp-content/uploads/",
        "/wp-content/themes/",
        "/wp-content/plugins/",
        "/wp-includes/",
        "/assets/",
        "/static/",
        "/cdn-cgi/",
    )
    return not any(fragment in path for fragment in blocked_fragments)
