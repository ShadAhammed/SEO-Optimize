"""Prompt templates for Claude and Gemini — Modules H and I.

All prompts are pure Python strings. No raw HTML is ever included in these
prompts (SEOArch.md §AI Philosophy).
"""

from __future__ import annotations

import json
from typing import Any

CLAUDE_SYSTEM_PROMPT = """You are a senior SEO consultant specializing in local service businesses in Germany.
You receive structured extraction data only. Do not invent or assume information not provided.
Never send generic advice. Every suggestion must be ready to implement immediately.
Always include the city name in title/H1 rewrites for local businesses.
Phone number placement is a conversion priority, not just a contact item.
NAP consistency issues are high-priority for local pack rankings.
Service pages need 600+ words to compete in local search."""

REVIEWER_SYSTEM_PROMPT = """You are an independent SEO critic and competitor intelligence analyst.
Your job is to review the primary analyst's recommendations, not repeat deterministic analysis.
Only report features where competitors outperform the client.
Never mention competitor weaknesses, errors, or lower scores."""

_ISSUE_STATUSES = {"warn", "fail", "warning"}


def build_claude_prompt(
    business_name: str,
    business_category: str,
    city: str,
    page_url: str,
    structured_data: dict[str, Any],
    section_id: str = "page",
    competitor_summary: dict[str, Any] | None = None,
) -> str:
    """Build the Claude primary SEO analysis prompt (Module H spec).

    Args:
        business_name: e.g. 'Fischer Entruempelungen'
        business_category: e.g. 'clearance'
        city: e.g. 'Siegen'
        page_url: URL of the page being analysed
        structured_data: The structured JSON from extraction (never raw HTML)

    Returns:
        Complete prompt string ready to send to Claude.
    """
    data_json = json.dumps(structured_data, ensure_ascii=False, indent=2)

    competitor_block = ""
    if competitor_summary and competitor_summary.get("competitor_gap_counts"):
        gap_counts = competitor_summary["competitor_gap_counts"]
        examples = competitor_summary.get("examples", {})
        current = competitor_summary.get("current_site", {})

        gap_lines = []
        for feature, count in gap_counts.items():
            ex = examples.get(feature, [])
            example_str = f" — e.g. {ex[0]}" if ex else ""
            gap_lines.append(f"  - {feature}: {count} competitor(s) have this{example_str}")

        current_lines = [
            f"  - FAQ section present: {'Yes' if current.get('has_faq') else 'NO — competitors have one'}",
            f"  - Review signals: {'Yes' if current.get('has_reviews') else 'NO — competitors show reviews'}",
            f"  - WhatsApp button: {'Yes' if current.get('has_whatsapp') else 'NO — competitors have it'}",
            f"  - Schema markup: {current.get('schema_status', 'unknown')}",
            f"  - H2 headings on page: {current.get('h2_count', 0)}",
        ]

        competitor_block = (
            "\n\nCOMPETITOR GAPS (features competitors have that this site lacks):\n"
            + "\n".join(gap_lines)
            + "\n\nCURRENT SITE STATUS:\n"
            + "\n".join(current_lines)
            + "\n\nFor each competitor gap, add an annotation referencing it explicitly."
            " Quote what competitors have. Focus only on gaps where competitors outperform this site."
        )

    return f"""{CLAUDE_SYSTEM_PROMPT}

You are analyzing section "{section_id}" for: {business_name}, a {business_category} business in {city}.

Page URL: {page_url}

The page has already been scanned by a deterministic extraction engine.
You are receiving only fields that require reasoning (WARNING/FAIL), scoped to the current section.

STRUCTURED SECTION DATA:
{data_json}{competitor_block}

Your task:
1. Evaluate the SEO quality of each issue provided.
2. For each issue found, reference the exact HTML selector (h1, meta[name="description"], etc.).
3. Generate a specific, ready-to-use improvement (not generic advice).
   - For German local businesses: use local keywords like "{business_category} {city}"
   - For clearance/trade businesses: emphasize urgency, trust, and local intent
4. Classify each finding as: critical / warning / quick_win / ok
5. Estimate the SEO impact of fixing this issue: high / medium / low
6. For each competitor gap listed above, create an annotation explaining what competitors have
   and exactly what this site should add. Set impact to "high".

Return ONLY valid JSON. No markdown, no explanation outside the JSON structure.

{{
  "page_score": <integer 0-100>,
  "annotations": [
    {{
      "selector": "<css selector string>",
      "label": "<short badge text, max 4 words>",
      "priority": "<critical|warning|quick_win|ok>",
      "issue": "<what is wrong, specific to this page>",
      "why_it_matters": "<business language explanation, 1-2 sentences>",
      "suggested_fix": "<exact replacement text or precise instruction, ready to use>",
      "impact": "<high|medium|low>",
      "confidence": <float 0.0-1.0>
    }}
  ],
  "top_priority_action": "<3-5 bullet points in plain business language for a non-technical website owner. Name the exact page object (headline, page title, phone number, footer, etc.). Say what text or part should change. Never use CSS selectors or HTML jargon.>"
}}"""


def build_gemini_prompt(
    business_name: str,
    city: str,
    page_url: str,
    claude_annotations: list[dict[str, Any]],
    competitor_data: list[dict[str, Any]] | dict[str, Any],
    structured_data: dict[str, Any] | None = None,
    section_id: str = "page",
) -> str:
    """Build the Gemini independent review + competitor lens prompt (Module I spec).

    Args:
        business_name: Business name.
        city: Primary service city.
        page_url: Page URL.
        structured_data: Extraction results (same as sent to Claude).
        claude_annotations: Claude's annotation output.
        competitor_data: List of extracted competitor page data.

    Returns:
        Complete prompt string for Gemini.
    """
    claude_json = json.dumps(claude_annotations, ensure_ascii=False, indent=2)
    competitor_json = json.dumps(competitor_data, ensure_ascii=False, indent=2)
    scoped_json = (
        json.dumps(structured_data, ensure_ascii=False, indent=2)
        if structured_data
        else "{}"
    )

    return f"""{REVIEWER_SYSTEM_PROMPT}
You are reviewing an SEO analysis of: {business_name} in {city}.
Page URL: {page_url}
Section: {section_id}

You have two inputs:
1. The primary analyst's annotations (CLAUDE ANNOTATIONS)
2. A compact deterministic competitor summary (COMPETITOR SUMMARY)
3. Optional scoped section issue data for context

CLAUDE ANNOTATIONS:
{claude_json}

COMPETITOR SUMMARY (local competitors in {city}):
{competitor_json}

SCOPED SECTION CONTEXT:
{scoped_json}

YOUR TASKS:

Task 1 — Validate Claude's findings:
For each Claude annotation, decide:
- "agree": Claude is correct — confirm and strengthen if needed
- "strengthen": Claude is right but understates the severity
- "reject": Claude is wrong — explain why
- "add": Claude missed something important that you are adding

Task 2 — Competitor evidence:
For each finding, check if a competitor does this better.
The business owner must feel motivated to act, not reassured by competitor failures.

Task 3 — Add missing findings:
If the competitor data reveals gaps that Claude missed, add them as "add" verdicts.

Return ONLY valid JSON:

{{
  "reviews": [
    {{
      "selector": "<same css selector as Claude used>",
      "gemini_verdict": "<agree|strengthen|reject|add>",
      "gemini_note": "<your reasoning, 1-2 sentences>",
      "competitor_evidence": {{
        "<competitor name or url>": "<their H1, title, or feature that outperforms client>"
      }},
      "revised_suggestion": "<improved version of Claude's suggestion, or empty string>"
    }}
  ],
  "additional_annotations": [
    {{
      "selector": "<selector>",
      "label": "<max 4 words>",
      "priority": "<critical|warning|quick_win|ok>",
      "issue": "<what is missing>",
      "why_it_matters": "<business impact>",
      "suggested_fix": "<specific fix>",
      "impact": "<high|medium|low>",
      "confidence": <float 0.0-1.0>
    }}
  ]
}}"""


def build_structured_page_data(
    page_data: dict[str, Any],
    project_config: dict[str, Any],
) -> dict[str, Any]:
    """Build the structured JSON sent to AI providers.

    This is the intermediary between raw extraction results and AI prompts.
    Never includes raw HTML — only structured, scored data.

    Args:
        page_data: Serialised PageData dict.
        project_config: Serialised ProjectConfig dict.

    Returns:
        Cleaned structured dict suitable for AI consumption.
    """
    extracted = page_data.get("extracted", {})
    local_seo = page_data.get("local_seo", {})
    scores = page_data.get("scores", {})

    def _field(key: str) -> dict[str, Any]:
        field = extracted.get(key, {})
        return {
            "status": field.get("status", "na"),
            "value": field.get("value"),
            "note": field.get("note", ""),
        }

    return {
        "page": {
            "url": page_data.get("url", ""),
            "title": page_data.get("title", ""),
        },
        "business": {
            "name": project_config.get("business_name", ""),
            "category": project_config.get("business_category", ""),
            "city": project_config.get("target_city", ""),
            "keyword": project_config.get("primary_keyword", ""),
            "service_areas": project_config.get("service_areas", []),
        },
        "seo_fields": {
            "meta_title": _field("meta_title"),
            "meta_description": _field("meta_description"),
            "h1": _field("h1"),
            "h2_structure": _field("h2_structure"),
            "word_count": _field("word_count"),
            "images_with_alt": _field("images_with_alt"),
            "phone_above_fold": _field("phone_above_fold"),
            "schema_markup": _field("schema_markup"),
            "canonical_tag": _field("canonical_tag"),
            "mobile_viewport": _field("mobile_viewport"),
            "nap_on_page": _field("nap_on_page"),
            "internal_links": _field("internal_links"),
            "page_load_time": _field("page_load_time"),
            "https": _field("https"),
        },
        "local_seo": {
            "nap_consistent": local_seo.get("nap_consistent", False),
            "nap_phone": local_seo.get("nap_phone", ""),
            "nap_address": local_seo.get("nap_address", ""),
            "nap_issues": local_seo.get("nap_issues", []),
            "has_local_business_schema": local_seo.get("has_local_business_schema", False),
            "schema_missing_fields": local_seo.get("schema_missing_fields", []),
            "city_in_title": local_seo.get("city_in_title", False),
            "city_in_h1": local_seo.get("city_in_h1", False),
            "city_mention_count": local_seo.get("city_mention_count", 0),
            "has_review_signals": local_seo.get("has_review_signals", False),
            "phone_above_fold_mobile": local_seo.get("phone_above_fold_mobile", False),
            "has_whatsapp": local_seo.get("has_whatsapp", False),
            "has_response_time_claim": local_seo.get("has_response_time_claim", False),
            "has_free_inspection": local_seo.get("has_free_inspection", False),
            "urgency_score": local_seo.get("urgency_score", 0.0),
        },
        "headings": extracted.get("all_headings", [])[:10],
        "schema_objects": extracted.get("schema_objects", [])[:5],
        "faq_items": extracted.get("faq_items", [])[:5],
        "scores": {
            "local_seo": scores.get("local_seo", 0),
            "content_quality": scores.get("content_quality", 0),
            "technical_seo": scores.get("technical_seo", 0),
            "conversion_signals": scores.get("conversion_signals", 0),
            "on_page_metadata": scores.get("on_page_metadata", 0),
            "total": (
                scores.get("local_seo", 0)
                + scores.get("content_quality", 0)
                + scores.get("technical_seo", 0)
                + scores.get("conversion_signals", 0)
                + scores.get("on_page_metadata", 0)
                + scores.get("competitor_gap", 0)
            ),
        },
    }


def build_section_payloads(structured_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Split structured page data into logical sections containing only issues.

    PASS/OK fields are intentionally excluded so they never consume AI tokens.
    """
    seo_fields = structured_data.get("seo_fields", {})
    local_seo = structured_data.get("local_seo", {})

    def issue_fields(*names: str) -> dict[str, Any]:
        issues: dict[str, Any] = {}
        for name in names:
            field = seo_fields.get(name, {})
            status = str(field.get("status", "")).lower()
            if status in _ISSUE_STATUSES:
                issues[name] = field
        return issues

    local_issues: dict[str, Any] = {}
    if local_seo.get("nap_issues"):
        local_issues["nap_issues"] = local_seo.get("nap_issues", [])
    for key in (
        "has_local_business_schema",
        "city_in_title",
        "city_in_h1",
        "has_review_signals",
        "phone_above_fold_mobile",
        "has_whatsapp",
        "has_response_time_claim",
        "has_free_inspection",
    ):
        if local_seo.get(key) is False:
            local_issues[key] = False
    if local_seo.get("schema_missing_fields"):
        local_issues["schema_missing_fields"] = local_seo["schema_missing_fields"]

    base = {
        "page": structured_data.get("page", {}),
        "business": structured_data.get("business", {}),
    }

    sections = {
        "metadata": {
            **base,
            "seo_fields": issue_fields(
                "meta_title",
                "meta_description",
                "canonical_tag",
                "mobile_viewport",
                "page_load_time",
                "https",
            ),
        },
        "hero": {
            **base,
            "seo_fields": issue_fields("h1", "phone_above_fold"),
            "headings": structured_data.get("headings", [])[:3],
        },
        "services": {
            **base,
            "seo_fields": issue_fields(
                "h2_structure",
                "word_count",
                "images_with_alt",
                "internal_links",
            ),
            "headings": structured_data.get("headings", [])[:10],
        },
        "faq": {
            **base,
            "seo_fields": issue_fields("schema_markup"),
            "faq_items": structured_data.get("faq_items", [])[:5],
            "schema_objects": structured_data.get("schema_objects", [])[:2],
        },
        "cta": {
            **base,
            "seo_fields": issue_fields("phone_above_fold", "nap_on_page"),
            "local_seo": {
                key: value
                for key, value in local_issues.items()
                if key
                in {
                    "has_review_signals",
                    "phone_above_fold_mobile",
                    "has_whatsapp",
                    "has_response_time_claim",
                    "has_free_inspection",
                }
            },
        },
        "footer": {
            **base,
            "seo_fields": issue_fields("nap_on_page", "schema_markup"),
            "local_seo": {
                key: value
                for key, value in local_issues.items()
                if key in {"nap_issues", "schema_missing_fields", "has_local_business_schema"}
            },
        },
    }

    return {
        section_id: payload
        for section_id, payload in sections.items()
        if payload.get("seo_fields") or payload.get("local_seo") or payload.get("faq_items")
    }


def build_competitor_summary(
    competitor_data: list[dict[str, Any]],
    client_data: dict[str, Any],
) -> dict[str, Any]:
    """Compress competitor gaps into counts/features instead of raw page data."""
    client_local = client_data.get("local_seo", {})
    client_seo = client_data.get("seo_fields", {})
    feature_counts: dict[str, int] = {}
    examples: dict[str, list[str]] = {}

    for competitor in competitor_data:
        domain = competitor.get("domain") or competitor.get("url", "competitor")
        for feature, value in competitor.get("positive_features", {}).items():
            feature_counts[feature] = feature_counts.get(feature, 0) + 1
            examples.setdefault(feature, [])
            if len(examples[feature]) < 2:
                examples[feature].append(f"{domain}: {value}")

    return {
        "competitor_gap_counts": feature_counts,
        "examples": examples,
        "current_site": {
            "has_faq": bool(client_data.get("faq_items")),
            "has_reviews": bool(client_local.get("has_review_signals")),
            "has_whatsapp": bool(client_local.get("has_whatsapp")),
            "schema_status": client_seo.get("schema_markup", {}).get("status", "na"),
            "word_count_status": client_seo.get("word_count", {}).get("status", "na"),
            "h2_count": client_seo.get("h2_count", {}).get("value", 0),
        },
    }
