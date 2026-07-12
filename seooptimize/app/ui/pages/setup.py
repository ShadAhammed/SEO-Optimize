"""Project Setup page — Module A.

Collects: business name, URL, category, city, service areas, competitor URLs.
"""

from __future__ import annotations

import streamlit as st

from app.models.project import CATEGORY_LABELS, BusinessCategory, ProjectConfig

# Stable widget keys — bump suffix if form defaults ever need a full reset.
_FORM_KEY = "project_setup_v2"
_FIELD_KEYS = {
    "business_name": "setup_business_name",
    "target_city": "setup_target_city",
    "website_url": "setup_website_url",
    "service_areas": "setup_service_areas",
    "primary_keyword": "setup_primary_keyword",
}


def render_setup_page() -> ProjectConfig | None:
    """Render the project setup form and return ProjectConfig on submit.

    Returns:
        ProjectConfig if the form was submitted with valid data, else None.
    """
    st.markdown(
        """
        <div style="max-width:700px;margin:0 auto;">
            <h1 style="font-size:2rem;font-weight:800;margin-bottom:0.25rem;">
                SEOOptimize
            </h1>
            <p style="color:#64748B;margin-bottom:2rem;">
                Local SEO analysis for service businesses. Enter your website details
                to begin a full audit.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form(_FORM_KEY, clear_on_submit=False):
        st.markdown("### Business Information")

        col1, col2 = st.columns(2)
        with col1:
            business_name = st.text_input(
                "Business Name *",
                key=_FIELD_KEYS["business_name"],
                help="Legal or trading name of the business",
            )
        with col2:
            target_city = st.text_input(
                "Primary Service City *",
                key=_FIELD_KEYS["target_city"],
                help="The main city or area the business serves",
            )

        category_options = list(CATEGORY_LABELS.values())
        category_values = list(CATEGORY_LABELS.keys())
        selected_label = st.selectbox(
            "Business Category *",
            options=category_options,
            key="setup_business_category",
            help="Drives keyword intent classification and urgency signals",
        )
        selected_category = category_values[category_options.index(selected_label)]

        st.markdown("### Website")
        website_url = st.text_input(
            "Primary Website URL *",
            key=_FIELD_KEYS["website_url"],
            help="The website you want to analyse",
        )

        st.markdown("### Service Areas (Optional)")
        service_areas_raw = st.text_input(
            "Additional cities (comma-separated)",
            key=_FIELD_KEYS["service_areas"],
            help="Other cities or towns in the service area",
        )

        primary_keyword = st.text_input(
            "Primary Target Keyword (optional)",
            key=_FIELD_KEYS["primary_keyword"],
            help="Leave blank to auto-derive from business category and city",
        )

        st.markdown("### Competitor URLs (up to 8)")
        st.caption(
            "Enter competitor website URLs to enable gap analysis and competitor evidence."
        )
        competitor_cols = st.columns(2)
        competitor_urls: list[str] = []
        for i in range(8):
            col = competitor_cols[i % 2]
            with col:
                url = st.text_input(
                    f"Competitor {i + 1}",
                    key=f"setup_competitor_{i}",
                )
                if url.strip():
                    competitor_urls.append(url.strip())

        st.markdown("---")
        submitted = st.form_submit_button(
            "Start Analysis",
            use_container_width=True,
            type="primary",
        )

        if submitted:
            errors: list[str] = []
            if not business_name.strip():
                errors.append("Business name is required.")
            if not website_url.strip():
                errors.append("Website URL is required.")
            if not target_city.strip():
                errors.append("Primary service city is required.")

            if errors:
                for err in errors:
                    st.error(err)
                return None

            service_areas = [
                s.strip()
                for s in service_areas_raw.split(",")
                if s.strip()
            ]

            try:
                config = ProjectConfig(
                    business_name=business_name.strip(),
                    website_url=website_url.strip(),
                    business_category=selected_category,
                    target_city=target_city.strip(),
                    service_areas=service_areas,
                    competitor_urls=competitor_urls,
                    primary_keyword=primary_keyword.strip(),
                )
                return config
            except Exception as exc:
                st.error(f"Configuration error: {exc}")
                return None

    return None
