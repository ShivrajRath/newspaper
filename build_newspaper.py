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
MAX_SECTION_ARTICLES = 8
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


# WMO Weather Interpretation Codes → (description, emoji)
WMO_CODES = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Foggy", "🌫️"),
    48: ("Icy fog", "🌫️"),
    51: ("Light drizzle", "🌦️"),
    53: ("Moderate drizzle", "🌦️"),
    55: ("Dense drizzle", "🌧️"),
    61: ("Slight rain", "🌧️"),
    63: ("Moderate rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    71: ("Slight snow", "❄️"),
    73: ("Moderate snow", "❄️"),
    75: ("Heavy snow", "❄️"),
    80: ("Slight showers", "🌦️"),
    81: ("Moderate showers", "🌦️"),
    82: ("Heavy showers", "⛈️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm w/ hail", "⛈️"),
    99: ("Thunderstorm w/ heavy hail", "⛈️"),
}

# Curated word list for fallback (one per day-of-year, cycling)
FALLBACK_WORDS = [
    "ephemeral", "sonder", "serendipity", "melancholy", "luminous",
    "petrichor", "ineffable", "soliloquy", "halcyon", "querulous",
    "fugacious", "sempiternal", "laconic", "perspicacious", "ebullient",
    "recondite", "sanguine", "tenacious", "veracious", "whimsical",
    "zealous", "arcane", "benevolent", "cogent", "dauntless",
    "eloquent", "fastidious", "grandiose", "heuristic", "indefatigable",
]

FALLBACK_PUZZLES = [
    {
        "type": "riddle",
        "question": "I speak without a mouth and hear without ears. I have no body, but I come alive with the wind. What am I?",
        "answer": "An echo",
        "hint": "Think about sound bouncing back to you in a canyon."
    },
    {
        "type": "riddle",
        "question": "The more you take, the more you leave behind. What am I?",
        "answer": "Footsteps",
        "hint": "Think about walking on a trail."
    },
    {
        "type": "riddle",
        "question": "I have cities, but no houses live there. I have mountains, but no trees grow there. I have water, but no fish swim there. I have roads, but no cars drive there. What am I?",
        "answer": "A map",
        "hint": "You unfold me to find your way."
    },
    {
        "type": "riddle",
        "question": "What has hands but can't clap?",
        "answer": "A clock",
        "hint": "It helps you keep track of time."
    },
    {
        "type": "riddle",
        "question": "What gets wetter the more it dries?",
        "answer": "A towel",
        "hint": "You use it after a shower."
    },
    {
        "type": "riddle",
        "question": "I'm light as a feather, yet the strongest man can't hold me for more than a minute. What am I?",
        "answer": "Breath",
        "hint": "You do it automatically, all the time."
    },
    {
        "type": "riddle",
        "question": "What begins with T, ends with T, and has T in it?",
        "answer": "A teapot",
        "hint": "You boil water to use it."
    },
]


def fetch_quote_of_day():
    """Fetch the quote of the day from ZenQuotes with a graceful fallback."""
    try:
        with safe_urlopen("https://zenquotes.io/api/today", timeout=15) as req:
            raw_data = json.loads(req.read().decode())
            if raw_data:
                quote_data = raw_data[0]
                return {
                    "text": quote_data.get("q") or "Make each day your masterpiece.",
                    "author": quote_data.get("a") or "John Wooden"
                }
    except Exception as e:
        logging.warning("Error fetching quote: %s", e)

    return {
        "text": "Make each day your masterpiece.",
        "author": "John Wooden"
    }


def fetch_weather():
    """Fetch current weather for Frisco, TX using Open-Meteo (free, no key required)."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=33.1507&longitude=-96.8236"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
        "wind_speed_10m,weather_code,precipitation"
        "&temperature_unit=fahrenheit&wind_speed_unit=mph"
        "&timezone=America%2FChicago"
    )
    try:
        with safe_urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            curr = data.get("current", {})
            code = curr.get("weather_code", 0)
            desc, emoji = WMO_CODES.get(code, ("Unknown", "🌡️"))
            return {
                "temperature_f": round(curr.get("temperature_2m", 0)),
                "feels_like_f": round(curr.get("apparent_temperature", 0)),
                "humidity": curr.get("relative_humidity_2m", 0),
                "wind_mph": round(curr.get("wind_speed_10m", 0), 1),
                "precipitation_mm": curr.get("precipitation", 0),
                "condition": desc,
                "emoji": emoji,
                "location": "Frisco, TX"
            }
    except Exception as e:
        logging.warning("Error fetching weather: %s", e)
        return {
            "temperature_f": None,
            "condition": "Unavailable",
            "emoji": "🌡️",
            "location": "Frisco, TX"
        }


def fetch_word_of_day():
    """Generate Word of the Day using Gemini AI, with Free Dictionary API fallback."""
    global client

    # Try Gemini AI first
    if client:
        prompt = (
            "Pick an interesting, sophisticated English word suitable for a daily newspaper \"Word of the Day\" feature. "
            "Avoid extremely obscure jargon. Return ONLY a JSON object with these exact fields: "
            '{"word": "...", "part_of_speech": "...", "definition": "...", "example": "..."}'
            " where example is a short illustrative sentence using the word."
        )
        try:
            time.sleep(1)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )
            match = re.search(r'\{[^{}]+\}', response.text, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                if all(k in parsed for k in ("word", "part_of_speech", "definition", "example")):
                    logging.info("Word of the day from AI: %s", parsed["word"])
                    return parsed
        except Exception as e:
            err_str = str(e)
            if "404" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "NOT_FOUND" in err_str:
                logging.warning("Gemini AI API error (%s). Disabling AI.", e)
                client = None
            else:
                logging.warning("AI word-of-day failed: %s. Falling back.", e)

    # Fallback: pick word from curated list by day-of-year, look up definition
    day_of_year = datetime.now().timetuple().tm_yday
    word = FALLBACK_WORDS[day_of_year % len(FALLBACK_WORDS)]
    try:
        with safe_urlopen(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=10) as resp:
            entries = json.loads(resp.read().decode())
            if entries and isinstance(entries, list):
                entry = entries[0]
                meanings = entry.get("meanings", [])
                if meanings:
                    m = meanings[0]
                    defs = m.get("definitions", [])
                    definition = defs[0].get("definition", "") if defs else ""
                    example = defs[0].get("example", "") if defs else ""
                    return {
                        "word": word,
                        "part_of_speech": m.get("partOfSpeech", ""),
                        "definition": definition,
                        "example": example
                    }
    except Exception as e:
        logging.warning("Dictionary API fallback failed for '%s': %s", word, e)

    return {"word": word, "part_of_speech": "", "definition": "", "example": ""}


def fetch_daily_puzzle():
    """Generate a daily puzzle (riddle or trivia) using Gemini AI, with a fallback."""
    global client

    if client:
        prompt = (
            "Generate a fun, clever daily puzzle for a newspaper. "
            "It should be a riddle or lateral-thinking question that is not too easy and not too hard. "
            "Return ONLY a JSON object with exactly these fields: "
            '{"type": "riddle", "question": "...", "answer": "...", "hint": "..."}'
            " Keep the question under 30 words, and the answer under 6 words."
        )
        try:
            time.sleep(1)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )
            match = re.search(r'\{[^{}]+\}', response.text, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                if all(k in parsed for k in ("type", "question", "answer", "hint")):
                    logging.info("Daily puzzle from AI: %s", parsed["question"][:40])
                    return parsed
        except Exception as e:
            err_str = str(e)
            if "404" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "NOT_FOUND" in err_str:
                logging.warning("Gemini AI API error (%s). Disabling AI.", e)
                client = None
            else:
                logging.warning("AI puzzle generation failed: %s. Falling back.", e)

    # Fallback: pick from curated list by day-of-year
    day_of_year = datetime.now().timetuple().tm_yday
    return FALLBACK_PUZZLES[day_of_year % len(FALLBACK_PUZZLES)]


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


def fetch_feed_entries(url, max_items=15, max_age_days=1):
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


def fetch_section_articles(feed_urls, max_per_feed=15):
    """Fetch articles across all feed URLs specified for a section."""
    all_articles = []
    for url in feed_urls:
        entries = fetch_feed_entries(url, max_items=max_per_feed)
        all_articles.extend(entries)
    return all_articles


def local_deduplicate_articles(articles, max_items=15):
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


def ai_deduplicate_articles(articles, category_name, max_items=15):
    """Use Gemini AI to select the most relevant unique stories from a section.

    Ensures a single batched request per section to respect rate limits.
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
        f"Select up to {max_items} of the most relevant, non-overlapping stories. "
        f"Prioritize the most important and timely stories, removing duplicates and near-duplicates. "
        f"Return ONLY a JSON array of indices, e.g. [1, 3, 4]:"
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
    min_score = hn_config.get("min_score", 0)
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

        hacker_news = []
        for item in raw_hn_items:
            if item["score"] >= min_score:
                hacker_news.append({
                    "title": item["title"],
                    "url": item["url"],
                    "score": item["score"]
                })

        return hacker_news
    except Exception as e:
        logging.error("Error fetching Hacker News: %s", e)
        return []


def _parse_google_finance_quote(html_content, symbol):
    """Parse a lightweight Google Finance quote page for the latest price and change."""
    if not html_content:
        return None

    text = html_content.decode("utf-8", errors="ignore") if isinstance(html_content, bytes) else str(html_content)
    patterns = [
        r'(?i)<div[^>]+class="[^"]*YMlKec[^"]*"[^>]*>([0-9,\.]+)',
        r'(?i)<div[^>]+class="[^"]*P6K39c[^"]*"[^>]*>([+-]?[0-9,\.]+%?)',
    ]

    price_match = re.search(patterns[0], text)
    change_match = re.search(patterns[1], text)
    if not price_match:
        return None

    price = float(price_match.group(1).replace(",", ""))
    change_pct = 0.0
    if change_match:
        raw_change = change_match.group(1).replace(",", "")
        try:
            change_pct = float(raw_change.rstrip("%"))
        except ValueError:
            change_pct = 0.0

    return {
        "symbol": symbol,
        "price": price,
        "change_pct": change_pct,
    }


def fetch_market_data(market_config):
    """Fetch stock and commodity market data based on configuration."""
    if not market_config.get("enabled", True):
        return {}

    market_data = {}
    tickers_list = market_config.get("tickers", [])

    for ticker_info in tickers_list:
        symbol = ticker_info.get("symbol")
        label = ticker_info.get("label", symbol)
        ticker_type = ticker_info.get("type", "stock")

        if ticker_type == "commodity":
            continue

        if not symbol:
            continue

        try:
            import yfinance as yf
            stock = yf.Ticker(symbol)
            with open(os.devnull, "w") as fnull1, open(os.devnull, "w") as fnull2:
                with redirect_stdout(fnull1), redirect_stderr(fnull2):
                    hist = stock.history(period="2d")
            if len(hist) >= 2:
                prev_close = hist["Close"].iloc[-2]
                curr = hist["Close"].iloc[-1]
                pct = ((curr - prev_close) / prev_close) * 100
                market_data[label] = f"${curr:.2f} ({'+' if pct >= 0 else ''}{pct:.2f}%)"
                continue
        except Exception as exc:
            logging.warning("yfinance lookup failed for %s: %s", symbol, exc)

        try:
            encoded_symbol = urllib.parse.quote(symbol)
            google_url = f"https://www.google.com/finance/quote/{encoded_symbol}:NASDAQ"
            quote_html = safe_fetch_url(google_url, timeout=10)
            if quote_html is None:
                raise ValueError("No response from Google Finance")

            parsed_quote = _parse_google_finance_quote(quote_html, symbol)
            if parsed_quote is None:
                raise ValueError("Could not parse quote from Google Finance")

            change_prefix = "+" if parsed_quote["change_pct"] >= 0 else ""
            market_data[label] = f"${parsed_quote['price']:.2f} ({change_prefix}{parsed_quote['change_pct']:.2f}%)"
        except Exception as exc:
            logging.warning("Google Finance fallback failed for %s: %s", symbol, exc)
            continue

    return market_data


def build_newspaper():
    """Main function to load configuration, fetch data, deduplicate, and write newspaper.json."""
    config = load_config("config.json")

    output_content = {
        "generated_at": datetime.now().strftime("%B %d, %Y %I:%M %p"),
        "quote": fetch_quote_of_day(),
        "weather": fetch_weather(),
        "word_of_the_day": fetch_word_of_day(),
        "puzzle": fetch_daily_puzzle(),
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

        raw_articles = fetch_section_articles(feed_urls, max_per_feed=15)

        # Prefer AI selection when available; fall back to local deduplication otherwise.
        if client:
            filtered_articles = ai_deduplicate_articles(raw_articles, sec_name, max_items=MAX_SECTION_ARTICLES)
        else:
            filtered_articles = local_deduplicate_articles(raw_articles, max_items=MAX_SECTION_ARTICLES)

        output_content["categories"][sec_name] = {
            "summary": "",
            "articles": filtered_articles[:MAX_SECTION_ARTICLES]
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
