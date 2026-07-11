"""Streamlit session-state contract for SEOOptimize.

Streamlit binds widget ``key`` values to internal widget state. Application
code must never assign to a widget key after that widget has been rendered in
the session — even on later runs when the widget is hidden.

Pattern used here:
  - App keys (``export_lang``) — read/write freely from business logic.
  - Widget keys (``export_lang_select``) — owned by ``st.radio`` only.
  - Mirror widget → app via ``on_change`` callback.
  - Pre-widget initialization only when the widget key is not yet present.
"""

from __future__ import annotations

import streamlit as st

from app.models.project import ProjectConfig

# ── Key names ─────────────────────────────────────────────────────────────────
# App-owned (safe for services / export to read)
EXPORT_LANG = "export_lang"

# Widget-owned (must never be assigned after st.radio mounts)
EXPORT_LANG_SELECT = "export_lang_select"

# Legacy key from earlier implementation — migrated once, then ignored.
_LEGACY_REPORT_LANG = "report_lang"


def default_export_lang(project: ProjectConfig | None = None) -> str:
    """Derive default PDF language from project config."""
    if project and str(getattr(project, "language", "")).startswith("de"):
        return "de"
    return "en"


def init_app_state(project: ProjectConfig | None = None) -> None:
    """Initialize app-owned session keys (never widget keys)."""
    if EXPORT_LANG not in st.session_state:
        st.session_state[EXPORT_LANG] = default_export_lang(project)

    _migrate_legacy_report_lang()


def _migrate_legacy_report_lang() -> None:
    """One-time migration from the old widget-bound ``report_lang`` key."""
    if _LEGACY_REPORT_LANG not in st.session_state:
        return
    legacy = st.session_state.get(_LEGACY_REPORT_LANG)
    if legacy in ("en", "de") and EXPORT_LANG not in st.session_state:
        st.session_state[EXPORT_LANG] = legacy
    # Do not delete legacy key — it may still be widget-bound in old sessions.


def get_export_lang(project: ProjectConfig | None = None) -> str:
    """Return the app-owned export language preference."""
    lang = st.session_state.get(EXPORT_LANG)
    if lang in ("en", "de"):
        return lang
    return default_export_lang(project)


def _on_export_lang_changed() -> None:
    """Mirror widget selection into the app-owned key."""
    selected = st.session_state.get(EXPORT_LANG_SELECT)
    if selected in ("en", "de"):
        st.session_state[EXPORT_LANG] = selected


def reset_export_lang(project: ProjectConfig | None = None) -> None:
    """Reset export language when starting a new project.

    Deletes the widget key so the next sidebar render can pre-initialize it
    before ``st.radio`` mounts (safe only when the export widget is not on screen).
    """
    st.session_state[EXPORT_LANG] = default_export_lang(project)
    if EXPORT_LANG_SELECT in st.session_state:
        del st.session_state[EXPORT_LANG_SELECT]


def render_export_lang_selector(project: ProjectConfig | None) -> None:
    """Render the EN/DE radio and keep app state in sync.

    Must be called from the sidebar export panel only. Initializes the widget
    key once (before mount); never writes to it afterwards.
    """
    init_app_state(project)

    if EXPORT_LANG_SELECT not in st.session_state:
        st.session_state[EXPORT_LANG_SELECT] = get_export_lang(project)

    st.radio(
        "Report language",
        options=["en", "de"],
        format_func=lambda x: "🇬🇧 English" if x == "en" else "🇩🇪 Deutsch",
        horizontal=True,
        key=EXPORT_LANG_SELECT,
        on_change=_on_export_lang_changed,
        label_visibility="collapsed",
    )
