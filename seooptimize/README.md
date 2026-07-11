# SEOOptimize v1.0

Commercial-quality local SEO analysis tool for service businesses.

## Overview

SEOOptimize crawls, renders, and analyses websites for local service businesses.
It uses a deterministic extraction engine (no AI cost) and then applies a dual-model
AI pipeline (Claude + Gemini) with a consensus engine to generate high-confidence,
actionable recommendations.

## Quick Start

```bash
# 1. Clone and enter the project
cd seooptimize

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt
pip install -e .

# 4. Install Playwright browsers
playwright install chromium

# 5. Configure environment
copy .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY and GOOGLE_API_KEY
```

### Start the app

From the repo root:

```powershell
# PowerShell
.\start
# or
Start.cmd

# CMD
start.cmd
```

The browser opens automatically at http://localhost:8501.

Press `Ctrl+C` in the terminal to stop the server.

## Architecture

See `../SEOArch.md` for the full architecture specification.

### Module Map

| Module | Description |
|--------|-------------|
| A | Project Setup — business profile, target city, competitor URLs |
| B | Website Discovery Engine — Playwright crawler, robots.txt, URL dedup |
| C | Rendering Engine — full-page screenshots, bounding box capture |
| D | Deterministic Extraction — 14 SEO fields, pass/warn/fail scoring |
| E | Local SEO Analysis — NAP consistency, schema, urgency signals |
| F | Knowledge Cache — SHA-256 keyed JSON, skip unchanged pages |
| G | Visual Canvas Bridge — CSS selector → pixel coordinates → PIL overlay |
| H | Claude Primary Analysis — structured JSON prompting |
| I | Gemini Independent Review — competitor lens, critic role |
| J | Consensus Engine — confidence ≥ 0.65, priority merge |

### Scoring Model

| Axis | Weight |
|------|--------|
| Local SEO | 30% |
| Content Quality | 25% |
| Technical SEO | 15% |
| Conversion Signals | 15% |
| On-Page Metadata | 10% |
| Competitor Gap | 5% |

## Technology Stack

- **UI**: Streamlit
- **Crawling**: Playwright (Python async)
- **Parsing**: BeautifulSoup 4
- **Screenshots**: Playwright + Pillow
- **AI**: Claude Sonnet (primary), Gemini 2.5 Flash (critic)
- **Cache**: JSON files + SHA-256
- **Export**: WeasyPrint (PDF), python-docx (DOCX)

## Project Structure

```
app/
├── config/      Settings, theme
├── core/        Logging
├── models/      Pydantic data models
├── crawler/     Module B — website discovery
├── rendering/   Module C — Playwright rendering
├── extractors/  Modules D, E — deterministic extraction + local SEO
├── cache/       Module F — knowledge cache
├── ai/          Modules H, I — Claude + Gemini providers
├── analysis/    Module J — consensus engine + competitor intelligence
├── canvas/      Module G — PIL annotation renderer
├── ui/          Streamlit pages and components
├── exports/     PDF, DOCX, HTML export
└── utils/       URL helpers, hashing
```
