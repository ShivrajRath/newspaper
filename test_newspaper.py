import os
import json
import sys
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
             patch.object(builder_module, "fetch_word_of_day", return_value={}), \
             patch.object(builder_module, "fetch_daily_puzzle", return_value={}):
            builder_module.build_newspaper()

        with open("newspaper.json", "r", encoding="utf-8") as f:
            data = json.load(f)

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
             patch.object(builder_module, "fetch_market_data", return_value={}):
            builder_module.build_newspaper()

        with open("newspaper.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertLessEqual(len(data["categories"]["Tech"]["articles"]), 8)

    def test_newspaper_json_structure(self):
        build_newspaper()
        self.assertTrue(os.path.exists("newspaper.json"))
        with open("newspaper.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("generated_at", data)
        self.assertIn("categories", data)
        self.assertIn("market", data)
        self.assertIn("hacker_news", data)
        self.assertIn("quote", data)


if __name__ == "__main__":
    unittest.main()
