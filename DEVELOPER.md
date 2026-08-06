# Developer Guide — The Daily Brief

Technical reference for contributors and self-hosters.

---

## Architecture Overview

| File | Role |
|---|---|
| `build_newspaper.py` | Main pipeline: fetches feeds, deduplicates, summarises, writes `newspaper.json` |
| `config.json` | Declarative config for sections, feeds, tickers, and Hacker News |
| `index.html` | Static front-end; reads `newspaper.json` at load time |
| `test_newspaper.py` | Unit test suite (`unittest`) |

### Data flow

```
config.json
    │
    ▼
build_newspaper.py
    ├── RSS feeds  (feedparser)
    ├── Hacker News API
    └── Market tickers (yfinance)
         │
         ▼  (optional AI deduplication via Gemini)
    newspaper.json
         │
         ▼
    index.html  (rendered in browser)
```

---

## Configuration (`config.json`)

```json
{
  "market": {
    "enabled": true,
    "tickers": [
      {
        "symbol": "AAPL",
        "label": "AAPL",
        "type": "stock",
        "exchange": "NASDAQ"
      }
    ]
  },
  "hacker_news": {
    "enabled": true,
    "title": "Hacker News Top Stories",
    "max_items": 5,
    "min_score": 100
  },
  "sections": [
    {
      "name": "World News",
      "feeds": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.theguardian.com/world/rss"
      ]
    },
    {
      "name": "Science & Tech",
      "feeds": [
        "https://www.sciencedaily.com/rss/top/science.xml",
        "https://feeds.arstechnica.com/arstechnica/index"
      ]
    }
  ]
}
```

- **`market.tickers`** — any symbol supported by `yfinance`; `type` can be `"stock"` or `"crypto"`.
- **`hacker_news.min_score`** — only stories with at least this upvote count are included.
- **`sections[].feeds`** — one or more RSS feed URLs per section. When multiple feeds are given, deduplication runs automatically.

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install feedparser yfinance google-genai
```

### Gemini AI (optional)

Enables smarter cross-feed deduplication and Hacker News batch summarisation.

```bash
export GEMINI_API_KEY="your_api_key_here"
export GEMINI_MODEL="gemini-2.5-flash"   # default if unset
```

Without a key the pipeline falls back to local fuzzy-matching deduplication and sentence-extraction summaries — no functionality is lost, just quality.

**Rate-limit compliance**: the pipeline caps Gemini calls at ≤ 15/min (1 call per section dedup + 1 call for HN summaries) to stay within the free tier.

---

## Running the pipeline

```bash
python3 build_newspaper.py
```

Then open `index.html` in a browser. The file reads `newspaper.json` locally — no server needed.

---

## Automated deployment (GitHub Actions)

The workflow in `.github/workflows/deploy.yml` runs the pipeline on a schedule and publishes `index.html` + `newspaper.json` to GitHub Pages.

Set the `GEMINI_API_KEY` secret in your repository settings to enable AI features in CI.

---

## Running tests

```bash
python3 -m unittest test_newspaper.py
```

---

## Key design decisions

- **No server-side rendering** — `index.html` is fully static; the build step only updates `newspaper.json`. This makes hosting trivial (GitHub Pages, S3, any CDN).
- **Single daily generation** — the newspaper is meant to be built once per day (via cron / Actions), not fetched live. This is intentional: it removes the temptation to refresh.
- **Graceful AI degradation** — every AI call has a local fallback so the pipeline always produces output even without credentials.
