import os
import json
import logging
import re
import html
import ssl
import hashlib
import feedparser
import urllib.request
import urllib.parse
import difflib
import time
import random
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from constants import WMO_CODES, FALLBACK_WORDS

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WORDNIK_API_KEY = os.environ.get("WORDNIK_API_KEY")


class RateLimitTracker:
    """Track rate limits from actual API responses."""
    
    def __init__(self):
        self.model_limits = {}  # model -> {rpm_used, tpm_used, rpd_used, rpm_limit, tpm_limit, rpd_limit}
    
    def update_from_response(self, model, response):
        """Extract and store rate limit info from API response."""
        try:
            # Check for usage_metadata in response
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                if model not in self.model_limits:
                    self.model_limits[model] = {
                        'rpm_used': 0, 'tpm_used': 0, 'rpd_used': 0,
                        'rpm_limit': None, 'tpm_limit': None, 'rpd_limit': None
                    }
                
                # Update token usage
                if hasattr(usage, 'total_token_count'):
                    self.model_limits[model]['tpm_used'] += usage.total_token_count
                if hasattr(usage, 'prompt_token_count'):
                    self.model_limits[model]['tpm_used'] += usage.prompt_token_count
                if hasattr(usage, 'candidates_token_count'):
                    self.model_limits[model]['tpm_used'] += usage.candidates_token_count
                
                # Increment request count
                self.model_limits[model]['rpm_used'] += 1
                self.model_limits[model]['rpd_used'] += 1
                
                logging.info("Rate limit update for %s: RPM=%d, TPM=%d, RPD=%d", 
                           model, self.model_limits[model]['rpm_used'], 
                           self.model_limits[model]['tpm_used'],
                           self.model_limits[model]['rpd_used'])
        except Exception as e:
            logging.debug("Could not extract rate limit info: %s", e)
    
    def get_usage(self, model):
        """Get current usage for a model."""
        return self.model_limits.get(model, {})
    
    def is_near_limit(self, model, threshold=0.8):
        """Check if model is near its rate limit."""
        limits = self.model_limits.get(model, {})
        if not limits or limits.get('rpm_limit') is None:
            return False
        rpm_usage = limits.get('rpm_used', 0) / max(limits.get('rpm_limit', 1), 1)
        return rpm_usage >= threshold


# Global rate limit tracker
rate_limit_tracker = RateLimitTracker()


def initialize_ai_client():
    """Initialize and return the Gemini AI client, or None if unavailable."""
    try:
        if GEMINI_API_KEY:
            from google import genai
            return genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logging.warning("Gemini AI client initialization failed or key not set: %s", e)
    return None


def _handle_ai_error(e, operation_name, client_ref):
    """Handle AI API errors with consistent logging and client disabling."""
    err_str = str(e)
    if "404" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "NOT_FOUND" in err_str:
        logging.warning("Gemini AI API error (%s). Disabling AI.", e)
        client_ref[0] = None  # Disable client by reference
        return True  # AI disabled
    else:
        logging.warning("AI %s failed: %s.", operation_name, e)
        return False  # AI still available


def get_model_for_task(config, task_name, prefer_primary=True):
    """Get the appropriate model for a task (primary or secondary)."""
    ai_config = config.get("ai", {})
    models_config = ai_config.get("models", {})
    
    task_config = models_config.get(task_name, {})
    if prefer_primary:
        return task_config.get("primary", ai_config.get("model", "gemini-3.5-flash"))
    else:
        return task_config.get("secondary", ai_config.get("model", "gemini-3.5-flash"))


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


_SOURCE_LABELS = {
    "bbci.co.uk": "BBC",
    "aljazeera.com": "Al Jazeera",
    "nytimes.com": "NY Times",
    "cbsnews.com": "CBS News",
    "dw.com": "DW",
    "cnbc.com": "CNBC",
    "yahoo.com": "Yahoo Finance",
    "dj.com": "WSJ",
    "wsj.com": "WSJ",
    "wfaa.com": "WFAA",
    "google.com": "Google News",
    "phys.org": "Phys.org",
    "nature.com": "Nature",
    "arstechnica.com": "Ars Technica",
    "theverge.com": "The Verge",
    "sciencedaily.com": "ScienceDaily",
}


def _source_from_url(url):
    """Derive a short human-readable source label from a feed URL."""
    try:
        netloc = urllib.parse.urlsplit(url).netloc.lower()
        netloc = netloc.split(":")[0]
        for prefix in ("www.", "feeds.", "feed.", "rss."):
            if netloc.startswith(prefix):
                netloc = netloc[len(prefix):]
        for domain, label in _SOURCE_LABELS.items():
            if netloc == domain or netloc.endswith("." + domain):
                return label
        # Fallback: title-case the first domain label (e.g. "example.com" -> "Example").
        first = netloc.split(".")[0] if netloc else ""
        return first.replace("-", " ").title() if first else "News"
    except Exception:
        return "News"


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


def fetch_word_of_the_day(config=None, today=None):
    """Fetch Word of the Day deterministically from local word-of-the-day.json file.

    The same calendar date always yields the same word (hash of YYYY-MM-DD
    modulo list length), so rebuilding twice in one day doesn't change the
    paper. Falls back to constants.FALLBACK_WORDS, then a hardcoded entry.
    """
    if config:
        wod_config = config.get("word_of_day", {})
        if not wod_config.get("enabled", True):
            return None

    if today is None:
        date_str = datetime.now().date().isoformat()
    elif isinstance(today, datetime):
        date_str = today.date().isoformat()
    elif hasattr(today, "isoformat"):
        try:
            date_str = today.isoformat()[:10]
        except Exception:
            date_str = str(today)[:10]
    else:
        date_str = str(today)[:10]

    def _pick(words):
        if not words:
            return None
        digest = hashlib.sha256(date_str.encode("utf-8")).hexdigest()
        return words[int(digest, 16) % len(words)]

    # Load words from local JSON file
    try:
        with open("word-of-the-day.json", "r", encoding="utf-8") as f:
            words = json.load(f)

        if words and isinstance(words, list):
            selected_word = _pick(words)
            if selected_word:
                logging.info("Selected word of the day for %s: %s", date_str, selected_word.get("word", ""))
                return {
                    "word": selected_word.get("word", ""),
                    "part_of_speech": "",
                    "definition": selected_word.get("common_thought", ""),
                    "example": selected_word.get("practice_sentence", ""),
                    "source": "Local"
                }
    except Exception as e:
        logging.warning("Error loading word-of-the-day.json: %s", e)

    # Fallback to curated constants list (deterministic too)
    try:
        selected = _pick(FALLBACK_WORDS)
        if selected:
            return {
                "word": selected.get("word", ""),
                "part_of_speech": selected.get("part_of_speech", ""),
                "definition": selected.get("definition", ""),
                "example": selected.get("example", ""),
                "source": "Local"
            }
    except Exception as e:
        logging.warning("Error selecting fallback word: %s", e)

    # Ultimate fallback if everything fails
    return {
        "word": "serendipity",
        "part_of_speech": "noun",
        "definition": "The occurrence and development of events by chance in a happy or beneficial way.",
        "example": "Finding that rare book in a small thrift shop was pure serendipity.",
        "source": ""
    }


def fetch_weather(config, client_ref):
    """Fetch current weather for configured location using Open-Meteo (free, no key required) and generate AI description."""
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
            if client_ref[0]:
                # Try primary model first, then secondary
                for model_name in [get_model_for_task(config, "weather", prefer_primary=True), 
                                   get_model_for_task(config, "weather", prefer_primary=False)]:
                    try:
                        prompt = weather_prompt.format(data=raw_summary)
                        time.sleep(1)
                        response = client_ref[0].models.generate_content(
                            model=model_name,
                            contents=prompt
                        )
                        # Track rate limits from response
                        rate_limit_tracker.update_from_response(model_name, response)
                        ai_description = response.text.strip()
                        logging.info("AI weather description generated using %s: %s", model_name, ai_description[:50])
                        break
                    except Exception as e:
                        if _handle_ai_error(e, f"weather description ({model_name})", client_ref):
                            break  # AI disabled, don't try secondary
                        logging.warning("Primary model %s failed, trying secondary...", model_name)
                        continue
            
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




def _prepare_safe_url(url):
    """Prepare URL with proper query encoding and user agent."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.query:
        # Unquote first to decode any existing encoding, then re-quote with safe characters
        unquoted_query = urllib.parse.unquote(parsed.query)
        query = urllib.parse.quote(unquoted_query, safe=',=&|:+()/')
    else:
        query = ''
    safe_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))
    return urllib.request.Request(safe_url, headers={"User-Agent": "Mozilla/5.0"})


def safe_urlopen(url, timeout=15):
    """Safely open URL returning response handle. Raises ConnectionError if all attempts fail."""
    request = _prepare_safe_url(url)
    last_exc = None
    for ctx in (ssl.create_default_context(), ssl._create_unverified_context()):
        try:
            return urllib.request.urlopen(request, timeout=timeout, context=ctx)
        except Exception as exc:
            last_exc = exc
            continue
    raise ConnectionError(f"Failed to open URL {url}: {last_exc}")


def safe_fetch_url(url, timeout=15):
    """Safely fetch raw bytes from URL supporting SSL fallback."""
    try:
        with safe_urlopen(url, timeout=timeout) as response:
            return response.read()
    except ConnectionError:
        return None


def fetch_feed_entries(url, max_items, max_age_days, config):
    """Fetch recent feed entries from an RSS feed URL."""
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

    source_label = _source_from_url(url)
    articles = []
    for entry in feed.entries:
        if not entry_is_recent(entry):
            continue
        title_raw = entry.get("title", "Untitled")
        summary_raw = entry.get("summary", entry.get("description", ""))
        title = clean_html(title_raw).strip()
        summary = clean_html(summary_raw).strip()
        published_iso = ""
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed:
            try:
                published_iso = datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                published_iso = ""
        if title:  # Only add articles with valid titles
            articles.append({
                "title": title,
                "summary": summary,
                "link": entry.get("link", ""),
                "source": source_label,
                "published": published_iso
            })
            if len(articles) >= max_items:
                break
    return articles


def fetch_section_articles(feed_urls, max_per_feed, config):
    """Fetch articles across all feed URLs specified for a section."""
    limits_config = config.get("limits", {})
    max_age_days = limits_config.get("max_feed_age_days", 1)
    
    all_articles = []
    for url in feed_urls:
        entries = fetch_feed_entries(url, max_per_feed, max_age_days, config)
        all_articles.extend(entries)
    return all_articles


_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "when", "while",
    "of", "at", "by", "for", "with", "about", "into", "through", "during",
    "before", "after", "above", "below", "up", "down", "in", "out", "on",
    "off", "over", "under", "again", "further", "once", "here", "there",
    "all", "any", "both", "each", "few", "more", "most", "other", "some",
    "such", "only", "own", "same", "than", "too", "very", "can", "will",
    "just", "don", "should", "now", "from", "as", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "having", "do",
    "does", "did", "doing", "would", "could", "ought", "its", "it", "itself",
    "this", "that", "these", "those", "he", "she", "they", "them", "his",
    "her", "hers", "their", "theirs", "our", "ours", "your", "yours",
    "who", "whom", "which", "what", "where", "why", "how", "to", "s",
    "t", "says", "say", "said", "tells", "told", "after", "amid", "among",
    "over", "under", "with", "without", "within", "along", "across",
    "new", "first", "last", "one", "two", "amid", "over",
}


def _normalize_for_match(text):
    """Lowercase, strip possessives, remove punctuation for comparison."""
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r"['\u2019]s\b", "", t)
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _stem_token(tok):
    """Lightweight stem for dedup: map key event words to canonical forms."""
    if not tok:
        return tok
    if tok in ("dies", "died", "dying", "dead", "deaths", "death"):
        return "die"
    if tok in ("obituary", "obituaries", "obits"):
        return "die"
    if tok.startswith("execut"):
        return "execut"
    if tok.startswith("hurrican"):
        return "hurrican"
    if tok in ("storms", "stormy"):
        return "storm"
    if tok in ("lawyers", "lawyer"):
        return "lawyer"
    if tok in ("injections", "injection"):
        return "injection"
    # generic plural handling
    if len(tok) > 5 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 4 and tok.endswith("es"):
        # e.g. passes -> pass, crashes -> crash, but keep 'texas' intact
        if tok not in ("texas", "isaias"):
            return tok[:-2]
    if len(tok) > 4 and tok.endswith("s") and not tok.endswith("ss"):
        if tok not in ("texas", "isaias", "news"):
            return tok[:-1]
    return tok


def _significant_tokens(text):
    """Return (list, set) of stemmed significant tokens preserving order."""
    norm = _normalize_for_match(text)
    tokens = []
    for raw in norm.split():
        if len(raw) < 3:
            continue
        if raw in _STOPWORDS:
            continue
        stemmed = _stem_token(raw)
        if stemmed in _STOPWORDS:
            continue
        if len(stemmed) < 3:
            continue
        tokens.append(stemmed)
    return tokens, set(tokens)


def _significant_bigrams(ordered_tokens):
    """Return set of 'w1 w2' for consecutive significant tokens."""
    if len(ordered_tokens) < 2:
        return set()
    return {f"{ordered_tokens[i]} {ordered_tokens[i + 1]}" for i in range(len(ordered_tokens) - 1)}


def _event_flags(sig_set):
    """Return set of event clusters present: death / execution / storm."""
    flags = set()
    if "die" in sig_set or "obit" in sig_set:
        flags.add("death")
    if "execut" in sig_set or "lethal" in sig_set or "injection" in sig_set:
        flags.add("execution")
    if "hurrican" in sig_set or "storm" in sig_set or "tropical" in sig_set or "cyclon" in sig_set or "typhoon" in sig_set:
        flags.add("storm")
    return flags


def _build_doc_freq(articles):
    """Count in how many article titles each significant token appears."""
    from collections import Counter
    freq = Counter()
    for art in articles:
        _, sig_set = _significant_tokens(art.get("title", ""))
        for tok in sig_set:
            freq[tok] += 1
    return freq


def _is_rare(tok, doc_freq, total_docs, max_df=3):
    """A token is distinctive if short-list rare across the batch."""
    if len(tok) < 5:
        return False
    if doc_freq is None or total_docs is None:
        return len(tok) >= 6
    return doc_freq.get(tok, 1) <= max_df


def _summary_word_overlap(s1, s2):
    """Word overlap ratio on summaries using significant tokens."""
    _, set1 = _significant_tokens(s1 or "")
    _, set2 = _significant_tokens(s2 or "")
    if not set1 or not set2:
        return 0.0
    return len(set1.intersection(set2)) / max(len(set1), len(set2))


def _are_near_duplicates(art1, art2, similarity_threshold=0.65, word_overlap_threshold=0.7,
                         doc_freq=None, total_docs=None):
    """Return True if two articles cover the same story.

    Combines the legacy checks (sequence ratio, raw word overlap) with
    entity-aware checks that catch same-person/same-event rewrites with
    very different wording, e.g.:
      - 'Margaret Hamilton, whose software helped land Apollo 11 ... dies'
        vs 'Margaret Hamilton, scientist who worked on NASA Apollo ... dead'
      - 'Texas carries out first US execution since Christa Pike's ...'
        vs 'Texas executes man after lawyers sought to stop ... citing Pike'
      - 'Isaias becomes first hurricane of 2026 ...'
        vs 'Tropical Storm Isaias forms in Gulf ...'
    """
    link1 = (art1.get("link") or art1.get("url") or "").strip()
    link2 = (art2.get("link") or art2.get("url") or "").strip()
    if link1 and link1 == link2:
        return True

    t1 = (art1.get("title") or "").strip()
    t2 = (art2.get("title") or "").strip()
    if not t1 or not t2:
        return False

    n1 = _normalize_for_match(t1)
    n2 = _normalize_for_match(t2)
    if n1 == n2:
        return True

    # 1) legacy sequence similarity on full normalized titles, guarded
    # against short-template false positives (e.g. 'Alpha Story' vs
    # 'Gamma Story' ratio 0.73, or 'Story 0' vs 'Story 1' ratio 0.86).
    # High ratio alone only counts when there is additional shared content.
    try:
        seq_ratio = difflib.SequenceMatcher(None, n1, n2).ratio()
        if seq_ratio > similarity_threshold:
            # Compute significant overlap early for the guard.
            _l1, _s1 = _significant_tokens(t1)
            _l2, _s2 = _significant_tokens(t2)
            _shared_early = _s1.intersection(_s2) if _s1 and _s2 else set()
            _raw_overlap_early = 0.0
            _w1e = set(n1.split())
            _w2e = set(n2.split())
            if _w1e and _w2e:
                _raw_overlap_early = len(_w1e.intersection(_w2e)) / max(len(_w1e), len(_w2e))
            is_long = max(len(n1), len(n2)) > 40 or max(len(_w1e), len(_w2e)) > 5
            if is_long or len(_shared_early) >= 2 or _raw_overlap_early > 0.5 or seq_ratio > 0.9:
                return True
            # else: fall through to entity-aware checks below
    except Exception:
        pass

    # 2) legacy raw word overlap (all words, matches historic behaviour)
    w1 = set(n1.split())
    w2 = set(n2.split())
    if w1 and w2:
        if len(w1.intersection(w2)) / max(len(w1), len(w2)) > word_overlap_threshold:
            return True

    # Significant-token views (stopwords removed, stemmed)
    list1, set1 = _significant_tokens(t1)
    list2, set2 = _significant_tokens(t2)
    if not set1 or not set2:
        return False
    shared = set1.intersection(set2)

    # 3) three or more shared content words -> same story even if
    #    wording/order differs (covers Pike x3, Hamilton x2, Isaias x2).
    if len(shared) >= 3:
        return True

    big1 = _significant_bigrams(list1)
    big2 = _significant_bigrams(list2)
    shared_bigrams = big1.intersection(big2) if big1 and big2 else set()

    flags1 = _event_flags(set1)
    flags2 = _event_flags(set2)
    shared_flags = flags1.intersection(flags2)

    s1 = art1.get("summary") or art1.get("description") or ""
    s2 = art2.get("summary") or art2.get("description") or ""
    summ_overlap = _summary_word_overlap(s1, s2)

    # Also consider title+summary tokens for entity continuity
    _, sum_set1 = _significant_tokens(s1)
    _, sum_set2 = _significant_tokens(s2)

    # 4) shared person-name-style bigram (e.g. 'margaret hamilton',
    #    'christa pike', 'jamaal howard') plus same event or extra overlap.
    if shared_bigrams:
        if shared_flags:
            return True
        if len(shared) >= 2:
            return True
        if summ_overlap > 0.25:
            return True
        # title entity + summary entity continuity (e.g. Pike in title,
        # Howard in both summaries)
        if sum_set1 and sum_set2 and len(sum_set1.intersection(sum_set2)) >= 2:
            title_entities = set1.union(set2)
            if len(title_entities.intersection(sum_set1.union(sum_set2))) >= 1 and len(sum_set1.intersection(sum_set2)) >= 2:
                return True

    # 5) two shared content words where at least one is rare/distinctive,
    #    or both share the same event type (death/execution/storm).
    if len(shared) >= 2:
        rare_shared = [w for w in shared if _is_rare(w, doc_freq, total_docs)]
        if rare_shared:
            return True
        if shared_flags:
            return True
        if summ_overlap > 0.3:
            return True

    # 6) single rare entity (e.g. 'isaias') + same event cluster or
    #    strong summary overlap -> same story despite paraphrased titles.
    if len(shared) >= 1:
        rare_shared = [w for w in shared if _is_rare(w, doc_freq, total_docs)]
        if rare_shared and (shared_flags or summ_overlap > 0.3):
            return True
        # summary carries the entity: title has 'pike', summaries share 'howard'
        if rare_shared and sum_set1 and sum_set2:
            if len(sum_set1.intersection(sum_set2)) >= 2:
                return True

    # 7) summaries strongly overlap and titles share an entity.
    if summ_overlap > 0.5 and len(shared) >= 1:
        return True

    return False


def deterministic_global_deduplicate(grouped_articles, section_order, config):
    """Double-check pass: guarantee no near-duplicates survive across sections.

    Keeps the first occurrence in `section_order` priority and drops later
    copies, regardless of whether the AI pass missed them. Also catches
    within-section duplicates the per-section pass may have missed.
    """
    limits_config = config.get("limits", {}) if isinstance(config, dict) else {}
    sim_threshold = limits_config.get("deduplication_similarity_threshold", 0.65)
    overlap_threshold = limits_config.get("word_overlap_threshold", 0.7)

    if not grouped_articles:
        return {}

    order = list(section_order) if section_order else list(grouped_articles.keys())
    for sec in grouped_articles.keys():
        if sec not in order:
            order.append(sec)

    all_kept = []
    for sec in order:
        all_kept.extend(grouped_articles.get(sec, []) or [])
    doc_freq = _build_doc_freq(all_kept)
    total = len(all_kept)

    seen = []
    result = {sec: [] for sec in order}
    for sec in order:
        for art in (grouped_articles.get(sec, []) or []):
            duplicate_of = None
            for prev_art, prev_sec in seen:
                if _are_near_duplicates(art, prev_art, sim_threshold, overlap_threshold, doc_freq, total):
                    duplicate_of = (prev_art, prev_sec)
                    break
            if duplicate_of is not None:
                logging.info(
                    "Deterministic dedup: dropping '%s' (%s) as duplicate of '%s' (%s)",
                    (art.get("title") or "")[:90], sec,
                    (duplicate_of[0].get("title") or "")[:90], duplicate_of[1],
                )
                continue
            seen.append((art, sec))
            result[sec].append(art)
    return result


def deduplicate_hacker_news_list(hacker_news, config):
    """Remove internal near-duplicates within the Hacker News list."""
    if not hacker_news:
        return []
    limits_config = config.get("limits", {}) if isinstance(config, dict) else {}
    sim_threshold = limits_config.get("deduplication_similarity_threshold", 0.65)
    overlap_threshold = limits_config.get("word_overlap_threshold", 0.7)
    doc_freq = _build_doc_freq([{"title": hn.get("title", "")} for hn in hacker_news])
    total = len(hacker_news)
    unique = []
    for hn in hacker_news:
        if not hn.get("title", "").strip():
            continue
        is_dup = any(
            _are_near_duplicates(
                {"title": hn.get("title", ""), "link": hn.get("url", "")},
                {"title": kept.get("title", ""), "link": kept.get("url", "")},
                sim_threshold, overlap_threshold, doc_freq, total,
            )
            for kept in unique
        )
        if is_dup:
            logging.info("HN dedup: dropping duplicate HN story '%s'", (hn.get("title") or "")[:90])
            continue
        unique.append(hn)
    return unique


def local_deduplicate_articles(articles, max_items, config):
    """Filter duplicate or near-duplicate articles using title+summary similarity."""
    if not articles:
        return []

    limits_config = config.get("limits", {}) if isinstance(config, dict) else {}
    similarity_threshold = limits_config.get("deduplication_similarity_threshold", 0.65)
    word_overlap_threshold = limits_config.get("word_overlap_threshold", 0.7)

    doc_freq = _build_doc_freq(articles)
    total = len(articles)

    unique_articles = []

    for art in articles:
        title = (art.get("title") or "").strip()
        if not title:
            continue

        is_duplicate = any(
            _are_near_duplicates(art, kept, similarity_threshold, word_overlap_threshold, doc_freq, total)
            for kept in unique_articles
        )

        if not is_duplicate:
            unique_articles.append(art)

        if len(unique_articles) >= max_items:
            break

    return unique_articles[:max_items]


def fetch_all_feeds_globally(sections, max_per_feed, config):
    """Fetch all RSS articles from every section once and tag each item with its section."""
    limits_config = config.get("limits", {})
    
    if max_per_feed == 15:  # Use default if not explicitly provided
        max_per_feed = limits_config.get("max_per_feed", 15)
    
    all_articles = []
    for section in sections:
        sec_name = section.get("name", "General")
        feed_urls = section.get("feeds", [])
        if not feed_urls:
            continue
        raw_articles = fetch_section_articles(feed_urls, max_per_feed=max_per_feed, config=config)
        for article in raw_articles:
            tagged_article = dict(article)
            tagged_article["section"] = sec_name
            all_articles.append(tagged_article)
    return all_articles


def _local_group_articles_by_section(all_articles, max_per_section, config):
    """Group by section with within-section dedup plus deterministic cross-section dedup."""
    limits_config = config.get("limits", {}) if isinstance(config, dict) else {}
    
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
        grouped_articles[sec_name] = local_deduplicate_articles(grouped_articles[sec_name], max_items=max_per_section, config=config)

    # Double-check: remove any remaining cross-section near-duplicates so the
    # same story never appears in two sections (or twice in one section).
    grouped_articles = deterministic_global_deduplicate(grouped_articles, section_order, config)

    return grouped_articles


def ai_global_deduplicate_and_filter(all_articles, max_per_section, config, client_ref):
    """Use a single AI call to deduplicate across sections and filter insignificant stories.

    The AI pass is followed by a mandatory deterministic double-check
    (`deterministic_global_deduplicate`) so missed near-duplicates are still
    eliminated even when the model is unavailable or returns weak results.
    """
    ai_config = config.get("ai", {}) if isinstance(config, dict) else {}
    limits_config = config.get("limits", {}) if isinstance(config, dict) else {}
    
    filtering_prompt = get_config_value(ai_config, "prompts.article_filtering",
        "Filter out low-value stories that are insignificant or not broadly relevant to readers, including gore, graphic violence, isolated crime, single-casualty incidents, routine police blotter items, celebrity gossip, and other clickbait. Exclude routine local crime stories such as 'Police investigate after man found dead in parking lot', 'Body found in [location]', 'Shooting investigation underway', or similar isolated incidents without broader impact. Do not include stories about a person being found dead, killed, injured, or arrested without a broader impact, unless the event is a major escalation, public safety crisis, mass casualty event, natural disaster, or major policy/geopolitical development. Keep significant and timely stories including major escalations, natural disasters, major accidents, notable scientific breakthroughs, and major policy or geopolitical developments.")
    
    if max_per_section == 15:  # Use default if not explicitly provided
        max_per_section = limits_config.get("max_section_articles", 8)

    if not all_articles:
        return {}

    section_names = []
    for article in all_articles:
        sec_name = article.get("section", "General")
        if sec_name not in section_names:
            section_names.append(sec_name)

    if not client_ref[0]:
        return _local_group_articles_by_section(all_articles, max_per_section, config)

    formatted_list = []
    for idx, article in enumerate(all_articles, 1):
        sec_name = article.get("section", "General")
        title = (article.get("title") or "Untitled").strip()
        summary = (article.get("summary") or "").strip()
        # Include a short summary so the model can link paraphrased titles
        # about the same event (e.g. different wordings of one death).
        snippet = f" — {summary[:200]}" if summary else ""
        formatted_list.append(f"[{idx}] {title}{snippet} ({sec_name})")

    # Combine deduplication instructions with user's filtering prompt
    dedup_instruction = (
        "You are selecting the most important and relevant news stories for a daily newspaper. "
        "Review all article titles (with summary hints) below, then return a JSON object mapping each section name to a list of article indices to keep. "
        "DEDUPLICATION IS MANDATORY: the same story must appear at most ONCE in the whole newspaper. "
        "Treat as duplicates and keep only the single best version when articles share the same person and event even if worded very differently, for example: "
        "'Christa Pike now walking after failed execution' vs 'Texas carries out execution since Christa Pike botched injections' vs 'Texas executes man, lawyers cited Christa Pike' (all one execution-fallout story); "
        "'Margaret Hamilton, whose software helped land Apollo 11, dies at 90' vs 'Margaret Hamilton, scientist who worked on NASA Apollo program, dead at 90' (one obituary); "
        "'Isaias becomes first hurricane of 2026' vs 'Tropical Storm Isaias forms in Gulf, could reach US as hurricane' (one storm). "
        "Also merge same-storm, same-obituary, same-execution, and same-major-event rewrites from different outlets or sections. "
        "Never keep two indices whose titles/summaries describe the same who+what, even across different sections. "
    )
    prompt = dedup_instruction + filtering_prompt + " Return ONLY valid JSON with this shape: {\"Section Name\": [1, 3, 5]}." + f"\n\nTitles:\n" + "\n".join(formatted_list)

    # Try primary model first, then secondary
    for model_name in [get_model_for_task(config, "article_filtering", prefer_primary=True), 
                       get_model_for_task(config, "article_filtering", prefer_primary=False)]:
        try:
            time.sleep(1)
            response = client_ref[0].models.generate_content(
                model=model_name,
                contents=prompt
            )
            # Track rate limits from response
            rate_limit_tracker.update_from_response(model_name, response)
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

            for sec_name in section_names:
                grouped_articles.setdefault(sec_name, [])

            logging.info("AI global deduplication selected stories across %d articles using %s", len(all_articles), model_name)
            # Double-check: deterministic pass guarantees no cross-section
            # duplicates survive even if the model missed paraphrased rewrites.
            grouped_articles = deterministic_global_deduplicate(grouped_articles, section_names, config)
            return grouped_articles
        except Exception as e:
            if _handle_ai_error(e, f"global deduplication ({model_name})", client_ref):
                break  # AI disabled, don't try secondary
            logging.warning("Primary model %s failed, trying secondary...", model_name)
            continue
    
    # If both models failed, fall back to local deduplication
    return _local_group_articles_by_section(all_articles, max_per_section, config)


def fetch_riddle():
    """Fetch a random riddle from the Riddles API."""
    categories = ['funny', 'science', 'logic']
    random_category = random.choice(categories)
    
    try:
        url = f"https://riddles-api-eight.vercel.app/{random_category}"
        with safe_urlopen(url, timeout=15) as req:
            data = json.loads(req.read().decode())
            
            if data and data.get("riddle") and data.get("answer"):
                logging.info("Successfully fetched riddle from category: %s", random_category)
                return {
                    "question": data.get("riddle"),
                    "answer": data.get("answer"),
                    "category": random_category
                }
    except Exception as e:
        logging.warning("Error fetching riddle: %s", e)

    # Fallback riddles if API fails
    fallback_riddles = [
        {"question": "What has keys but can't open locks?", "answer": "A piano", "category": "fallback"},
        {"question": "What can travel around the world while staying in a corner?", "answer": "A stamp", "category": "fallback"},
        {"question": "What gets wetter the more it dries?", "answer": "A towel", "category": "fallback"},
        {"question": "What can you catch but not throw?", "answer": "A cold", "category": "fallback"},
        {"question": "What has hands but can't clap?", "answer": "A clock", "category": "fallback"}
    ]
    
    return random.choice(fallback_riddles)


def fetch_joke():
    """Fetch a safe kid-friendly pun joke from JokeAPI."""
    try:
        url = "https://v2.jokeapi.dev/joke/pun?safe-mode"
        with safe_urlopen(url, timeout=15) as req:
            data = json.loads(req.read().decode())
            
            if data and data.get("type") == "single":
                logging.info("Successfully fetched single-part joke")
                return {
                    "type": "single",
                    "content": data.get("joke", ""),
                    "category": data.get("category", "pun")
                }
            elif data and data.get("type") == "twopart":
                logging.info("Successfully fetched two-part joke")
                return {
                    "type": "twopart",
                    "setup": data.get("setup", ""),
                    "delivery": data.get("delivery", ""),
                    "category": data.get("category", "pun")
                }
    except Exception as e:
        logging.warning("Error fetching joke: %s", e)

    # Fallback kid-safe pun jokes if API fails
    fallback_jokes = [
        {"type": "single", "content": "Why don't scientists trust atoms? Because they make up everything!", "category": "fallback"},
        {"type": "single", "content": "What do you call a fake noodle? An impasta!", "category": "fallback"},
        {"type": "single", "content": "Why did the scarecrow win an award? Because he was outstanding in his field!", "category": "fallback"},
        {"type": "twopart", "setup": "What do you call a bear with no teeth?", "delivery": "A gummy bear!", "category": "fallback"},
        {"type": "twopart", "setup": "Why don't eggs tell jokes?", "delivery": "They'd crack each other up!", "category": "fallback"},
        {"type": "single", "content": "What do you call a dinosaur that crashes their car? Tyrannosaurus Wrecks!", "category": "fallback"},
        {"type": "twopart", "setup": "What do you call a fish without eyes?", "delivery": "A fsh!", "category": "fallback"}
    ]
    
    return random.choice(fallback_jokes)


def fetch_hacker_news(hn_config):
    """Fetch Hacker News top stories using configuration settings."""
    if not hn_config.get("enabled", True):
        return []

    max_items = hn_config.get("max_items", 5)
    min_score = hn_config.get("min_score", 0)
    try:
        with safe_urlopen("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=15) as req:
            top_ids = json.loads(req.read().decode())[:max_items]

        hacker_news = []
        for item_id in top_ids:
            with safe_urlopen(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json", timeout=15) as item_req:
                data = json.loads(item_req.read().decode())
                article_url = data.get("url", f"https://news.ycombinator.com/item?id={item_id}")
                score = data.get("score", 0)
                if score >= min_score:
                    hacker_news.append({
                        "title": data.get("title", "Untitled story"),
                        "url": article_url,
                        "score": score
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
            if not quote_html:
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


def build_newspaper(output_path="newspaper.json", config_path="config.json"):
    """Main function to load configuration, fetch data, deduplicate, and write newspaper.json."""
    config = load_config(config_path)
    limits_config = config.get("limits", {})
    max_section_articles = limits_config.get("max_section_articles", 8)

    # Initialize AI client as a mutable reference
    client_ref = [initialize_ai_client()]

    now_utc = datetime.now(timezone.utc)
    output_content = {
        "generated_at": now_utc.astimezone().strftime("%B %d, %Y %I:%M %p"),
        "generated_at_iso": now_utc.isoformat(),
        "quote": fetch_quote_of_day(),
        "word_of_day": fetch_word_of_the_day(config),
        "weather": fetch_weather(config, client_ref),
        "riddle": fetch_riddle(),
        "joke": fetch_joke(),
        "categories": {},
        "market": {},
        "hacker_news": []
    }

    # Fetch all sections once, then deduplicate globally across sections.
    sections = config.get("sections", [])
    all_articles = fetch_all_feeds_globally(sections, 15, config)
    grouped_articles = ai_global_deduplicate_and_filter(all_articles, max_section_articles, config, client_ref)

    for section in sections:
        sec_name = section.get("name", "General")
        filtered_articles = grouped_articles.get(sec_name, [])
        output_content["categories"][sec_name] = {
            "articles": filtered_articles[:max_section_articles]
        }

    # Fetch Hacker News
    raw_hn = fetch_hacker_news(config.get("hacker_news", {}))
    # Double-check within HN so the same story never appears twice there.
    # HN is intentionally kept independent of RSS categories (different source
    # card), so we do not drop HN items merely for overlapping a category.
    output_content["hacker_news"] = deduplicate_hacker_news_list(raw_hn, config)

    # Fetch Market Data
    output_content["market"] = fetch_market_data(config.get("market", {}))

    # Save to newspaper.json
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_content, f, indent=2, ensure_ascii=False)

    logging.info("Successfully generated %s with %d sections.", output_path, len(output_content["categories"]))
    
    # Log rate limit usage from actual API responses
    if rate_limit_tracker.model_limits:
        logging.info("=== Rate Limit Usage (from API responses) ===")
        for model, usage in rate_limit_tracker.model_limits.items():
            logging.info("Model: %s", model)
            logging.info("  Requests (RPM): %d", usage.get('rpm_used', 0))
            logging.info("  Tokens (TPM): %d", usage.get('tpm_used', 0))
            logging.info("  Requests today (RPD): %d", usage.get('rpd_used', 0))
            if usage.get('rpm_limit'):
                logging.info("  RPM Limit: %d (%.1f%% used)", usage['rpm_limit'], 
                           usage.get('rpm_used', 0) / max(usage['rpm_limit'], 1) * 100)
            if usage.get('tpm_limit'):
                logging.info("  TPM Limit: %d (%.1f%% used)", usage['tpm_limit'], 
                           usage.get('tpm_used', 0) / max(usage['tpm_limit'], 1) * 100)
            if usage.get('rpd_limit'):
                logging.info("  RPD Limit: %d (%.1f%% used)", usage['rpd_limit'], 
                           usage.get('rpd_used', 0) / max(usage['rpd_limit'], 1) * 100)

    return output_content


if __name__ == "__main__":
    build_newspaper()
