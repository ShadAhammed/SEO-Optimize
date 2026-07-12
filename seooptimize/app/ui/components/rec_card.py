"""Recommendation card component (SEOArch.md §5 specification)."""

from __future__ import annotations

import streamlit as st

from app.config.theme import PRIORITY_COLORS
from app.models.recommendations import RecommendationCard, UserAction


def render_recommendation_card(card: RecommendationCard, index: int) -> None:
    """Render a single recommendation card following the spec layout.

    Updates card.user_action in session state when user clicks Accept/Reject/Edit.
    """
    bg, fg = PRIORITY_COLORS.get(card.priority.value, ("#F3F4F6", "#374151"))

    priority_label = {
        "critical": "🔴 CRITICAL",
        "warning": "🟡 WARNING",
        "quick_win": "🟢 QUICK WIN",
        "ok": "⚪ OK",
    }.get(card.priority.value, card.priority.value.upper())

    with st.container():
        st.markdown(
            f"""
            <div class="rec-card rec-card-{card.priority.value}">
                <div style="display:flex;justify-content:space-between;align-items:center;
                            margin-bottom:0.5rem;flex-wrap:wrap;gap:6px;">
                    <span style="background:{bg};color:{fg};padding:3px 10px;
                                 border-radius:9999px;font-weight:700;font-size:0.8rem;">
                        {priority_label}
                    </span>
                </div>
                <div style="font-size:0.75rem;color:#64748B;margin-bottom:0.75rem;">
                    Confidence: <strong>{card.confidence*100:.0f}%</strong>
                    &nbsp;|&nbsp; Impact: <strong>{card.impact.value.upper()}</strong>
                    &nbsp;|&nbsp; <code>{card.selector}</code>
                </div>
                <h4 style="margin:0 0 0.75rem 0;font-size:1rem;">{card.label}</h4>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("View Details", expanded=(card.priority.value == "critical")):
            # ── Problem ──────────────────────────────────────────────────
            st.markdown(
                f"<p class='section-label'>PROBLEM</p>{card.problem}",
                unsafe_allow_html=True,
            )

            # ── Why it matters ────────────────────────────────────────────
            st.markdown(
                f"<p class='section-label' style='margin-top:0.75rem;'>WHY IT MATTERS</p>"
                f"{card.why_it_matters}",
                unsafe_allow_html=True,
            )

            # ── Competitor evidence ───────────────────────────────────────
            if card.competitor_evidence:
                st.markdown(
                    "<p class='section-label' style='margin-top:0.75rem;'>"
                    "COMPETITOR EVIDENCE</p>",
                    unsafe_allow_html=True,
                )
                for name, evidence in card.competitor_evidence.items():
                    st.markdown(
                        f"<div style='background:#F8FAFC;padding:6px 10px;"
                        f"border-radius:6px;margin-bottom:4px;font-size:0.85rem;'>"
                        f"<strong>{name}:</strong> {evidence}</div>",
                        unsafe_allow_html=True,
                    )

            # ── Reviewer note (DeepSeek / Gemini) ────────────────────────
            if card.gemini_note:
                st.markdown(
                    f"<div style='background:#EFF6FF;border-left:3px solid #3B82F6;"
                    f"padding:8px 12px;border-radius:4px;margin:8px 0;font-size:0.82rem;'>"
                    f"<strong>AI reviewer note:</strong> {card.gemini_note}</div>",
                    unsafe_allow_html=True,
                )

            # ── Suggested fix ─────────────────────────────────────────────
            st.markdown(
                "<p class='section-label' style='margin-top:0.75rem;'>"
                "SUGGESTED FIX (ready to paste)</p>",
                unsafe_allow_html=True,
            )
            st.code(card.display_fix, language=None)

            # ── Expected impact ───────────────────────────────────────────
            if card.expected_impact:
                st.markdown(
                    f"<p class='section-label' style='margin-top:0.75rem;'>"
                    f"EXPECTED IMPACT</p>{card.expected_impact}",
                    unsafe_allow_html=True,
                )

            # ── Action buttons ────────────────────────────────────────────
            st.markdown("<div style='margin-top:0.75rem;'></div>", unsafe_allow_html=True)
            col_a, col_e, col_r, col_ai = st.columns(4)

            state_key = f"card_action_{card.card_id}"

            with col_a:
                if st.button(
                    "✅ Accept",
                    key=f"accept_{card.card_id}_{index}",
                    use_container_width=True,
                    type="primary",
                ):
                    st.session_state[state_key] = UserAction.ACCEPTED
                    st.rerun()

            with col_e:
                if st.button(
                    "✏️ Edit",
                    key=f"edit_{card.card_id}_{index}",
                    use_container_width=True,
                ):
                    st.session_state[f"editing_{card.card_id}"] = True

            with col_r:
                if st.button(
                    "✗ Reject",
                    key=f"reject_{card.card_id}_{index}",
                    use_container_width=True,
                ):
                    st.session_state[state_key] = UserAction.REJECTED
                    st.rerun()

            with col_ai:
                if st.button(
                    "🤖 Ask AI",
                    key=f"ask_ai_{card.card_id}_{index}",
                    use_container_width=True,
                ):
                    st.session_state[f"ask_ai_{card.card_id}"] = True

            # ── Inline edit field ─────────────────────────────────────────
            if st.session_state.get(f"editing_{card.card_id}"):
                edited = st.text_area(
                    "Edit the suggested fix:",
                    value=card.display_fix,
                    key=f"edit_text_{card.card_id}_{index}",
                )
                if st.button("Save Edit", key=f"save_edit_{card.card_id}_{index}"):
                    card.user_edited_fix = edited
                    st.session_state[state_key] = UserAction.EDITED
                    st.session_state[f"editing_{card.card_id}"] = False
                    st.rerun()

            # ── Current action status ─────────────────────────────────────
            action = st.session_state.get(state_key, UserAction.PENDING)
            if action != UserAction.PENDING:
                action_labels = {
                    UserAction.ACCEPTED: "✅ Accepted",
                    UserAction.REJECTED: "✗ Rejected",
                    UserAction.EDITED: "✏️ Edited and saved",
                }
                st.info(f"Status: {action_labels.get(action, action.value)}")
