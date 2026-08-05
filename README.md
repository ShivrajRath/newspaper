# The Daily Brief - Automated Newspaper Generator

A modern, highly customizable automated newspaper generator. It fetches news from RSS feeds, Hacker News, and financial market tickers, formats them into a clean JSON structure (`newspaper.json`), and renders an elegant daily brief interface (`index.html`).

---

## Features

- **Declarative Configuration (`config.json`)**: Easily configure news sections, multiple RSS feeds per section, Hacker News settings, and stock pickers without modifying any Python code.
- **Multi-Feed RSS Aggregation**: Under any section, specify one or multiple RSS feeds.
- **AI-Powered Deduplication**: Automatically filters out duplicate or overlapping news stories when multiple RSS feeds are configured under a section using Google Gemini AI. Includes a rule-based fuzzy matching fallback if Gemini API is disabled or rate-limited.
- **Strict AI Rate-Limit Compliance**: Ensures AI operations remain well within Gemini rate limits (max 15 calls/min) by batching requests (e.g. 1 call per section deduplication, 1 call for Hacker News summaries).
- **Automated Market Tickers**: Supports stock market tickers using `yfinance` without relying on Google Finance fallback.
- **Responsive Daily Brief Dashboard**: Renders articles and market data seamlessly in `index.html`.

---

## Configuration (`config.json`)

To add new news categories, RSS feeds, or stocks, simply edit `config.json`:

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

---

## Getting Started

### 1. Requirements & Setup

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install feedparser yfinance google-genai
```

### 2. Set Up Gemini API Key (Optional)

To enable AI deduplication and batch summarization:

```bash
export GEMINI_API_KEY="your_api_key_here"
# Optional: specify model (defaults to gemini-3.5-flash)
export GEMINI_MODEL="gemini-3.5-flash"
```

_Note: If no API key is set, the application automatically uses smart local fuzzy matching deduplication and sentence extraction fallbacks._

### 3. Build the Newspaper

Generate `newspaper.json`:

```bash
python3 build_newspaper.py
```

### 4. View in Browser

Open `index.html` in your web browser.

---

## Running Unit Tests

Run the test suite using `unittest`:

```bash
python3 -m unittest test_newspaper.py
```
