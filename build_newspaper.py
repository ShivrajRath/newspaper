import os
import json
import logging
import re
import html
import ssl
import feedparser
import urllib.request
import urllib.parse
import difflib
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
client = None

try:
    if GEMINI_API_KEY:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    logging.warning("Gemini AI client initialization failed or key not set: %s", e)
    client = None


def load_config(config_path="config.json"):
    """Load configuration file or return an empty config if unavailable."""
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                logging.info("Successfully loaded configuration from %s", config_path)
                return config
        except Exception as e:
            logging.error("Failed to parse %s: %s. Using empty config.", config_path, e)
    else:
        logging.info("Configuration file %s not found. Using empty config.", config_path)
    return {}


def clean_html(text):
    """Remove anchor tags and other HTML tags, unescape HTML entities."""
    if not text:
        return ""
    text = re.sub(r'<a[^>]*>(.*?)</a>', r'\1', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = ' '.join(text.split())
    return html.unescape(text)


def safe_fetch_url(url, timeout=15):
    """Safely fetch raw bytes from URL supporting SSL fallback."""
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
    """Safely open URL returning response handle."""
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


def fetch_feed_entries(url, max_items=5, max_age_days=2):
    """Fetch recent feed entries from an RSS feed URL."""
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

    def entry_is_recent(entry):
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


def fetch_section_articles(feed_urls, max_per_feed=5):
    """Fetch articles across all feed URLs specified for a section."""
    all_articles = []
    for url in feed_urls:
        entries = fetch_feed_entries(url, max_items=max_per_feed)
        all_articles.extend(entries)
    return all_articles


def local_deduplicate_articles(articles, max_items=4):
    """Filter duplicate or near-duplicate articles using rule-based title similarity."""
    if not articles:
        return []

    unique_articles = []
    seen_titles = []

    for art in articles:
        title = art.get("title", "").strip()
        if not title:
            continue

        normalized_title = re.sub(r'[^\w\s]', '', title.lower())
        is_duplicate = False

        for seen in seen_titles:
            # Check exact or near-exact string similarity
            ratio = difflib.SequenceMatcher(None, normalized_title, seen).ratio()
            if ratio > 0.65:
                is_duplicate = True
                break
            # Check word overlap
            words1 = set(normalized_title.split())
            words2 = set(seen.split())
            if words1 and words2:
                intersection = words1.intersection(words2)
                overlap = len(intersection) / max(len(words1), len(words2))
                if overlap > 0.7:
                    is_duplicate = True
                    break

        if not is_duplicate:
            unique_articles.append(art)
            seen_titles.append(normalized_title)

        if len(unique_articles) >= max_items:
            break

    return unique_articles[:max_items]


def ai_deduplicate_articles(articles, category_name, max_items=4):
    """Use Gemini AI to filter out duplicate/overlapping articles from multiple RSS feeds.
    
    Ensures single batched request per section to respect rate limits.
    Falls back to local_deduplicate_articles on failure or if client is missing.
    """
    global client
    if not articles:
        return []

    if len(articles) <= 1 or not client:
        return local_deduplicate_articles(articles, max_items=max_items)

    formatted_list = []
    for idx, art in enumerate(articles, 1):
        formatted_list.append(f"[{idx}] {art.get('title')}")

    articles_str = "\n".join(formatted_list)
    prompt = (
        f"Category: {category_name}\n"
        f"Titles:\n{articles_str}\n\n"
        f"Select up to {max_items} unique story indices. Remove duplicates. Return ONLY a JSON array of indices, e.g. [1, 3, 4]:"
    )

    try:
        time.sleep(1)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        response_text = response.text.strip()
        match = re.search(r'\[[\d\s,]+\]', response_text)
        if match:
            selected_indices = json.loads(match.group(0))
            selected_articles = []
            seen_idx = set()
            for i in selected_indices:
                if isinstance(i, int) and 1 <= i <= len(articles) and i not in seen_idx:
                    selected_articles.append(articles[i - 1])
                    seen_idx.add(i)
                if len(selected_articles) >= max_items:
                    break
            if selected_articles:
                logging.info("AI deduplication selected %d unique articles for %s", len(selected_articles), category_name)
                return selected_articles
    except Exception as e:
        err_str = str(e)
        if "404" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "NOT_FOUND" in err_str:
            logging.warning("Gemini AI API error (%s). Disabling AI for remaining sections and using local fallback.", e)
            client = None
        else:
            logging.warning("AI deduplication call failed for %s: %s. Using local fallback.", category_name, e)

    return local_deduplicate_articles(articles, max_items=max_items)


def extract_page_snippet(url):
    """Fetches raw text content from target URL for summarization."""
    html_bytes = safe_fetch_url(url, timeout=10)
    if not html_bytes:
        return ""

    html_content = html_bytes.decode("utf-8", errors="ignore")
    clean_text = re.sub(r'<script.*?>.*?</script>', ' ', html_content, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r'<style.*?>.*?</style>', ' ', clean_text, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
    return " ".join(clean_text.split())[:1800]


def summarize_hn_stories_batched(items_data):
    """Summarize multiple HN stories in a single batched Gemini call to preserve rate limits."""
    global client
    descriptions = []

    if client and items_data:
        stories_input = []
        for idx, item in enumerate(items_data, 1):
            snippet = item.get("snippet", "")
            title = item.get("title", "")
            stories_input.append(f"Story {idx}:\nTitle: {title}\nSnippet: {snippet[:400]}")

        prompt = (
            "For each story listed below, write a single concise summary sentence (10-20 words).\n"
            "Return ONLY a JSON array of strings corresponding to each story in order.\n"
            "Example: [\"Summary 1.\", \"Summary 2.\"]\n\n" +
            "\n\n".join(stories_input)
        )

        try:
            time.sleep(1)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )
            match = re.search(r'\[\s*".*?"\s*\]', response.text, flags=re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list) and len(parsed) == len(items_data):
                    return [str(s).strip() for s in parsed]
        except Exception as e:
            err_str = str(e)
            if "404" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "NOT_FOUND" in err_str:
                logging.warning("Gemini AI API error (%s). Disabling AI for remaining tasks and using local fallback.", e)
                client = None
            else:
                logging.warning("Batched HN AI summarization failed: %s. Falling back to snippet extraction.", e)

    # Local fallback for HN descriptions
    for item in items_data:
        snippet = item.get("snippet", "")
        if snippet:
            first_sentence = snippet.split('. ')[0].strip()
            if first_sentence:
                descriptions.append(first_sentence.rstrip('.') + '.')
                continue
        descriptions.append("Click link to read story.")

    return descriptions


def fetch_hacker_news(hn_config):
    """Fetch Hacker News top stories using configuration settings."""
    if not hn_config.get("enabled", True):
        return []

    max_items = hn_config.get("max_items", 5)
    try:
        with safe_urlopen("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=15) as req:
            top_ids = json.loads(req.read().decode())[:max_items]

        raw_hn_items = []
        for item_id in top_ids:
            with safe_urlopen(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json", timeout=15) as item_req:
                data = json.loads(item_req.read().decode())
                article_url = data.get("url", f"https://news.ycombinator.com/item?id={item_id}")
                snippet = extract_page_snippet(article_url) if article_url else ""
                raw_hn_items.append({
                    "title": data.get("title", "Untitled story"),
                    "url": article_url,
                    "score": data.get("score", 0),
                    "snippet": snippet
                })

        descriptions = summarize_hn_stories_batched(raw_hn_items)

        hacker_news = []
        for idx, item in enumerate(raw_hn_items):
            hacker_news.append({
                "title": item["title"],
                "url": item["url"],
                "score": item["score"],
                "description": descriptions[idx] if idx < len(descriptions) else "Click link to read story."
            })

        return hacker_news
    except Exception as e:
        logging.error("Error fetching Hacker News: %s", e)
        return []


def fetch_market_data(market_config):
    """Fetch stock and commodity market data based on configuration."""
    if not market_config.get("enabled", True):
        return {}

    market_data = {}
    tickers_list = market_config.get("tickers", [])

    try:
        import yfinance as yf
        for ticker_info in tickers_list:
            symbol = ticker_info.get("symbol")
            label = ticker_info.get("label", symbol)
            ticker_type = ticker_info.get("type", "stock")

            if ticker_type == "commodity":
                continue

            try:
                stock = yf.Ticker(symbol)
                with open(os.devnull, "w") as fnull1, open(os.devnull, "w") as fnull2:
                    with redirect_stdout(fnull1), redirect_stderr(fnull2):
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

    return market_data


def build_newspaper():
    """Main function to load configuration, fetch data, deduplicate, and write newspaper.json."""
    config = load_config("config.json")

    output_content = {
        "generated_at": datetime.now().strftime("%B %d, %Y %I:%M %p"),
        "categories": {},
        "market": {},
        "hacker_news": []
    }

    # Fetch Sections (RSS feeds)
    sections = config.get("sections", [])
    for section in sections:
        sec_name = section.get("name", "General")
        feed_urls = section.get("feeds", [])

        if not feed_urls:
            output_content["categories"][sec_name] = {
                "summary": "",
                "articles": []
            }
            continue

        raw_articles = fetch_section_articles(feed_urls, max_per_feed=5)
        
        # Deduplicate articles using AI if multiple feeds, otherwise local deduplication
        if len(feed_urls) > 1:
            filtered_articles = ai_deduplicate_articles(raw_articles, sec_name, max_items=4)
        else:
            filtered_articles = local_deduplicate_articles(raw_articles, max_items=4)

        output_content["categories"][sec_name] = {
            "summary": "",
            "articles": filtered_articles
        }

    # Fetch Hacker News
    output_content["hacker_news"] = fetch_hacker_news(config.get("hacker_news", {}))

    # Fetch Market Data
    output_content["market"] = fetch_market_data(config.get("market", {}))

    # Save to newspaper.json
    with open("newspaper.json", "w", encoding="utf-8") as f:
        json.dump(output_content, f, indent=2, ensure_ascii=False)

    logging.info("Successfully generated newspaper.json with %d sections.", len(output_content["categories"]))


if __name__ == "__main__":
    build_newspaper()
