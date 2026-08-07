# Developer Guide — The Daily Brief

Technical reference for contributors and self-hosters.

---

## Architecture Overview

| File                 | Role                                                                            |
| -------------------- | ------------------------------------------------------------------------------- |
| `build_newspaper.py` | Main pipeline: fetches feeds, deduplicates, summarises, writes `newspaper.json` |
| `config.json`        | Declarative config for sections, feeds, tickers, and Hacker News                |
| `index.html`         | Static front-end; reads `newspaper.json` at load time                           |
| `test_newspaper.py`  | Unit test suite (`unittest`)                                                    |

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
  "ai": {
    "model": "gemini-3.5-flash",
    "prompts": {
      "weather": "Turn this weather data into a short 1-sentence newspaper header snippet...",
      "word_of_day": "Pick an interesting, sophisticated English word...",
      "daily_puzzle": "Generate a fun, clever daily puzzle...",
      "global_deduplication": "You are selecting the most important and relevant news stories...",
      "section_deduplication": "Category: {category}\nTitles:\n{titles}...",
      "hn_summarization": "For each story listed below, write a single concise summary sentence..."
    }
  },
  "limits": {
    "max_section_articles": 8,
    "max_per_feed": 15,
    "max_feed_age_days": 1,
    "deduplication_similarity_threshold": 0.65,
    "word_overlap_threshold": 0.7,
    "page_snippet_length": 1800,
    "hn_snippet_length": 400,
    "hn_summary_min_words": 10,
    "hn_summary_max_words": 20
  },
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

- **`ai.model`** — Gemini model to use for AI features (overrides `GEMINI_MODEL` env var if set)
- **`ai.prompts.article_filtering`** — Custom filtering instructions for AI to control which news stories are included (e.g., exclude certain topics, prioritize certain types of stories)
- **`ai.prompts.weather`** — Custom prompt for weather description generation
- **`ai.prompts.word_of_day`** — Custom prompt for word of the day generation
- **`ai.prompts.daily_puzzle`** — Custom prompt for daily puzzle generation
- **`limits.max_section_articles`** — Maximum number of articles per section after deduplication
- **`limits.max_per_feed`** — Maximum articles to fetch from each RSS feed
- **`limits.max_feed_age_days`** — Maximum age of articles to include from feeds
- **`limits.deduplication_similarity_threshold`** — Similarity threshold for duplicate detection (0-1)
- **`limits.word_overlap_threshold`** — Word overlap threshold for duplicate detection (0-1)
- **`limits.page_snippet_length`** — Character limit for page content extraction
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
```

The AI models are configured per-task in `config.json` under `ai.models`. Each task has a primary and secondary model for automatic fallback when rate limited:

```json
"ai": {
  "models": {
    "article_filtering": {
      "primary": "gemini-3.6-flash",
      "secondary": "gemini-3.5-flash"
    },
    "weather": {
      "primary": "gemini-3.5-flash-lite",
      "secondary": "gemini-3.1-flash-lite"
    },
    "word_of_day": {
      "primary": "gemini-3.5-flash-lite",
      "secondary": "gemini-3.1-flash-lite"
    },
    "daily_puzzle": {
      "primary": "gemini-3.5-flash-lite",
      "secondary": "gemini-3.1-flash-lite"
    }
  },
  "prompts": { ... }
}
```

**Rate-limit tracking**: The pipeline now tracks actual rate limit usage from API responses (via `usage_metadata`) and logs it at the end of each run.

Without a key the pipeline falls back to local fuzzy-matching deduplication and sentence-extraction summaries — no functionality is lost, just quality.

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
