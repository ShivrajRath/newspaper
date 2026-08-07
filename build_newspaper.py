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


def get_config_value(config, key_path, default):
    """Get a nested config value using dot notation (e.g., 'ai.model')."""
    keys = key_path.split('.')
    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value


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
    """Fetch current weather for Frisco, TX using Open-Meteo (free, no key required) and generate AI description."""
    global client
    
    # Load config
    config = load_config("config.json")
    weather_config = config.get("weather", {})
    ai_config = config.get("ai", {})
    
    location = weather_config.get("location", "Frisco, TX")
    latitude = weather_config.get("latitude", 33.1507)
    longitude = weather_config.get("longitude", -96.8236)
    gemini_model = ai_config.get("model", "gemini-3.5-flash")
    weather_prompt = get_config_value(ai_config, "prompts.weather", 
        "Turn this weather data into a short 1-sentence newspaper header snippet (e.g. '🌤️ Frisco: High of 92°F, Low of 74°F with scattered clouds'): {data}")
    
    # Simplified API call - only get current and daily data we need
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}&longitude={longitude}"
        "&current=temperature_2m,weather_code"
        "&daily=temperature_2m_max,temperature_2m_min,weather_code"
        "&temperature_unit=fahrenheit&wind_speed_unit=mph"
        "&timezone=America/Chicago"
    )
    
    try:
        with safe_urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            
            # Current temp
            current_temp = round(data.get("current", {}).get("temperature_2m", 0))
            
            # Daily forecast max & min (index 0 is today)
            daily = data.get("daily", {})
            high_temp = round(daily.get("temperature_2m_max", [0])[0])
            low_temp = round(daily.get("temperature_2m_min", [0])[0])
            code = daily.get("weather_code", [0])[0]
            desc, emoji = WMO_CODES.get(code, ("Variable conditions", "🌡️"))
            
            # Ground truth string
            raw_summary = (
                f"{location}: Currently {current_temp}°F, High of {high_temp}°F, Low of {low_temp}°F with {desc.lower()}."
            )
            
            # Generate AI description if available
            ai_description = None
            if client:
                try:
                    prompt = weather_prompt.format(data=raw_summary)
                    time.sleep(1)
                    response = client.models.generate_content(
                        model=gemini_model,
                        contents=prompt
                    )
                    ai_description = response.text.strip()
                    logging.info("AI weather description generated: %s", ai_description[:50])
                except Exception as e:
                    err_str = str(e)
                    if "404" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "NOT_FOUND" in err_str:
                        logging.warning("Gemini AI API error (%s). Disabling AI.", e)
                        client = None
                    else:
                        logging.warning("AI weather description failed: %s. Using fallback.", e)
            
            # Fallback to formatted string if AI unavailable
            if not ai_description:
                ai_description = f"🌤️ {raw_summary}"
            
            return {
                "location": location,
                "temperature_f": current_temp,
                "high_temp_f": high_temp,
                "low_temp_f": low_temp,
                "condition": desc,
                "emoji": emoji,
                "description": ai_description
            }
            
    except Exception as e:
        logging.warning("Error fetching weather: %s", e)
        return {
            "location": location,
            "temperature_f": None,
            "high_temp_f": None,
            "low_temp_f": None,
            "condition": "Unavailable",
            "emoji": "🌡️",
            "description": f"🌡️ {location} weather unavailable"
        }


def fetch_word_of_day():
    """Generate Word of the Day using Gemini AI, with Free Dictionary API fallback."""
    global client

    # Load config
    config = load_config("config.json")
    ai_config = config.get("ai", {})
    gemini_model = ai_config.get("model", "gemini-3.5-flash")
    word_prompt = get_config_value(ai_config, "prompts.word_of_day",
        "Pick an interesting, sophisticated English word suitable for a daily newspaper \"Word of the Day\" feature. Avoid extremely obscure jargon. Return ONLY a JSON object with these exact fields: {\"word\": \"...\", \"part_of_speech\": \"...\", \"definition\": \"...\", \"example\": \"...\"} where example is a short illustrative sentence using the word.")

    # Try Gemini AI first
    if client:
        try:
            time.sleep(1)
            response = client.models.generate_content(
                model=gemini_model,
                contents=word_prompt
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

    # Load config
    config = load_config("config.json")
    ai_config = config.get("ai", {})
    gemini_model = ai_config.get("model", "gemini-3.5-flash")
    puzzle_prompt = get_config_value(ai_config, "prompts.daily_puzzle",
        "Generate a fun, clever daily puzzle for a newspaper. It should be a riddle or lateral-thinking question that is not too easy and not too hard. Return ONLY a JSON object with exactly these fields: {\"type\": \"riddle\", \"question\": \"...\", \"answer\": \"...\", \"hint\": \"...\"} Keep the question under 30 words, and the answer under 6 words.")

    if client:
        try:
            time.sleep(1)
            response = client.models.generate_content(
                model=gemini_model,
                contents=puzzle_prompt
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
    if parsed.query:
        # Unquote first to decode any existing encoding, then re-quote with safe characters
        unquoted_query = urllib.parse.unquote(parsed.query)
        query = urllib.parse.quote(unquoted_query, safe=',=&|:+()/')
    else:
        query = ''
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
    """Safely open URL returning response handle. Raises ConnectionError if all attempts fail."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.query:
        # Unquote first to decode any existing encoding, then re-quote with safe characters
        unquoted_query = urllib.parse.unquote(parsed.query)
        query = urllib.parse.quote(unquoted_query, safe=',=&|:+()/')
    else:
        query = ''
    safe_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))
    request = urllib.request.Request(safe_url, headers={"User-Agent": "Mozilla/5.0"})

    last_exc = None
    for ctx in (ssl.create_default_context(), ssl._create_unverified_context()):
        try:
            return urllib.request.urlopen(request, timeout=timeout, context=ctx)
        except Exception as exc:
            last_exc = exc
            continue
    raise ConnectionError(f"Failed to open URL {url}: {last_exc}")


def fetch_feed_entries(url, max_items=15, max_age_days=1):
    """Fetch recent feed entries from an RSS feed URL."""
    # Load config for default values
    config = load_config("config.json")
    limits_config = config.get("limits", {})
    
    if max_items == 15:  # Use default if not explicitly provided
        max_items = limits_config.get("max_per_feed", 15)
    if max_age_days == 1:  # Use default if not explicitly provided
        max_age_days = limits_config.get("max_feed_age_days", 1)
    
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

    # Load config for thresholds
    config = load_config("config.json")
    limits_config = config.get("limits", {})
    similarity_threshold = limits_config.get("deduplication_similarity_threshold", 0.65)
    word_overlap_threshold = limits_config.get("word_overlap_threshold", 0.7)

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
            if ratio > similarity_threshold:
                is_duplicate = True
                break
            # Check word overlap
            words1 = set(normalized_title.split())
            words2 = set(seen.split())
            if words1 and words2:
                intersection = words1.intersection(words2)
                overlap = len(intersection) / max(len(words1), len(words2))
                if overlap > word_overlap_threshold:
                    is_duplicate = True
                    break

        if not is_duplicate:
            unique_articles.append(art)
            seen_titles.append(normalized_title)

        if len(unique_articles) >= max_items:
            break

    return unique_articles[:max_items]


def fetch_all_feeds_globally(sections, max_per_feed=15):
    """Fetch all RSS articles from every section once and tag each item with its section."""
    # Load config for default values
    config = load_config("config.json")
    limits_config = config.get("limits", {})
    
    if max_per_feed == 15:  # Use default if not explicitly provided
        max_per_feed = limits_config.get("max_per_feed", 15)
    
    all_articles = []
    for section in sections:
        sec_name = section.get("name", "General")
        feed_urls = section.get("feeds", [])
        if not feed_urls:
            continue
        raw_articles = fetch_section_articles(feed_urls, max_per_feed=max_per_feed)
        for article in raw_articles:
            tagged_article = dict(article)
            tagged_article["section"] = sec_name
            all_articles.append(tagged_article)
    return all_articles


def _local_group_articles_by_section(all_articles, max_per_section=15):
    """Fallback grouping that preserves section membership without cross-section deduplication."""
    # Load config for default values
    config = load_config("config.json")
    limits_config = config.get("limits", {})
    
    if max_per_section == 15:  # Use default if not explicitly provided
        max_per_section = limits_config.get("max_section_articles", 8)
    
    grouped_articles = {}
    section_order = []
    for article in all_articles:
        sec_name = article.get("section", "General")
        if sec_name not in grouped_articles:
            grouped_articles[sec_name] = []
            section_order.append(sec_name)
        grouped_articles[sec_name].append(article)

    for sec_name in section_order:
        grouped_articles[sec_name] = local_deduplicate_articles(grouped_articles[sec_name], max_items=max_per_section)

    return grouped_articles


def ai_global_deduplicate_and_filter(all_articles, max_per_section=15):
    """Use a single AI call to deduplicate across sections and filter insignificant stories."""
    global client

    # Load config
    config = load_config("config.json")
    ai_config = config.get("ai", {})
    limits_config = config.get("limits", {})
    
    gemini_model = ai_config.get("model", "gemini-3.5-flash")
    dedup_prompt = get_config_value(ai_config, "prompts.global_deduplication",
        "You are selecting the most important and relevant news stories for a daily newspaper. Review all article titles below, then return a JSON object mapping each section name to a list of article indices to keep. Remove duplicates and near-duplicates across sections. Filter out low-value stories that are insignificant or not broadly relevant to readers, including gore, graphic violence, isolated crime, single-casualty incidents, routine police blotter items, celebrity gossip, and other clickbait. Exclude routine local crime stories such as 'Police investigate after man found dead in parking lot', 'Body found in [location]', 'Shooting investigation underway', or similar isolated incidents without broader impact. Do not include stories about a person being found dead, killed, injured, or arrested without a broader impact, unless the event is a major escalation, public safety crisis, mass casualty event, natural disaster, or major policy/geopolitical development. Keep significant and timely stories including major escalations, natural disasters, major accidents, notable scientific breakthroughs, and major policy or geopolitical developments. Return ONLY valid JSON with this shape: {\"Section Name\": [1, 3, 5]}.")
    
    if max_per_section == 15:  # Use default if not explicitly provided
        max_per_section = limits_config.get("max_section_articles", 8)

    if not all_articles:
        return {}

    if not client:
        return _local_group_articles_by_section(all_articles, max_per_section=max_per_section)

    formatted_list = []
    for idx, article in enumerate(all_articles, 1):
        sec_name = article.get("section", "General")
        title = article.get("title", "Untitled").strip()
        formatted_list.append(f"[{idx}] {title} ({sec_name})")

    prompt = dedup_prompt + f"\n\nTitles:\n" + "\n".join(formatted_list)

    try:
        time.sleep(1)
        response = client.models.generate_content(
            model=gemini_model,
            contents=prompt
        )
        response_text = response.text.strip()
        match = re.search(r'(\{.*\}|\[\s*[\d\s,]+\s*\])', response_text, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON payload found in AI response")

        parsed = json.loads(match.group(0))
        grouped_articles = {}

        if isinstance(parsed, dict):
            for section_name, selected_indices in parsed.items():
                if not isinstance(section_name, str):
                    continue
                selected_articles = []
                seen_indices = set()
                for index in selected_indices:
                    if isinstance(index, int) and 1 <= index <= len(all_articles) and index not in seen_indices:
                        article = all_articles[index - 1]
                        if article.get("section", "General") == section_name:
                            selected_articles.append(article)
                            seen_indices.add(index)
                grouped_articles[section_name] = selected_articles[:max_per_section]
        elif isinstance(parsed, list):
            selected_articles = []
            seen_indices = set()
            for index in parsed:
                if isinstance(index, int) and 1 <= index <= len(all_articles) and index not in seen_indices:
                    selected_articles.append(all_articles[index - 1])
                    seen_indices.add(index)
            if len({article.get("section", "General") for article in selected_articles}) <= 1:
                section_name = all_articles[0].get("section", "General") if all_articles else "General"
                grouped_articles[section_name] = selected_articles[:max_per_section]
            else:
                raise ValueError("AI response array did not map to a single section")
        else:
            raise ValueError("AI response was not a JSON object or array")

        if not grouped_articles:
            raise ValueError("AI response did not contain any sections")

        section_names = []
        for article in all_articles:
            sec_name = article.get("section", "General")
            if sec_name not in section_names:
                section_names.append(sec_name)

        for sec_name in section_names:
            grouped_articles.setdefault(sec_name, [])

        logging.info("AI global deduplication selected stories across %d articles", len(all_articles))
        return grouped_articles
    except Exception as e:
        err_str = str(e)
        if "404" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "NOT_FOUND" in err_str:
            logging.warning("Gemini AI API error (%s). Disabling AI for remaining tasks and using local fallback.", e)
            client = None
        else:
            logging.warning("AI global deduplication failed: %s. Using local fallback.", e)

    return _local_group_articles_by_section(all_articles, max_per_section=max_per_section)


def ai_deduplicate_articles(articles, category_name, max_items=15):
    """Use Gemini AI to select the most relevant unique stories from a section.

    Ensures a single batched request per section to respect rate limits.
    Falls back to local_deduplicate_articles on failure or if client is missing.
    """
    global client
    
    # Load config
    config = load_config("config.json")
    ai_config = config.get("ai", {})
    limits_config = config.get("limits", {})
    
    gemini_model = ai_config.get("model", "gemini-3.5-flash")
    section_dedup_prompt = get_config_value(ai_config, "prompts.section_deduplication",
        "Category: {category}\nTitles:\n{titles}\n\nSelect up to {max_items} of the most relevant, non-overlapping stories. Prioritize the most important and timely stories, removing duplicates and near-duplicates. Return ONLY a JSON array of indices, e.g. [1, 3, 4]:")
    
    if max_items == 15:  # Use default if not explicitly provided
        max_items = limits_config.get("max_section_articles", 8)
    
    if not articles:
        return []

    if len(articles) <= 1 or not client:
        return local_deduplicate_articles(articles, max_items=max_items)

    formatted_list = []
    for idx, art in enumerate(articles, 1):
        formatted_list.append(f"[{idx}] {art.get('title')}")

    articles_str = "\n".join(formatted_list)
    prompt = section_dedup_prompt.format(
        category=category_name,
        titles=articles_str,
        max_items=max_items
    )

    try:
        time.sleep(1)
        response = client.models.generate_content(
            model=gemini_model,
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
    # Load config for snippet length
    config = load_config("config.json")
    limits_config = config.get("limits", {})
    snippet_length = limits_config.get("page_snippet_length", 1800)
    
    html_bytes = safe_fetch_url(url, timeout=10)
    if not html_bytes:
        return ""

    html_content = html_bytes.decode("utf-8", errors="ignore")
    clean_text = re.sub(r'<script.*?>.*?</script>', ' ', html_content, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r'<style.*?>.*?</style>', ' ', clean_text, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
    return " ".join(clean_text.split())[:snippet_length]


def summarize_hn_stories_batched(items_data):
    """Summarize multiple HN stories in a single batched Gemini call to preserve rate limits."""
    global client
    
    # Load config
    config = load_config("config.json")
    ai_config = config.get("ai", {})
    limits_config = config.get("limits", {})
    
    gemini_model = ai_config.get("model", "gemini-3.5-flash")
    hn_summary_prompt = get_config_value(ai_config, "prompts.hn_summarization",
        "For each story listed below, write a single concise summary sentence (10-20 words). Return ONLY a JSON array of strings corresponding to each story in order. Example: [\"Summary 1.\", \"Summary 2.\"]")
    
    snippet_length = limits_config.get("hn_snippet_length", 400)
    min_words = limits_config.get("hn_summary_min_words", 10)
    max_words = limits_config.get("hn_summary_max_words", 20)
    
    descriptions = []

    if client and items_data:
        stories_input = []
        for idx, item in enumerate(items_data, 1):
            snippet = item.get("snippet", "")
            title = item.get("title", "")
            stories_input.append(f"Story {idx}:\nTitle: {title}\nSnippet: {snippet[:snippet_length]}")

        prompt = hn_summary_prompt + "\n\n" + "\n\n".join(stories_input)

        try:
            time.sleep(1)
            response = client.models.generate_content(
                model=gemini_model,
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
    limits_config = config.get("limits", {})
    max_section_articles = limits_config.get("max_section_articles", 8)

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

    # Fetch all sections once, then deduplicate globally across sections.
    sections = config.get("sections", [])
    all_articles = fetch_all_feeds_globally(sections, max_per_feed=15)
    grouped_articles = ai_global_deduplicate_and_filter(all_articles, max_per_section=max_section_articles)

    for section in sections:
        sec_name = section.get("name", "General")
        filtered_articles = grouped_articles.get(sec_name, [])
        output_content["categories"][sec_name] = {
            "summary": "",
            "articles": filtered_articles[:max_section_articles]
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
