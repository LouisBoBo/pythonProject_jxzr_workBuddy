"""出站 HTTP 约束。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request

_AGENT = Path(__file__).resolve().parent
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from safe_http import (
    SameHostRedirectHandler,
    assert_http_url_allowed,
    safe_query_name,
    safe_request_path,
)


class SafeHttpTests(unittest.TestCase):
    def test_allows_loopback_and_private(self) -> None:
        self.assertTrue(assert_http_url_allowed("http://127.0.0.1:8009/docs").startswith("http://"))
        self.assertEqual(
            assert_http_url_allowed("http://10.0.0.8:8080"),
            "http://10.0.0.8:8080",
        )

    def test_rejects_metadata_and_link_local(self) -> None:
        with self.assertRaises(ValueError):
            assert_http_url_allowed("http://169.254.169.254/latest/meta-data")
        with self.assertRaises(ValueError):
            assert_http_url_allowed("http://metadata.google.internal/")
        with self.assertRaises(ValueError):
            assert_http_url_allowed("http://100.100.100.200/")

    def test_rejects_file_and_userinfo(self) -> None:
        with self.assertRaises(ValueError):
            assert_http_url_allowed("file:///etc/passwd")
        with self.assertRaises(ValueError):
            assert_http_url_allowed("http://user:pass@127.0.0.1:8009/")

    def test_safe_path_and_query(self) -> None:
        self.assertEqual(safe_request_path("/api/auth/login"), "/api/auth/login")
        self.assertIsNone(safe_request_path("http://evil/login"))
        self.assertIsNone(safe_request_path("/api/../etc"))
        self.assertIsNone(safe_request_path("/x?a=1"))
        self.assertEqual(safe_query_name("pageSize"), "pageSize")
        self.assertIsNone(safe_query_name("page=1&x"))

    def test_redirect_handler_blocks_cross_host(self) -> None:
        handler = SameHostRedirectHandler()
        req = Request("http://127.0.0.1:8009/login")
        with self.assertRaises(URLError):
            handler.redirect_request(
                req, None, 307, "tmp", {}, "http://evil.example/steal"
            )


if __name__ == "__main__":
    unittest.main()
