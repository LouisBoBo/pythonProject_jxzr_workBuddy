"""openapi_fetch：/docs → openapi.json 候选。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_AGENT = Path(__file__).resolve().parents[2]
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from tools.query_tool.openapi_fetch import openapi_candidate_urls, validate_docs_url


class OpenApiFetchTests(unittest.TestCase):
    def test_docs_expands_to_openapi_json(self) -> None:
        urls = openapi_candidate_urls("http://127.0.0.1:8009/docs")
        self.assertTrue(any(u.endswith("/openapi.json") for u in urls))
        self.assertTrue(urls[0].endswith("/openapi.json"))

    def test_openapi_json_kept(self) -> None:
        urls = openapi_candidate_urls("http://127.0.0.1:8009/openapi.json")
        self.assertEqual(urls, ["http://127.0.0.1:8009/openapi.json"])

    def test_rejects_bad_scheme(self) -> None:
        with self.assertRaises(ValueError):
            validate_docs_url("file:///etc/passwd")

    def test_rejects_metadata_ip(self) -> None:
        with self.assertRaises(ValueError):
            validate_docs_url("http://169.254.169.254/latest/meta-data")


if __name__ == "__main__":
    unittest.main()
