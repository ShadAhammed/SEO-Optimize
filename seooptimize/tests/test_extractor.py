"""Unit tests for the Deterministic Extraction Engine (Module D)."""

import pytest
from app.extractors.dom import DOMExtractor
from app.models.page import ScoreStatus


@pytest.fixture
def extractor() -> DOMExtractor:
    return DOMExtractor()


@pytest.fixture
def sample_html() -> str:
    return """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>Entrümpelung Siegen — Professionell | Fischer</title>
  <meta name="description" content="Professionelle Entrümpelung in Siegen und Umgebung. Kostenlose Besichtigung. Rufen Sie uns an: 0271 1234567. Schnell, zuverlässig, günstig.">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="canonical" href="https://fischer-entruempelungen.de/">
  <script type="application/ld+json">
  {"@context":"https://schema.org","@type":"LocalBusiness","name":"Fischer Entruempelungen","telephone":"0271 1234567"}
  </script>
</head>
<body>
  <header>
    <a href="tel:02711234567">0271 123 45 67</a>
  </header>
  <main>
    <h1>Professionelle Entrümpelung in Siegen</h1>
    <h2>Unsere Leistungen</h2>
    <h2>Warum Fischer?</h2>
    <h2>Unser Service</h2>
    <h2>Kontakt</h2>
    <p>Wir bieten professionelle Entrümpelungsservices in Siegen und der gesamten Region an.
       Mit über 10 Jahren Erfahrung sind wir Ihr zuverlässiger Partner für Haushaltsauflösungen,
       Kellerentrümpelungen und Gewerbeentrümpelungen. Unsere Preise sind fair und transparent.
       Kontaktieren Sie uns für eine kostenlose Besichtigung. Wir kommen zu Ihnen und erstellen
       ein unverbindliches Angebot. Professionell, schnell und günstig - das ist unser Versprechen.
       Wir arbeiten sauber und zuverlässig. Alle Mitarbeiter sind versichert und geprüft.
       Rufen Sie uns an: 0271 123 45 67. Siegen, Kreuztal, Netphen - wir kommen zu Ihnen.
       Haushaltsauflösungen, Kellerentrümpelungen, Dachbodenentrümpelungen - alles aus einer Hand.</p>
    <img src="hero.jpg" alt="Entrümpelung Siegen - Fischer Team">
    <img src="work.jpg" alt="Unsere Arbeit in Siegen">
    <a href="/leistungen">Unsere Leistungen</a>
    <a href="/kontakt">Kontakt aufnehmen</a>
    <a href="/referenzen">Referenzen ansehen</a>
    <a href="/impressum">Impressum</a>
  </main>
  <footer>
    <p>Fischer Entruempelungen | Siegerland | 0271 123 45 67</p>
  </footer>
</body>
</html>"""


class TestMetaTitle:
    def test_pass_for_optimal_length(self, extractor):
        # Exactly 60 chars: "Professionelle Entrumpelung Siegen - Fischer Entruempelungen"
        html = (
            "<html><head>"
            "<title>Professionelle Entrumpelung Siegen - Fischer Entruempelungen</title>"
            "</head><body><h1>Test</h1></body></html>"
        )
        result = extractor.extract(html, "https://example.com")
        assert result.meta_title.status == ScoreStatus.PASS

    def test_fail_for_missing_title(self, extractor):
        html = "<html><head></head><body><h1>Test</h1></body></html>"
        result = extractor.extract(html, "https://example.com")
        assert result.meta_title.status == ScoreStatus.FAIL

    def test_warn_for_short_title(self, extractor):
        html = "<html><head><title>Short</title></head><body></body></html>"
        result = extractor.extract(html, "https://example.com")
        assert result.meta_title.status in (ScoreStatus.WARN, ScoreStatus.FAIL)


class TestH1:
    def test_pass_for_one_h1(self, extractor, sample_html):
        result = extractor.extract(sample_html, "https://example.com")
        assert result.h1.status == ScoreStatus.PASS

    def test_fail_for_missing_h1(self, extractor):
        html = "<html><head><title>Test</title></head><body><p>No H1</p></body></html>"
        result = extractor.extract(html, "https://example.com")
        assert result.h1.status == ScoreStatus.FAIL

    def test_warn_for_multiple_h1(self, extractor):
        html = "<html><head></head><body><h1>First</h1><h1>Second</h1></body></html>"
        result = extractor.extract(html, "https://example.com")
        assert result.h1.status == ScoreStatus.WARN


class TestH2Structure:
    def test_pass_for_four_h2(self, extractor, sample_html):
        result = extractor.extract(sample_html, "https://example.com")
        assert result.h2_structure.status == ScoreStatus.PASS

    def test_fail_for_no_h2(self, extractor):
        html = "<html><head></head><body><h1>Title</h1><p>Content</p></body></html>"
        result = extractor.extract(html, "https://example.com")
        assert result.h2_structure.status == ScoreStatus.FAIL


class TestHTTPS:
    def test_pass_for_https(self, extractor, sample_html):
        result = extractor.extract(sample_html, "https://example.com")
        assert result.https.status == ScoreStatus.PASS

    def test_fail_for_http(self, extractor, sample_html):
        result = extractor.extract(sample_html, "http://example.com")
        assert result.https.status == ScoreStatus.FAIL


class TestMobileViewport:
    def test_pass_for_correct_viewport(self, extractor, sample_html):
        result = extractor.extract(sample_html, "https://example.com")
        assert result.mobile_viewport.status == ScoreStatus.PASS

    def test_fail_for_missing_viewport(self, extractor):
        html = "<html><head><title>Test</title></head><body></body></html>"
        result = extractor.extract(html, "https://example.com")
        assert result.mobile_viewport.status == ScoreStatus.FAIL


class TestSchemaMarkup:
    def test_pass_for_local_business_schema(self, extractor, sample_html):
        result = extractor.extract(sample_html, "https://example.com")
        assert result.schema_markup.status == ScoreStatus.PASS

    def test_fail_for_no_schema(self, extractor):
        html = "<html><head></head><body><h1>Test</h1></body></html>"
        result = extractor.extract(html, "https://example.com")
        assert result.schema_markup.status == ScoreStatus.FAIL


class TestInternalLinks:
    def test_pass_for_multiple_internal_links(self, extractor, sample_html):
        result = extractor.extract(sample_html, "https://fischer-entruempelungen.de/")
        assert result.internal_links.status == ScoreStatus.PASS


class TestPhoneAboveFold:
    def test_pass_for_tel_link_in_header(self, extractor, sample_html):
        result = extractor.extract(sample_html, "https://example.com")
        # The tel: link is in the header, so should be pass or warn
        assert result.phone_above_fold.status in (ScoreStatus.PASS, ScoreStatus.WARN)

    def test_fail_for_no_phone(self, extractor):
        html = "<html><head></head><body><h1>Test</h1></body></html>"
        result = extractor.extract(html, "https://example.com")
        assert result.phone_above_fold.status == ScoreStatus.FAIL


class TestWordCount:
    def test_pass_for_sufficient_words(self, extractor):
        # 220 reps × 3 words = 660 words → PASS (threshold is 600)
        words = "professionelle Entrumpelung Siegen " * 220
        html = (
            f"<html><head><title>Test</title></head>"
            f"<body><h1>Siegen</h1><p>{words}</p></body></html>"
        )
        result = extractor.extract(html, "https://example.com")
        assert result.word_count.status == ScoreStatus.PASS

    def test_fail_for_thin_content(self, extractor):
        html = "<html><head></head><body><h1>Hi</h1><p>Short page.</p></body></html>"
        result = extractor.extract(html, "https://example.com")
        assert result.word_count.status == ScoreStatus.FAIL


class TestFaqExtraction:
    def test_extracts_faq_schema(self, extractor):
        html = """<html><head></head><body>
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"FAQPage","mainEntity":[
          {"@type":"Question","name":"Was kostet eine Entrümpelung?",
           "acceptedAnswer":{"@type":"Answer","text":"Die Kosten variieren je nach Umfang."}}
        ]}
        </script></body></html>"""
        result = extractor.extract(html, "https://example.com")
        assert len(result.faq_items) == 1
        assert "Was kostet" in result.faq_items[0]["question"]
