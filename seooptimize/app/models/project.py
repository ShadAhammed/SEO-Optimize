"""Project-level data models — business profile and configuration."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, HttpUrl, field_validator


class BusinessCategory(str, Enum):
    """Supported business categories.

    The category drives keyword-intent classification and urgency-signal
    detection.  Clearance companies use transactional patterns; lawyers use
    informational patterns.
    """

    CLEARANCE = "clearance"           # Entrümpelungsservice
    CLEANING = "cleaning"             # Reinigungsservice
    TRADE = "trade"                   # Handwerksbetrieb (general)
    LEGAL = "legal"                   # Anwaltskanzlei
    MEDICAL = "medical"               # Arztpraxis / Physiotherapie
    RETAIL = "retail"                 # Einzelhandel
    RESTAURANT = "restaurant"         # Gastronomie
    REAL_ESTATE = "real_estate"       # Immobilien
    CONSTRUCTION = "construction"     # Bauunternehmen
    OTHER = "other"


CATEGORY_LABELS: dict[BusinessCategory, str] = {
    BusinessCategory.CLEARANCE: "Clearance / Entrümpelungsservice",
    BusinessCategory.CLEANING: "Cleaning Service",
    BusinessCategory.TRADE: "Trade / Handwerk",
    BusinessCategory.LEGAL: "Legal / Anwaltskanzlei",
    BusinessCategory.MEDICAL: "Medical / Healthcare",
    BusinessCategory.RETAIL: "Retail",
    BusinessCategory.RESTAURANT: "Restaurant / Gastronomie",
    BusinessCategory.REAL_ESTATE: "Real Estate / Immobilien",
    BusinessCategory.CONSTRUCTION: "Construction / Bau",
    BusinessCategory.OTHER: "Other",
}


class ProjectConfig(BaseModel):
    """Complete project configuration supplied by the user (Module A)."""

    # Required fields
    business_name: str = Field(
        ..., min_length=1, max_length=200, description="Legal or trading name"
    )
    website_url: str = Field(..., description="Primary website URL to analyse")
    business_category: BusinessCategory = Field(..., description="Business type")
    target_city: str = Field(
        ..., min_length=1, max_length=100, description="Primary service city"
    )

    # Optional fields
    service_areas: list[str] = Field(
        default_factory=list,
        description="Additional cities / towns in the service area",
    )
    competitor_urls: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Up to 8 competitor website URLs",
    )
    primary_keyword: str = Field(
        default="",
        description="Main target keyword (auto-derived if blank)",
    )
    language: str = Field(default="de", description="Primary content language (ISO 639-1)")

    @field_validator("website_url", "competitor_urls", mode="before")
    @classmethod
    def ensure_https_scheme(cls, v: str | list) -> str | list:
        def _fix(url: str) -> str:
            url = url.strip()
            if url and not url.startswith(("http://", "https://")):
                return f"https://{url}"
            return url

        if isinstance(v, list):
            return [_fix(u) for u in v if u.strip()]
        return _fix(v)

    @property
    def derived_keyword(self) -> str:
        """Best guess at the primary target keyword if not explicitly set."""
        if self.primary_keyword:
            return self.primary_keyword
        category_keywords: dict[BusinessCategory, str] = {
            BusinessCategory.CLEARANCE: "Entrümpelung",
            BusinessCategory.CLEANING: "Reinigungsservice",
            BusinessCategory.TRADE: "Handwerker",
            BusinessCategory.LEGAL: "Rechtsanwalt",
            BusinessCategory.MEDICAL: "Arztpraxis",
            BusinessCategory.RETAIL: "Geschäft",
            BusinessCategory.RESTAURANT: "Restaurant",
            BusinessCategory.REAL_ESTATE: "Immobilien",
            BusinessCategory.CONSTRUCTION: "Bauunternehmen",
            BusinessCategory.OTHER: self.business_name,
        }
        base = category_keywords.get(self.business_category, self.business_name)
        return f"{base} {self.target_city}"
