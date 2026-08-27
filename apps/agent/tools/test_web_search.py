"""智谱联网搜索工具单测。"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from tools.web_search import _format_results_markdown, search_web, web_search_enabled


class TestWebSearch(unittest.TestCase):
    def test_format_markdown(self):
        md = _format_results_markdown(
            [
                {
                    "title": "测试新闻",
                    "content": "摘要内容",
                    "link": "https://example.com/a",
                    "media": "Example",
                    "publish_date": "2026-08-27",
                }
            ]
        )
        self.assertIn("测试新闻", md)
        self.assertIn("https://example.com/a", md)

    @patch("tools.web_search._api_key", return_value="")
    def test_missing_key(self, _mock_key):
        out = search_web("PCB AI 新闻")
        self.assertFalse(out.get("ok"))
        self.assertIn("未配置", out.get("error", ""))

    @patch("tools.web_search._api_key", return_value="test-key")
    @patch("tools.web_search.urlopen_limited")
    def test_success(self, mock_open, _key):
        payload = {
            "search_result": [
                {
                    "title": "AI 服务器带动 HDI",
                    "content": "高层板需求上升",
                    "link": "https://news.example/pcb",
                    "media": "News",
                    "publish_date": "2026-08-27",
                }
            ]
        }

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self):
                return json.dumps(payload).encode()

        mock_open.return_value = _Resp()
        out = search_web("PCB AI", count=5, search_recency_filter="oneDay")
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("count"), 1)
        self.assertIn("AI 服务器", out.get("markdown", ""))

    @patch("tools.web_search._api_key", return_value="k")
    def test_enabled_with_key(self, _key):
        self.assertTrue(web_search_enabled())


if __name__ == "__main__":
    unittest.main()
