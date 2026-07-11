# SEOOptimize v1.0 -- Senior Reviewed Architecture

> **Reviewer:** Senior SEO Architect (30 years field experience, local service sector)

> **Based on:** Intern draft v1.0

> **Status:** Architecture Finalized - Ready to Build


---

## Senior Review Verdict


The intern draft shows strong software architecture thinking. The deterministic-before-AI

principle is the right call and saves significant API cost. The dual-model consensus is sound.

However, three critical gaps must be fixed before this is usable for a real SME client:


**Gap 1 -- Local SEO is missing as a first-class concern.**

For a clearance company in Siegen, Google Business Profile, NAP consistency, and

local citations drive more leads than any on-page SEO change. This discipline is

structurally different from on-page SEO and needs its own dedicated module, its own

scoring axis, and its own recommendation cards.


**Gap 2 -- Business-type keyword intent is not modeled.**

A person searching 'Entrumpelung Siegen sofort' is ready to book today -- high urgency,

local transactional intent. A person searching 'Entrumpelung was kostet' is comparing

prices -- informational intent. The tool must classify keyword intent by business type

and surface urgency signals (phone number above the fold, same-day availability claim,

WhatsApp button) as the highest-priority recommendations.


**Gap 3 -- The visual canvas needs a precise technical bridge.**

The intern described the canvas feature but not the implementation. Playwright's

locator.bounding_box() API maps any CSS selector to exact pixel coordinates on the

screenshot. Without specifying this bridge, a developer will guess at coordinates and

the flagship feature will be inaccurate.


Everything else in the intern draft is preserved and refined below.


---

## 1. Design Philosophy (Preserved and Extended)


**Core principle:** Use deterministic software wherever possible. Use AI only where reasoning is required.


| Deterministic (no AI cost) | AI-Required (reasoning needed) |
| --- | --- |
| Detect H1 presence | Evaluate H1 keyword quality |
| Extract meta title | Rewrite meta title with local keyword |
| Count words on page | Judge whether content depth is adequate |
| Detect schema markup | Explain what schema is missing and why it matters |
| Detect phone number presence | Judge whether CTA placement drives conversions |
| Detect NAP on all pages | Assess NAP consistency risk to local rankings |
| Measure page load time | Explain business impact of slow load on mobile users |
| Extract internal links | Recommend internal linking strategy for authority flow |
| Detect review count | Suggest review acquisition strategy for local trust |


---

## 2. Scoring Model (New -- Not in Intern Draft)


Every page and site-level view shows scores across six axes. Weights reflect what

actually drives rankings for local service businesses -- not generic SEO checklists.


| Axis | Weight | Rationale |
| --- | --- | --- |
| Local SEO | 30% | GBP, NAP, local keywords, service-area pages -- primary ranking driver |
| Content Quality | 25% | Intent match, depth, readability, EEAT signals |
| Technical SEO | 15% | Crawlability, canonicals, schema, mobile, Core Web Vitals |
| Conversion Signals | 15% | CTA, phone visibility, trust badges, urgency language |
| On-Page Metadata | 10% | Titles, descriptions, OG tags, heading structure |
| Competitor Gap | 5% | Features present in local competitors but absent here |


Local SEO carries the highest weight because for a business like Fischer Entruempelungen,

the majority of customers find them via 'near me' or city-scoped searches. Technical SEO

matters but a perfect sitemap does not offset the absence of a Google Business Profile.


---

## 3. Full System Workflow


```

User enters Website URL + Competitor URLs

        |

        v

Website Discovery Engine (Playwright + BeautifulSoup)

  -- Crawl all internal pages up to depth 3

  -- Respect robots.txt

  -- Deduplicate URLs

        |

        v

Rendering Engine

  -- Playwright renders each page (handles JS)

  -- Capture full-page screenshot (PNG)

  -- Capture rendered DOM HTML

  -- Record element bounding boxes via locator.bounding_box()

        |

        v

Deterministic Extraction Engine

  -- Extract all structured data (no AI)

  -- Score each field with pass/warn/fail

  -- Build structured JSON per page

        |

        v

Structured Knowledge Cache

  -- Cache keyed by (URL + content hash)

  -- Skip re-analysis if content unchanged

        |

        v

Local SEO Analysis (New Module)

  -- NAP consistency check across all pages

  -- Schema LocalBusiness presence check

  -- GBP signals audit

        |

        v

AI Analysis Pipeline

  -- Claude: Primary SEO Consultant

  -- Input: structured JSON only (never raw HTML)

  -- Output: annotation JSON with bounding box references

        |

        v

AI Independent Review

  -- Gemini: Independent Critic + Competitor Lens

  -- Receives: structured JSON + competitor extracted data

  -- Output: enriched annotations with competitor evidence

        |

        v

Consensus Engine

  -- Merge Claude and Gemini outputs

  -- Assign agreement level and confidence score

  -- Filter: only recommendations with confidence >= 0.65 shown

        |

        v

Visual Canvas Renderer

  -- Overlay annotation boxes on screenshot using PIL

  -- Map selector -> bounding_box -> PIL rectangle

        |

        v

Interactive Dashboard + Export

```


---

## 4. Module Catalogue (Revised)


### Module A -- Project Setup

User provides:

- Primary website URL
- Business name and category
- Competitor URLs (up to 5)
- Target city / service area

The business category drives keyword intent classification. A clearance company

(Entrumpelung) uses urgency-transactional patterns. A lawyer uses informational patterns.

The tool adapts its recommendations accordingly.


### Module B -- Website Discovery Engine

Playwright loads the root URL. BeautifulSoup extracts all anchor tags.

The crawler filters to same-origin URLs only, respects robots.txt, and

deduplicates canonical equivalents. Output: ordered list of pages that

become the left-panel navigation tree.


Crawl limits:

- Max pages: 50 (configurable)
- Max depth: 3 levels from root
- Delay between requests: 1.5 seconds (politeness)
- User-agent: identifies as SEOOptimize bot

### Module C -- Rendering Engine (Playwright)

Every page is rendered headlessly before extraction. This correctly handles

JavaScript-dependent content that simple HTTP requests miss.


Per page, Playwright captures:

- Full-page PNG screenshot (viewport width 1280px)
- Mobile screenshot (viewport width 375px) -- Google indexes mobile first
- Final rendered DOM HTML
- Element bounding boxes for the canvas annotation bridge (see Module G)

### Module D -- Deterministic Extraction Engine

No AI. Pure structured extraction. Every field receives a pass/warn/fail score.


Extracted fields:

| Field | Pass condition | Warn condition | Fail condition |
| --- | --- | --- | --- |
| Meta title | 50-60 chars, contains target keyword | Present but suboptimal | Missing |
| Meta description | 150-160 chars, contains CTA | Present but too short/long | Missing |
| H1 tag | One H1, contains primary keyword | Present but weak keyword | Missing or multiple |
| H2 structure | 3+ H2 tags present | 1-2 H2 tags | No H2 tags |
| Word count | 600+ words (service page) | 300-599 words | Under 300 words |
| Images with alt text | All images have descriptive alt | Some missing alt | All missing alt |
| Phone number | Visible above the fold | Present but below fold | Not found on page |
| Schema markup | LocalBusiness + Service schema | Partial schema | No schema |
| Canonical tag | Present and self-referencing | Missing | Conflicting |
| Mobile viewport | Meta viewport tag present | N/A | Missing |
| NAP on page | Name, address, phone all present | Partial NAP | No NAP |
| Internal links | 3+ contextual internal links | 1-2 internal links | No internal links |
| Page load time | Under 2.5s LCP | 2.5-4s LCP | Over 4s LCP |
| HTTPS | Full HTTPS | N/A | HTTP |

### Module E -- Local SEO Analysis (New -- Critical Gap in Intern Draft)


This module is the most important addition to the intern's architecture.

For local service businesses, local SEO factors outweigh on-page factors in

determining whether the business appears in Google's local pack (the map results)

which capture 30-40% of all clicks for local service queries.


The module checks:


**NAP Consistency (Name, Address, Phone)**

- Extract NAP from every page using regex patterns
- Verify Name, Address, and Phone are identical across all pages
- Compare against NAP found in schema markup
- Flag any inconsistency -- even a missing period in the street address can
-   create a duplicate entity signal that suppresses local rankings

**Schema Markup for Local Businesses**

- Detect JSON-LD schema type LocalBusiness or its subtypes
- Verify required fields: name, address, telephone, openingHours, geo, url
- Generate a ready-to-paste corrected schema block -- not just a warning
- For clearance companies: use schema type 'HomeAndConstructionBusiness'

**Service Area Signals**

- Detect whether target city name appears in title, H1, first paragraph
- Count city mentions across the page
- Identify missing service-area pages (one page per major city in coverage area)
- For Fischer: Siegen is served, but Kreuztal, Netphen, Hilchenbach, Freudenberg
-   are likely service areas with no dedicated landing pages

**Review Signals**

- Detect whether Google Reviews widget or review count is embedded
- Check for review schema markup
- Surface recommendation: minimum 10 Google reviews to appear in local pack

**Urgency and Trust Signals (specific to service businesses)**

- Phone number visible above the fold on mobile
- WhatsApp button present
- Response time claim ('Innerhalb von 24 Stunden')
- Free inspection offer ('Kostenlose Besichtigung')
- Insurance/certification badge
- Before/after photo gallery

### Module F -- Structured Knowledge Cache

All extracted and scored data is stored as structured JSON per page.

Cache is keyed by (URL + SHA-256 of rendered HTML).

If content has not changed, AI analysis is skipped on re-run.

This makes repeated analysis essentially free.


Cache schema per page:

```
{
  'url': 'https://...',
  'fetched_at': '2026-07-10T21:00:00Z',
  'content_hash': 'sha256:...',
  'screenshot_path': 'cache/page_home.png',
  'mobile_screenshot_path': 'cache/page_home_mobile.png',
  'element_boxes': {
    'head > title': {'x': 0, 'y': 0, 'w': 0, 'h': 0},
    'h1': {'x': 120, 'y': 180, 'w': 900, 'h': 72},
    ...element selector to bounding box map...
  },
  'extracted': { ...all deterministic fields... },
  'scores': { 'meta_title': 'fail', 'h1': 'warn', ... },
  'ai_analysis': { ...Claude + Gemini results... }
}
```

### Module G -- Visual Canvas Bridge (Critical Technical Specification)


This is the technical implementation the intern did not specify.

It is the engineering bridge that makes the visual canvas feature work correctly.


**The Problem:**

Claude returns SEO recommendations referencing HTML selectors (e.g. 'h1', 'meta[name=description]').

The canvas displays a PNG screenshot. There is no automatic connection between a CSS selector

and a pixel position in the image.


**The Bridge:**

During the Playwright rendering step (Module C), after the page loads, the system runs:

```
# Playwright Python -- run after page.goto(url)
selectors_to_track = [
    'h1', 'h2', 'h3',
    'meta[name=description]',
    'img',
    'a[href]',
    '.hero, header, #hero',
    'footer',
    'form',
    '[class*=cta], [class*=button], button',
    'script[type="application/ld+json"]',
]

element_boxes = {}
for selector in selectors_to_track:
    try:
        box = await page.locator(selector).first.bounding_box()
        if box:
            element_boxes[selector] = box  # {x, y, width, height}
    except:
        pass

# These pixel coordinates directly map to positions in the full-page screenshot
```

When Claude returns an annotation referencing 'h1', the system looks up

element_boxes['h1'] to get the pixel rectangle, then PIL draws the colored

overlay box at exactly that position on the screenshot.


**Annotation rendering with PIL:**

```
from PIL import Image, ImageDraw, ImageFont

COLORS = {'critical': (220,50,50,160), 'warning': (240,160,0,160), 'ok': (40,180,40,160)}

def render_canvas(screenshot_path, annotations, element_boxes):
    img = Image.open(screenshot_path).convert('RGBA')
    overlay = Image.new('RGBA', img.size, (0,0,0,0))
    draw = ImageDraw.Draw(overlay)
    for ann in annotations:
        box = element_boxes.get(ann['selector'])
        if not box: continue
        x, y, w, h = box['x'], box['y'], box['width'], box['height']
        color = COLORS.get(ann['priority'], COLORS['warning'])
        draw.rectangle([x, y, x+w, y+h], outline=color[:3], width=3, fill=color)
        draw.text((x+4, y+4), ann['label'], fill=(255,255,255,230))
    return Image.alpha_composite(img, overlay).convert('RGB')
```

### Module H -- AI Analysis Pipeline (Claude as Primary)


Claude receives structured JSON only -- never raw HTML.

Sending raw HTML would triple token cost and introduce irrelevant markup noise.


**Prompt strategy for Claude:**

```
You are a senior SEO consultant specializing in local service businesses in Germany.
You are analyzing a page for: {business_name}, a {business_category} in {city}.

The page has already been scanned by a deterministic engine. You are receiving
structured data only. Do not invent or assume information not provided.

Your task:
1. Evaluate the SEO quality of each field provided.
2. For each issue found, reference the exact HTML selector.
3. Generate a specific, ready-to-use improvement (not generic advice).
4. Classify each finding as: critical / warning / quick_win / ok
5. Estimate the SEO impact of fixing this issue: high / medium / low

Return valid JSON only. Schema:
{
  'page_score': int (0-100),
  'annotations': [
    {
      'selector': 'css selector string',
      'label': 'short badge text (max 4 words)',
      'priority': 'critical|warning|quick_win|ok',
      'issue': 'what is wrong',
      'why_it_matters': 'business language explanation',
      'suggested_fix': 'exact replacement text or instruction',
      'impact': 'high|medium|low',
      'confidence': float (0.0-1.0)
    }
  ],
  'top_priority_action': 'single most important thing to fix first'
}
```

### Module I -- AI Independent Review (Gemini as Critic and Competitor Lens)


Gemini receives two inputs:

- The same structured page JSON that Claude received
- Extracted data from all competitor pages

Gemini's job is NOT to repeat Claude's work. Its job is:

- 1. Validate or challenge each of Claude's annotations
- 2. Add competitor evidence to each annotation where relevant
- 3. Identify anything Claude missed that the competitor analysis reveals

**Key rule for competitor comparisons:**

Gemini is only permitted to surface gaps where Fischer is weaker than a competitor.

Competitor weaknesses must never be mentioned. This preserves the sales psychology

principle: the business owner sees opportunity, not comfort.


**Competitor evidence format in Gemini output:**

```
{
  'selector': 'h1',
  'gemini_verdict': 'agree|strengthen|reject|add',
  'gemini_note': 'Confirms Claude -- competitor A uses H1 with city name and ranks 3rd',
  'competitor_evidence': {
    'competitor_a': 'Has H1: Professionelle Entrumpelung Siegen -- Jetzt anfragen',
    'competitor_b': 'Has H1: Gunstige Haushaltsauflosung Siegen und Umgebung'
  },
  'revised_suggestion': 'Entrumpelung Siegen -- Kostenlose Besichtigung | Fischer'
}
```

### Module J -- Consensus Engine


The consensus engine merges Claude and Gemini outputs into final recommendations.


| Claude verdict | Gemini verdict | Consensus action |
| --- | --- | --- |
| Critical | Agree | Show as Critical -- high confidence |
| Critical | Reject | Show as Warning -- flag disagreement for user |
| Warning | Agree | Show as Warning |
| Warning | Strengthen to Critical | Show as Critical |
| Quick Win | Agree | Show as Quick Win |
| OK | OK | Show as Passed -- no action needed |
| Any | Adds competitor evidence | Attach competitor card to recommendation |


Only recommendations with final confidence >= 0.65 are displayed by default.

A toggle allows the user to reveal low-confidence recommendations.


---

## 5. Recommendation Card Specification


Every recommendation displayed in the UI follows this exact structure.

Consistency is critical -- the client must be able to scan recommendations

quickly without re-learning the layout on each card.


```

+---------------------------------------------------------+
|  [CRITICAL] H1 Tag Missing Primary Keyword             |
|  Confidence: 94%   Impact: HIGH   Selector: h1         |
+---------------------------------------------------------+
|  PROBLEM                                               |
|  Your H1 heading does not contain 'Entrumpelung Siegen'|
|  which is the most-searched term for your service.     |
|                                                        |
|  WHY IT MATTERS                                        |
|  Google uses the H1 as the primary signal for what     |
|  the page is about. Without the city name, your page   |
|  will not appear in local searches.                    |
|                                                        |
|  COMPETITOR EVIDENCE                                   |
|  Competitor A: 'Entrumpelung Siegen - Jetzt anfragen'  |
|  Competitor B: 'Professionelle Entrumpelung in Siegen' |
|                                                        |
|  SUGGESTED FIX (ready to paste)                       |
|  Professionelle Entrumpelung in Siegen | Fischer       |
|                                                        |
|  EXPECTED IMPACT                                       |
|  Estimated 25-40% improvement in local search ranking  |
|  for primary service keyword within 4-8 weeks.         |
|                                                        |
|  [Accept Suggestion]  [Edit]  [Reject]  [Ask AI more] |
+---------------------------------------------------------+
```


---

## 6. Competitor Intelligence Rules


This module must be implemented with strict editorial discipline.

The following rules are non-negotiable:


**Show only:**

- Features present in a competitor that are absent or weaker in the client's site
- Keyword strategies the competitor uses that are missing from the client's site
- Trust signals the competitor displays that the client does not
- Content depth where the competitor clearly outperforms the client

**Never show:**

- Competitor weaknesses (broken links, slow pages, thin content, errors)
- Comparative scores that make the competitor look worse overall
- Any language that could be construed as criticizing a competitor's business

**The psychological principle:**

The business owner must leave every competitor comparison card feeling motivated,

not reassured. 'They are not perfect either' creates inaction.

'Here is exactly what they do that gets them more calls' creates action.


---

## 7. UI Layout Specification


```

+------------------------------------------------------+
|  SEOOptimize    [Project: Fischer Entruempelungen]   |
+------------------+-----------------------------------+
| SIDEBAR          | MAIN AREA                        |
|                  |                                  |
| PROJECT          |  [Overview] [Canvas] [Details]   |
| -- Overview      |                                  |
| -- Homepage      |  OVERVIEW MODE                   |
| -- Leistungen    |  Site Score: 54/100              |
|    Entrumpelung  |  [=========-----------]          |
|    Haushalt      |                                  |
|    Aktenver.     |  Local SEO    31/30  [critical]  |
| -- Referenzen    |  Content      18/25  [warning]   |
| -- Kontakt       |  Technical    12/15  [ok]        |
| -- Impressum     |  Conversion    8/15  [warning]   |
|                  |  Metadata      7/10  [warning]   |
| SCORES           |  Competitor    2/5   [critical]  |
| Home    42/100   |                                  |
| Leistg  61/100   |  CRITICAL ISSUES (3)             |
| Referenz 71/100  |  > No LocalBusiness schema       |
| Kontakt 53/100   |  > NAP missing from 2 pages      |
|                  |  > Phone not above fold mobile   |
| [Export Report]  |                                  |
+------------------+-----------------------------------+
```


Clicking any page in the sidebar switches the main area between three views:

- **Overview** -- score breakdown and prioritized issue list
- **Canvas** -- annotated screenshot with clickable overlay boxes
- **Details** -- full structured field-by-field analysis

---

## 8. Priority Queue for Fischer Entruempelungen (Live Example)


Based on the website review at https://fischer-entruempelungen.de/, a senior

SEO consultant would prioritize the following actions in this exact order:


| Priority | Action | Impact | Effort | Why first |
| --- | --- | --- | --- | --- |
| 1 | Add LocalBusiness schema to every page | High | Low | 30 minutes -- highest ROI per hour |
| 2 | Add meta description to homepage and Leistungen | High | Low | Currently blank -- hurts CTR |
| 3 | Put phone number in header (above fold) | High | Low | Mobile users bounce without visible phone |
| 4 | Create 'Entrumpelung Siegen' dedicated landing page | Very High | Medium | Targets highest-volume keyword directly |
| 5 | Add H1 to homepage with city keyword | High | Low | Current H1 has no local intent signal |
| 6 | Fix typo: Entrumplungsservice -> Entruempelungsservice | Low | Low | Professional credibility signal |
| 7 | Create service-area pages for 5 surrounding cities | High | High | Expands local pack eligibility |
| 8 | Add before/after gallery to Referenzen page | Medium | Medium | Competitors use this as primary trust signal |
| 9 | Embed Google Reviews or add review schema | High | Medium | Local pack requires visible review signals |
| 10 | Add WhatsApp contact button | High | Low | German SME customers strongly prefer WhatsApp |


---

## 9. Technology Stack


| Component | Technology | Rationale |
| --- | --- | --- |
| UI | Streamlit | Fast to build, no frontend framework needed |
| Crawler | Playwright (Python async) | Handles JS rendering, provides bounding_box API |
| HTML parsing | BeautifulSoup 4 | Deterministic extraction from rendered DOM |
| Screenshot annotation | Pillow (PIL) | Draw colored boxes on PNG screenshots |
| Primary AI | Claude Sonnet API | Best structured JSON output, strong German language |
| Secondary AI | Gemini 2.5 Flash API | Low cost, large context for competitor comparison |
| Cache | JSON files + SHA-256 keys | Simple, portable, no database needed for v1 |
| Schema generator | Python dict -> json.dumps | Generate corrected JSON-LD ready to paste |
| PDF export | WeasyPrint | Client-deliverable report from HTML template |
| Config | .env file | API keys never hardcoded |
| Hosting (optional) | Hetzner VPS (Germany) | DSGVO compliant, same region as client |


---

## 10. Version 1.0 Scope (Finalized)


Included:

- Website crawling with Playwright rendering
- Automatic page discovery and left-panel navigation tree
- Deterministic extraction engine with pass/warn/fail scoring
- Local SEO analysis (NAP, schema, urgency signals, service area)
- Structured knowledge cache (content-hash keyed)
- Canvas annotation bridge (Playwright bounding_box -> PIL overlay)
- Claude primary SEO analysis (structured JSON prompting)
- Gemini independent review with competitor lens
- Consensus engine with confidence filtering
- Competitor intelligence (positive features only)
- Overview dashboard with six-axis scoring
- Page explorer with field-by-field detail
- Visual canvas with clickable AI-annotated overlays
- Section-based analysis
- AI rewrite suggestions for meta, headings, CTA, body copy
- Priority classification (Critical / Warning / Quick Win / OK)
- Exportable PDF report

Deferred to v2:

- Live ranking tracking
- Google Search Console API integration
- Google Business Profile audit via API
- Automated content publishing to WordPress REST API
- Conversion tracking integration
- Multi-language support

---

## 11. SEO Principles for Service Businesses (Reference)


These principles must inform every AI prompt and every recommendation generated.

They are not generic SEO advice -- they are specific to businesses like Fischer.


**1. Local intent keywords dominate.**

'Entrumpelung' alone is not a target keyword. 'Entrumpelung Siegen' is.

'Entrumpelung Siegen sofort' is even better -- it captures same-day urgency.


**2. The phone number is a conversion element, not just contact information.**

A clearance customer has often just experienced a bereavement or is under time

pressure from an estate. They call. They do not fill out forms. The phone number

must be in the top 20% of every mobile page.


**3. Trust signals for physical service businesses differ from e-commerce.**

Reviews, before/after photos, certifications, and insurance badges outperform

brand logos and awards pages. The visitor is trusting a stranger with their home.


**4. Service-area pages are high-ROI, low-effort assets.**

A 600-word page titled 'Entrumpelung [City]' targeting each of the 5-8 cities

in the service area will rank for city-specific queries without cannibalizing

the main page. This is the single highest-ROI content strategy for local trades.


**5. Speed matters more on mobile than desktop for this audience.**

Clearance customers often search on mobile from the property they need to clear.

A page that takes 6 seconds to load on a 4G connection will lose the lead.


**6. FAQ schema earns featured snippets for service questions.**

'Was kostet eine Entrumpelung?' and 'Wie lange dauert eine Entrumpelung?'

are frequently searched. FAQ schema lets the site appear as a rich result

answering these questions directly in Google, above the standard results.
