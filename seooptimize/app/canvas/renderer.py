"""Visual Canvas Bridge — Module G.

Renders PIL overlays on top of Playwright screenshots.

The bridge works as follows (SEOArch.md §Module G):

1. During Playwright rendering (Module C), we capture element bounding boxes
   using `page.locator(selector).first.bounding_box()`.

2. Claude returns annotations that reference CSS selectors.

3. This renderer looks up the selector in element_boxes to get the pixel
   rectangle, then draws a coloured semi-transparent overlay on the screenshot.

The output is a PIL Image that can be displayed in Streamlit or embedded
in the PDF export.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import IO

from PIL import Image, ImageDraw, ImageFont

from app.core.logging import get_logger
from app.models.annotations import Annotation
from app.models.page import BoundingBox

logger = get_logger(__name__)

# ── Colour palette (RGBA) — from SEOArch.md §Module G ─────────────────────
COLORS: dict[str, tuple[int, int, int, int]] = {
    "critical":  (220, 50,  50,  160),
    "warning":   (240, 160,  0,  160),
    "quick_win": (40,  180, 40,  160),
    "ok":        (100, 100, 100, 100),
}

BORDER_COLORS: dict[str, tuple[int, int, int]] = {
    "critical":  (220, 50,  50),
    "warning":   (240, 160,  0),
    "quick_win": (40,  180, 40),
    "ok":        (100, 100, 100),
}

LABEL_BG: dict[str, tuple[int, int, int, int]] = {
    "critical":  (180, 0,   0,   220),
    "warning":   (200, 120, 0,   220),
    "quick_win": (0,   140, 0,   220),
    "ok":        (80,  80,  80,  220),
}


def render_canvas(
    screenshot_path: str,
    annotations: list[Annotation],
    element_boxes: dict[str, BoundingBox],
) -> Image.Image:
    """Render annotation overlays on a screenshot.

    Args:
        screenshot_path: Path to the full-page PNG screenshot.
        annotations: List of Annotation objects from Claude/Consensus.
        element_boxes: CSS selector → BoundingBox map from Playwright.

    Returns:
        PIL Image with RGBA overlays composited onto the screenshot.
    """
    img = Image.open(screenshot_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font = _load_font(size=13)
    label_font = _load_font(size=11, bold=True)

    rendered_count = 0

    for ann in annotations:
        box = element_boxes.get(ann.selector)
        if not box:
            # Try partial selector match (e.g. "h1" matches "h1" in "h1, h2")
            box = _fuzzy_match_box(ann.selector, element_boxes)

        if not box:
            logger.debug("No bounding box for selector: %s", ann.selector)
            continue

        x, y, w, h = box.x, box.y, box.width, box.height
        priority = ann.priority.value

        fill_color = COLORS.get(priority, COLORS["warning"])
        border_color = BORDER_COLORS.get(priority, BORDER_COLORS["warning"])
        label_bg = LABEL_BG.get(priority, LABEL_BG["warning"])

        # ── Draw semi-transparent fill ─────────────────────────────────────
        draw.rectangle(
            [x, y, x + w, y + h],
            fill=fill_color,
            outline=border_color,
            width=2,
        )

        # ── Draw label badge ───────────────────────────────────────────────
        label_text = ann.label[:30]
        label_w = len(label_text) * 7 + 10
        label_h = 18
        label_x = x
        label_y = max(0, y - label_h)

        draw.rectangle(
            [label_x, label_y, label_x + label_w, label_y + label_h],
            fill=label_bg,
        )
        draw.text(
            (label_x + 4, label_y + 3),
            label_text,
            fill=(255, 255, 255, 230),
            font=label_font,
        )

        rendered_count += 1

    logger.debug(
        "Rendered %d/%d annotations on canvas",
        rendered_count,
        len(annotations),
    )

    composited = Image.alpha_composite(img, overlay)
    return composited.convert("RGB")


def render_canvas_to_bytes(
    screenshot_path: str,
    annotations: list[Annotation],
    element_boxes: dict[str, BoundingBox],
    format: str = "PNG",
) -> bytes:
    """Render canvas and return as bytes (for Streamlit or PDF embedding).

    Args:
        screenshot_path: Path to the full-page PNG.
        annotations: Annotation list.
        element_boxes: Bounding box map.
        format: Output image format ('PNG' or 'JPEG').

    Returns:
        Image bytes.
    """
    img = render_canvas(screenshot_path, annotations, element_boxes)
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


def _load_font(size: int = 12, bold: bool = False) -> ImageFont.ImageFont:
    """Load a TrueType font if available, falling back to the default."""
    try:
        # Prefer a bundled font or system font
        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/verdana.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for path in font_paths:
            if Path(path).exists():
                return ImageFont.truetype(path, size)
    except Exception:
        pass
    return ImageFont.load_default()


def _fuzzy_match_box(
    selector: str,
    element_boxes: dict[str, BoundingBox],
) -> BoundingBox | None:
    """Find the best matching bounding box for a selector using partial matching."""
    # Direct match
    if selector in element_boxes:
        return element_boxes[selector]

    # Try individual parts of compound selectors
    parts = [s.strip() for s in selector.split(",")]
    for part in parts:
        if part in element_boxes:
            return element_boxes[part]

    # Fuzzy: selector starts with or matches a prefix
    selector_lower = selector.lower()
    for key, box in element_boxes.items():
        key_lower = key.lower()
        if (
            selector_lower.startswith(key_lower)
            or key_lower.startswith(selector_lower)
            or selector_lower in key_lower
        ):
            return box

    return None
