import os
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
import build_newspaper as builder_module
from build_newspaper import (
    load_config,
    clean_html,
    local_deduplicate_articles,
    ai_global_deduplicate_and_filter,
    build_newspaper,
    fetch_market_data,
)


class TestNewspaperBuilder(unittest.TestCase):

    def test_load_config_custom(self):
        test_config_path = "test_temp_config.json"
        custom_data = {
            "sections": [
                {"name": "Custom Test Section", "feeds": ["http://example.com/rss.xml"]}
            ]
        }
        with open(test_config_path, "w", encoding="utf-8") as f:
            json.dump(custom_data, f)

        try:
            config = load_config(test_config_path)
            self.assertEqual(config["sections"][0]["name"], "Custom Test Section")
        finally:
            if os.path.exists(test_config_path):
                os.remove(test_config_path)

    def test_clean_html(self):
        raw_text = '<a href="https://example.com">Breaking News</a> &amp; <b>Updates</b>'
        cleaned = clean_html(raw_text)
        self.assertEqual(cleaned, "Breaking News & Updates")

    def test_local_deduplicate_articles(self):
        articles = [
            {"title": "Global Market Rallies After Earnings", "summary": "Markets go up today.", "link": "http://a.com"},
            {"title": "Global Market Rallies After Earnings!", "summary": "Markets surged today.", "link": "http://b.com"},
            {"title": "New Tech Innovations Unveiled", "summary": "Tech event today.", "link": "http://c.com"}
        ]
        deduped = local_deduplicate_articles(articles, 4, {})
        self.assertEqual(len(deduped), 2)
        titles = [a["title"] for a in deduped]
        self.assertIn("New Tech Innovations Unveiled", titles)

    def test_ai_global_deduplicate_and_filter(self):
        articles = [
            {"title": "World leaders meet over rising tensions", "summary": "Major escalation.", "link": "http://a.com", "section": "World"},
            {"title": "World leaders meet over rising tensions", "summary": "Same story.", "link": "http://b.com", "section": "India"},
            {"title": "Local man killed in dispute", "summary": "Minor crime.", "link": "http://c.com", "section": "World"},
            {"title": "Major earthquake devastates coastal city", "summary": "Natural disaster.", "link": "http://d.com", "section": "India"},
        ]

        class FakeResponse:
            text = '{"World": [1, 4], "India": [4]}'

        class FakeClient:
            class Models:
                @staticmethod
                def generate_content(*args, **kwargs):
                    return FakeResponse()

            models = Models()

        client_ref = [FakeClient()]
        grouped = ai_global_deduplicate_and_filter(articles, 2, {"ai": {"prompts": {"article_filtering": ""}}}, client_ref)

        self.assertEqual(list(grouped.keys()), ["World", "India"])
        self.assertEqual([a["title"] for a in grouped["World"]], ["World leaders meet over rising tensions"])
        self.assertEqual([a["title"] for a in grouped["India"]], ["Major earthquake devastates coastal city"])

    def test_fetch_hacker_news_respects_min_score(self):
        class FakeResponse:
            def __init__(self, data):
                self._data = data

            def read(self):
                return json.dumps(self._data).encode()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        top_stories = [101, 102, 103]
        item_101 = {"id": 101, "title": "High Score Story", "url": "https://example.com/101", "score": 120}
        item_102 = {"id": 102, "title": "Low Score Story", "url": "https://example.com/102", "score": 80}
        item_103 = {"id": 103, "title": "Borderline Story", "url": "https://example.com/103", "score": 100}

        responses = [
            FakeResponse(top_stories),
            FakeResponse(item_101),
            FakeResponse(item_102),
            FakeResponse(item_103),
        ]

        with patch.object(builder_module, "safe_urlopen", side_effect=responses):
            hacker_news = builder_module.fetch_hacker_news({"enabled": True, "max_items": 3, "min_score": 100})

        self.assertEqual(len(hacker_news), 2)
        titles = [item["title"] for item in hacker_news]
        self.assertIn("High Score Story", titles)
        self.assertIn("Borderline Story", titles)
        self.assertNotIn("Low Score Story", titles)

    def test_fetch_market_data_falls_back_to_google_finance(self):
        html_payload = """
        <html><body>
            <div class="YMlKec fxKbKc">123.45</div>
            <div class="P6K39c">+1.23%</div>
        </body></html>
        """

        with patch.dict(sys.modules, {"yfinance": None}), \
             patch.object(builder_module, "safe_fetch_url", return_value=html_payload.encode("utf-8")):
            market_data = fetch_market_data({"enabled": True, "tickers": [{"symbol": "AAPL", "label": "Apple"}]})

        self.assertEqual(market_data["Apple"], "$123.45 (+1.23%)")

    def test_build_newspaper_uses_ai_dedup_for_single_feed(self):
        articles = [
            {"title": "Alpha Story", "summary": "Alpha", "link": "http://a.com"},
            {"title": "Beta Story", "summary": "Beta", "link": "http://b.com"},
            {"title": "Gamma Story", "summary": "Gamma", "link": "http://c.com"},
        ]

        class FakeResponse:
            text = "[1, 3]"

        class FakeClient:
            class Models:
                @staticmethod
                def generate_content(*args, **kwargs):
                    return FakeResponse()

            models = Models()

        config = {
            "sections": [{"name": "Tech", "feeds": ["http://example.com/rss.xml"]}],
            "hacker_news": {"enabled": False},
            "market": {"enabled": False},
        }

        with patch.object(builder_module, "load_config", return_value=config), \
             patch.object(builder_module, "fetch_section_articles", return_value=articles), \
             patch.object(builder_module, "fetch_quote_of_day", return_value={"text": "", "author": ""}), \
             patch.object(builder_module, "fetch_hacker_news", return_value=[]), \
             patch.object(builder_module, "fetch_market_data", return_value={}), \
             patch.object(builder_module, "initialize_ai_client", return_value=FakeClient()), \
             patch.object(builder_module, "fetch_weather", return_value={}), \
             patch.object(builder_module, "fetch_riddle", return_value={}), \
             patch.object(builder_module, "fetch_joke", return_value=None), \
             patch.object(builder_module, "fetch_word_of_the_day", return_value=None):
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                builder_module.build_newspaper(output_path=tmp_path)
                with open(tmp_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        selected_titles = [article["title"] for article in data["categories"]["Tech"]["articles"]]
        self.assertEqual(selected_titles, ["Alpha Story", "Gamma Story"])

    def test_build_newspaper_limits_section_articles_to_eight(self):
        articles = [
            {"title": f"Story {i}", "summary": "Summary", "link": f"http://example.com/{i}"}
            for i in range(10)
        ]

        config = {
            "sections": [{"name": "Tech", "feeds": ["http://example.com/rss.xml"]}],
            "hacker_news": {"enabled": False},
            "market": {"enabled": False},
        }

        with patch.object(builder_module, "load_config", return_value=config), \
             patch.object(builder_module, "fetch_section_articles", return_value=articles), \
             patch.object(builder_module, "fetch_quote_of_day", return_value={"text": "", "author": ""}), \
             patch.object(builder_module, "fetch_hacker_news", return_value=[]), \
             patch.object(builder_module, "fetch_market_data", return_value={}), \
             patch.object(builder_module, "fetch_weather", return_value={}), \
             patch.object(builder_module, "fetch_riddle", return_value={}), \
             patch.object(builder_module, "fetch_joke", return_value=None), \
             patch.object(builder_module, "fetch_word_of_the_day", return_value=None):
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                builder_module.build_newspaper(output_path=tmp_path)
                with open(tmp_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        self.assertLessEqual(len(data["categories"]["Tech"]["articles"]), 8)

    def test_newspaper_json_structure(self):
        config = {
            "sections": [{"name": "Tech", "feeds": ["http://example.com/rss.xml"]}],
            "hacker_news": {"enabled": False},
            "market": {"enabled": False},
        }
        with patch.object(builder_module, "load_config", return_value=config), \
             patch.object(builder_module, "fetch_section_articles", return_value=[
                 {"title": "T", "summary": "S", "link": "http://example.com/1"}
             ]), \
             patch.object(builder_module, "fetch_quote_of_day", return_value={"text": "Q", "author": "A"}), \
             patch.object(builder_module, "fetch_hacker_news", return_value=[]), \
             patch.object(builder_module, "fetch_market_data", return_value={}), \
             patch.object(builder_module, "fetch_weather", return_value={"location": "Testville", "description": "Sunny"}), \
             patch.object(builder_module, "fetch_riddle", return_value={}), \
             patch.object(builder_module, "fetch_joke", return_value=None), \
             patch.object(builder_module, "fetch_word_of_the_day", return_value={"word": "test"}):
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                data = builder_module.build_newspaper(output_path=tmp_path)
                self.assertTrue(os.path.exists(tmp_path))
                with open(tmp_path, "r", encoding="utf-8") as f:
                    on_disk = json.load(f)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        self.assertIn("generated_at", data)
        self.assertIn("generated_at_iso", data)
        self.assertIn("categories", data)
        self.assertIn("market", data)
        self.assertIn("hacker_news", data)
        self.assertIn("quote", data)
        self.assertIn("word_of_day", data)
        self.assertEqual(data, on_disk)

    def test_fallback_words_count_and_structure(self):
        from constants import FALLBACK_WORDS
        self.assertEqual(len(FALLBACK_WORDS), 100)
        for item in FALLBACK_WORDS:
            self.assertIn("word", item)
            self.assertIn("part_of_speech", item)
            self.assertIn("definition", item)
            self.assertIn("example", item)
            self.assertTrue(bool(item["word"].strip()))
            self.assertTrue(bool(item["definition"].strip()))

    def test_fetch_word_of_the_day_deterministic(self):
        from datetime import date
        r1 = builder_module.fetch_word_of_the_day({"word_of_day": {"enabled": True}}, today=date(2026, 1, 15))
        r2 = builder_module.fetch_word_of_the_day({"word_of_day": {"enabled": True}}, today=date(2026, 1, 15))
        self.assertIsNotNone(r1)
        self.assertEqual(r1, r2)
        self.assertTrue(bool(r1["word"]))
        self.assertTrue(bool(r1["definition"]))
        self.assertIn("source", r1)

    def test_fetch_word_of_the_day_disabled(self):
        result = builder_module.fetch_word_of_the_day({"word_of_day": {"enabled": False}})
        self.assertIsNone(result)

    def test_source_from_url_labels(self):
        self.assertEqual(builder_module._source_from_url("http://feeds.bbci.co.uk/news/world/rss.xml"), "BBC")
        self.assertEqual(builder_module._source_from_url("https://www.aljazeera.com/xml/rss/all.xml"), "Al Jazeera")
        self.assertEqual(builder_module._source_from_url("https://feeds.arstechnica.com/arstechnica/index"), "Ars Technica")
        self.assertTrue(bool(builder_module._source_from_url("https://example.com/rss.xml")))

    def test_fetch_feed_entries_adds_source_and_published(self):
        class FakeFeed:
            feed = {"title": "Example"}
            entries = [{
                "title": "Hello",
                "summary": "World",
                "link": "https://example.com/1",
                "published_parsed": (2026, 10, 8, 6, 0, 0, 0, 0, 0),
            }]
            bozo = False
            bozo_exception = None
        with patch.object(builder_module, "safe_fetch_url", return_value=b"<rss/>"), \
             patch("feedparser.parse", return_value=FakeFeed()):
            articles = builder_module.fetch_feed_entries("https://example.com/rss.xml", 15, 30, {})
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["source"], "Example")
        self.assertTrue(bool(articles[0]["source"]))
        self.assertIn("published", articles[0])
        self.assertTrue(articles[0]["published"].startswith("2026-10-08"))


if __name__ == "__main__":
    unittest.main()
