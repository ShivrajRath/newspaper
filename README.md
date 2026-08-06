# The Daily Brief

**A personal newspaper for the things that actually matter — built for focus, not feeds.**

---

The internet is full of noise. Infinite scrolls, clickbait, and algorithmic feeds engineered to keep you hooked.

**The Daily Brief** is the antidote. Once a day, it quietly pulls together news from the sources *you* choose — world news, tech, markets, Hacker News — and lays it out as a clean, readable newspaper. No recommendations. No notifications. No doomscrolling. Just today's brief, ready when you are.

You read it, you close it, you move on with your day.

---

## What it does

- Fetches headlines from RSS feeds you configure
- Pulls top Hacker News stories (above a score threshold you set)
- Shows live market data for stocks you care about
- Deduplicates stories so you're not reading the same news twice
- Renders everything as a single clean page — one newspaper, one day

---

## Quickstart

```bash
# Install dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install feedparser yfinance google-genai

# Build today's newspaper
python3 build_newspaper.py

# Open index.html in your browser
```

Optionally, set a `GEMINI_API_KEY` to enable smarter deduplication. Without it, a local fuzzy-matching fallback is used automatically.

---

## Configuration

Edit `config.json` to choose your news sources, stocks, and Hacker News settings. No code changes needed.

See [DEVELOPER.md](DEVELOPER.md) for architecture details, technical docs, and how to contribute.
