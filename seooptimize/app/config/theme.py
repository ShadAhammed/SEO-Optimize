"""Streamlit theme constants and CSS injection."""

# Streamlit config is written to .streamlit/config.toml at startup.
# These constants are also used by components that build their own HTML.

BRAND_PRIMARY = "#1E40AF"       # Deep blue — professional, trustworthy
BRAND_SECONDARY = "#0F172A"     # Near-black — sidebar background
BRAND_ACCENT = "#3B82F6"        # Lighter blue — interactive elements

SCORE_CRITICAL = "#DC2626"      # Red
SCORE_WARNING = "#D97706"       # Amber
SCORE_OK = "#16A34A"            # Green
SCORE_INFO = "#6B7280"          # Grey

FONT_FAMILY = "Inter, system-ui, sans-serif"

# Priority badge colours (background, text)
PRIORITY_COLORS: dict[str, tuple[str, str]] = {
    "critical": ("#FEE2E2", "#991B1B"),
    "warning": ("#FEF3C7", "#92400E"),
    "quick_win": ("#D1FAE5", "#065F46"),
    "ok": ("#F3F4F6", "#374151"),
}

# Score axis colours for the radar/bar chart
AXIS_COLORS: dict[str, str] = {
    "local_seo": "#1E40AF",
    "content_quality": "#7C3AED",
    "technical_seo": "#0F766E",
    "conversion_signals": "#B45309",
    "on_page_metadata": "#0369A1",
    "competitor_gap": "#6B7280",
}

CUSTOM_CSS = """
<style>
/* ── Global typography ──────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: Inter, system-ui, sans-serif;
}

/* ── Sidebar ──────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background-color: #0F172A;
}
section[data-testid="stSidebar"] * {
    color: #CBD5E1 !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background-color: transparent;
    border: 1px solid #334155;
    color: #CBD5E1 !important;
    width: 100%;
    text-align: left;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    margin-bottom: 2px;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #1E293B;
    border-color: #3B82F6;
}

/* ── Recommendation cards ────────────────────────────────────────────── */
.rec-card {
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 1.25rem;
    margin-bottom: 1rem;
    background: #FFFFFF;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
.rec-card-critical { border-left: 4px solid #DC2626; }
.rec-card-warning  { border-left: 4px solid #D97706; }
.rec-card-quick_win { border-left: 4px solid #16A34A; }
.rec-card-ok       { border-left: 4px solid #6B7280; }

/* ── Score badge ─────────────────────────────────────────────────────── */
.score-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
}

/* ── Section headers ─────────────────────────────────────────────────── */
.section-label {
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #64748B;
    margin-bottom: 0.25rem;
}

/* ── Form inputs: no grey placeholder hints ──────────────────────────── */
input::placeholder,
textarea::placeholder {
    color: transparent !important;
    opacity: 0 !important;
}
</style>
"""
