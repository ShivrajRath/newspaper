import os
import json
import unittest
from build_newspaper import (
    load_config,
    clean_html,
    local_deduplicate_articles,
    ai_deduplicate_articles,
    summarize_hn_stories_batched,
    build_newspaper,
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
        deduped = local_deduplicate_articles(articles, max_items=4)
        self.assertEqual(len(deduped), 2)
        titles = [a["title"] for a in deduped]
        self.assertIn("New Tech Innovations Unveiled", titles)

    def test_ai_deduplicate_fallback(self):
        articles = [
            {"title": "Local Sports Win Championship", "summary": "Team wins.", "link": "http://a.com"},
            {"title": "Local Sports Win Championship!", "summary": "Team victorious.", "link": "http://b.com"}
        ]
        # Should fallback gracefully if Gemini is not configured or in test env
        deduped = ai_deduplicate_articles(articles, "Sports", max_items=4)
        self.assertEqual(len(deduped), 1)

    def test_summarize_hn_stories_batched_fallback(self):
        items = [
            {"title": "Show HN: My New App", "snippet": "This is a great new app built with Python. It automates tasks."},
            {"title": "Ask HN: Favorite Books?", "snippet": ""}
        ]
        summaries = summarize_hn_stories_batched(items)
        self.assertEqual(len(summaries), 2)
        self.assertTrue(summaries[0].startswith("This is a great new app"))
        self.assertEqual(summaries[1], "Click link to read story.")

    def test_newspaper_json_structure(self):
        build_newspaper()
        self.assertTrue(os.path.exists("newspaper.json"))
        with open("newspaper.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("generated_at", data)
        self.assertIn("categories", data)
        self.assertIn("market", data)
        self.assertIn("hacker_news", data)


if __name__ == "__main__":
    unittest.main()
