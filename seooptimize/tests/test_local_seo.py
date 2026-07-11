"""Unit tests for the Local SEO Analyser (Module E)."""

import pytest
from app.extractors.local_seo import LocalSEOAnalyser


@pytest.fixture
def analyser() -> LocalSEOAnalyser:
    return LocalSEOAnalyser()


@pytest.fixture
def good_local_html() -> str:
    return """<!DOCTYPE html>
<html>
<head>
  <title>Entrümpelung Siegen - Fischer Entruempelungen</title>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "LocalBusiness",
    "name": "Fischer Entruempelungen",
    "telephone": "0271 123456",
    "address": {"@type": "PostalAddress", "streetAddress": "Musterstraße 1", "addressLocality": "Siegen"},
    "openingHours": ["Mo-Fr 08:00-18:00"],
    "geo": {"@type": "GeoCoordinates", "latitude": "50.87", "longitude": "8.02"},
    "url": "https://fischer-entruempelungen.de"
  }
  </script>
</head>
<body>
  <header><a href="tel:0271123456">0271 123 456</a></header>
  <h1>Professionelle Entrümpelung Siegen</h1>
  <p>Fischer Entruempelungen, Musterstraße 1, 57072 Siegen. Tel: 0271 123456.
     Kostenlose Besichtigung! Sofort verfügbar. Versichert und zertifiziert.
     Wir sind in Siegen für Sie da. <a href="https://wa.me/49271123456">WhatsApp</a>
     Innerhalb von 24 Stunden. Vorher-Nachher Galerie unserer Referenzen.</p>
  <div class="google-bewertungen">4.9 Sterne - 45 Bewertungen</div>
</body>
</html>"""


class TestNAPExtraction:
    def test_phone_extracted(self, analyser, good_local_html):
        result = analyser.analyse(good_local_html, "https://example.com", "Siegen", "Fischer Entruempelungen")
        assert result.nap_phone != ""

    def test_address_extracted(self, analyser, good_local_html):
        result = analyser.analyse(good_local_html, "https://example.com", "Siegen", "Fischer Entruempelungen")
        assert result.nap_address != ""

    def test_consistent_nap(self, analyser, good_local_html):
        result = analyser.analyse(good_local_html, "https://example.com", "Siegen", "Fischer Entruempelungen")
        assert result.nap_consistent is True


class TestLocalBusinessSchema:
    def test_detects_local_business_schema(self, analyser, good_local_html):
        result = analyser.analyse(good_local_html, "https://example.com", "Siegen", "Fischer")
        assert result.has_local_business_schema is True

    def test_no_schema_detected(self, analyser):
        html = "<html><head></head><body><h1>Test</h1></body></html>"
        result = analyser.analyse(html, "https://example.com", "Siegen", "Test")
        assert result.has_local_business_schema is False
        assert result.suggested_schema  # Should generate a suggestion


class TestCitySignals:
    def test_city_in_title(self, analyser, good_local_html):
        result = analyser.analyse(good_local_html, "https://example.com", "Siegen", "Fischer")
        assert result.city_in_title is True

    def test_city_in_h1(self, analyser, good_local_html):
        result = analyser.analyse(good_local_html, "https://example.com", "Siegen", "Fischer")
        assert result.city_in_h1 is True

    def test_city_mention_count_positive(self, analyser, good_local_html):
        result = analyser.analyse(good_local_html, "https://example.com", "Siegen", "Fischer")
        assert result.city_mention_count >= 1


class TestUrgencySignals:
    def test_whatsapp_detected(self, analyser, good_local_html):
        result = analyser.analyse(good_local_html, "https://example.com", "Siegen", "Fischer")
        assert result.has_whatsapp is True

    def test_response_time_detected(self, analyser, good_local_html):
        result = analyser.analyse(good_local_html, "https://example.com", "Siegen", "Fischer")
        assert result.has_response_time_claim is True

    def test_free_inspection_detected(self, analyser, good_local_html):
        result = analyser.analyse(good_local_html, "https://example.com", "Siegen", "Fischer")
        assert result.has_free_inspection is True

    def test_insurance_badge_detected(self, analyser, good_local_html):
        result = analyser.analyse(good_local_html, "https://example.com", "Siegen", "Fischer")
        assert result.has_insurance_badge is True

    def test_review_signals_detected(self, analyser, good_local_html):
        result = analyser.analyse(good_local_html, "https://example.com", "Siegen", "Fischer")
        assert result.has_review_signals is True

    def test_urgency_score_positive(self, analyser, good_local_html):
        result = analyser.analyse(good_local_html, "https://example.com", "Siegen", "Fischer")
        assert result.urgency_score > 0


class TestSuggestedSchema:
    def test_generates_schema_when_missing(self, analyser):
        html = "<html><head><title>Entrümpelung Siegen</title></head><body><h1>Siegen</h1></body></html>"
        result = analyser.analyse(html, "https://example.com", "Siegen", "Test GmbH")
        assert result.suggested_schema.get("@type") == "HomeAndConstructionBusiness"
        assert result.suggested_schema.get("name") == "Test GmbH"
