import os
import json
import logging
import re
import html
import ssl
import feedparser
import urllib.request
import urllib.parse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
model = None

try:
    if GEMINI_API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
except Exception:
    model = None


def clean_html(text):
    """Remove anchor tags and other HTML tags, unescape HTML entities."""
    if not text:
        return ""
    # Remove anchor tags but keep their inner text
    text = re.sub(r'<a[^>]*>(.*?)</a>', r'\1', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove any remaining tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Normalize whitespace and unescape
    text = ' '.join(text.split())
    return html.unescape(text)


def summarize_text(articles_text, category_name):
    """Create a simple non-AI summary: up to 3 concise bullets from article titles/summaries.

    This intentionally avoids calling any external generative model and filters
    out empty or placeholder lines (like lone bullets).
    """
    lines = [line.strip() for line in articles_text.splitlines() if line.strip()]
    cleaned = []
    for line in lines:
        # remove leading bullets or numbering
        line = re.sub(r'^[\u2022\-\*\s]+', '', line).strip()
        # drop very short or placeholder lines
        if not line or line in ('.', '-'): 
            continue
        # if the line contains a colon, take text after it (title: summary)
        if ':' in line:
            _, text = line.split(':', 1)
            text = text.strip()
        else:
            text = line
        if text:
            cleaned.append(text)
        if len(cleaned) >= 3:
            break

    if cleaned:
        return "\n".join(f"• {c}" for c in cleaned)
    return 'No concise summary available.'


FEEDS = {
    "Science": "https://www.sciencedaily.com/rss/top/science.xml",
    "Technology": "https://feeds.arstechnica.com/arstechnica/index",
    "World News": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "Business": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Sports": "https://www.theguardian.com/sport/rss",
    "Frisco TX": "https://news.google.com/rss/search?q=Frisco+TX&hl=en-US&gl=US&ceid=US:en",
    "Local": "https://www.wfaa.com/feeds/syndication/rss/news/local",
}

content = {
    "generated_at": datetime.now().strftime("%B %d, %Y %I:%M %p"),
    "categories": {},
    "market": {},
    "hacker_news": []
}


def safe_fetch_url(url, timeout=15):
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.quote(parsed.query, safe='=&|:+()') if parsed.query else ''
    safe_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))
    request = urllib.request.Request(safe_url, headers={"User-Agent": "Mozilla/5.0"})

    for ctx in (ssl.create_default_context(), ssl._create_unverified_context()):
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=ctx) as response:
                return response.read()
        except Exception:
            continue
    return None


def safe_urlopen(url, timeout=15):
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.quote(parsed.query, safe='=&|:+()') if parsed.query else ''
    safe_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))
    request = urllib.request.Request(safe_url, headers={"User-Agent": "Mozilla/5.0"})

    for ctx in (ssl.create_default_context(), ssl._create_unverified_context()):
        try:
            return urllib.request.urlopen(request, timeout=timeout, context=ctx)
        except Exception:
            continue
    return None


def fetch_feed_entries(url, max_items=5):
    raw_data = safe_fetch_url(url)
    if raw_data is None:
        logging.warning("Unable to fetch feed URL: %s", url)
        return []

    feed = feedparser.parse(raw_data)
    if getattr(feed, "bozo", False):
        bozo_exception = getattr(feed, "bozo_exception", None)
        logging.warning("Feed parse problem for %s: %s", url, bozo_exception)

    if not getattr(feed, "entries", None):
        logging.warning("No entries found for feed URL: %s", url)
        return []

    def entry_is_recent(entry, max_age_days=2):
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if not parsed:
            return True
        published = datetime(*parsed[:6], tzinfo=timezone.utc)
        return published >= datetime.now(timezone.utc) - timedelta(days=max_age_days)

    articles = []
    for entry in feed.entries:
        if not entry_is_recent(entry):
            continue
        title_raw = entry.get("title", "Untitled")
        summary_raw = entry.get("summary", entry.get("description", ""))
        title = clean_html(title_raw).strip()
        summary = clean_html(summary_raw).strip()
        articles.append({
            "title": title or "Untitled",
            "summary": summary,
            "link": entry.get("link", "")
        })
        if len(articles) >= max_items:
            break
    return articles


def extract_page_snippet(url):
    """Fetches raw text content from the target URL for summarization."""
    html_bytes = safe_fetch_url(url, timeout=10)
    if not html_bytes:
        return ""

    html = html_bytes.decode("utf-8", errors="ignore")
    clean_text = re.sub(r'<script.*?>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r'<style.*?>.*?</style>', ' ', clean_text, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
    return " ".join(clean_text.split())[:1800]


def summarize_article_description(snippet):
    if snippet and model:
        prompt = (
            "Provide a single concise sentence describing what this article is about "
            "based on this snippet:\n" + snippet
        )
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            if text:
                return text
        except Exception:
            pass

    if snippet:
        first_sentence = snippet.split('. ')[0].strip()
        if first_sentence:
            return first_sentence.rstrip('.') + '.'
    return "Click link to read story."


for category, url in FEEDS.items():
    articles = fetch_feed_entries(url, max_items=5)
    summary = ""
    if not articles:
        summary = "No articles were available from this feed."

    content["categories"][category] = {
        "summary": summary,
        "articles": articles[:4]
    }


try:
    with safe_urlopen("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=15) as req:
        top_ids = json.loads(req.read().decode())[:5]
    hacker_news = []
    for item_id in top_ids:
        with safe_urlopen(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json", timeout=15) as item_req:
            data = json.loads(item_req.read().decode())
            article_url = data.get("url", f"https://news.ycombinator.com/item?id={item_id}")
            snippet = extract_page_snippet(article_url) if article_url else ""
            hacker_news.append({
                "title": data.get("title", "Untitled story"),
                "url": article_url,
                "score": data.get("score", 0),
                "description": summarize_article_description(snippet)
            })
    content["hacker_news"] = hacker_news
except Exception:
    content["hacker_news"] = []


def parse_google_finance_price(html, symbol, exchange=None):
    if symbol == "Gold":
        pattern = r'\["GCW00","COMEX"\],"Gold",\d+,"USD",\[([0-9]+\.[0-9]+),([0-9eE+\-.]+),([0-9eE+\-.]+)'
    else:
        symbol_escaped = re.escape(symbol)
        exchange_escaped = re.escape(exchange or "")
        pattern = rf'\[\["/m/[^"]*",\["{symbol_escaped}","{exchange_escaped}"\],"[^"]*",\d+,"USD",\[([0-9]+\.[0-9]+),([0-9eE+\-.]+),([0-9eE+\-.]+)'

    match = re.search(pattern, html)
    if not match:
        return None

    price = float(match.group(1))
    change = float(match.group(2))
    pct = float(match.group(3))
    return price, change, pct


def fetch_google_finance_price(url, symbol, exchange=None):
    raw_data = safe_fetch_url(url)
    if raw_data is None:
        return None

    html = raw_data.decode("utf-8", errors="replace")
    parsed = parse_google_finance_price(html, symbol, exchange)
    if parsed is None:
        return None

    price, change, pct = parsed
    return {
        "price": price,
        "change": change,
        "pct": pct
    }


def fetch_market_data():
    market_data = {}
    try:
        import yfinance as yf
        tickers = {
            "AAPL": "AAPL",
            "ADSK": "ADSK",
            "MSFT": "MSFT",
            "VOO": "VOO"
        }
        for ticker, label in tickers.items():
            try:
                stock = yf.Ticker(ticker)
                with redirect_stdout(open(os.devnull, "w")), redirect_stderr(open(os.devnull, "w")):
                    hist = stock.history(period="2d")
                if len(hist) >= 2:
                    prev_close = hist["Close"].iloc[-2]
                    curr = hist["Close"].iloc[-1]
                    pct = ((curr - prev_close) / prev_close) * 100
                    market_data[label] = f"${curr:.2f} ({'+' if pct >= 0 else ''}{pct:.2f}%)"
            except Exception:
                continue
    except Exception:
        pass

    if "Gold" not in market_data:
        google_gold = fetch_google_finance_price("https://www.google.com/finance/quote/GC%3D%3DF:COM", "Gold")
        if google_gold is not None:
            market_data["Gold"] = f"${google_gold['price']:.2f}/oz ({'+' if google_gold['change'] >= 0 else ''}{google_gold['pct']:.2f}%)"

    google_fallbacks = {
        "AAPL": ("https://www.google.com/finance/quote/AAPL:NASDAQ", "NASDAQ"),
        "ADSK": ("https://www.google.com/finance/quote/ADSK:NASDAQ", "NASDAQ"),
        "MSFT": ("https://www.google.com/finance/quote/MSFT:NASDAQ", "NASDAQ"),
        "VOO": ("https://www.google.com/finance/quote/VOO:NASDAQ", "NASDAQ")
    }
    for label, (url, exchange) in google_fallbacks.items():
        if label in market_data:
            continue
        google_data = fetch_google_finance_price(url, label, exchange)
        if google_data is not None:
            market_data[label] = f"${google_data['price']:.2f} ({'+' if google_data['change'] >= 0 else ''}{google_data['pct']:.2f}%)"

    return market_data


content["market"] = fetch_market_data()

with open("newspaper.json", "w", encoding="utf-8") as f:
    json.dump(content, f, indent=2, ensure_ascii=False)
