"""CORS 解析单测（无网络、无 LLM）。"""
from __future__ import annotations

import unittest

from cors_config import resolve_cors_settings


class CorsConfigTests(unittest.TestCase):
    def test_wildcard_disables_credentials(self) -> None:
        s = resolve_cors_settings("*", is_production=False)
        self.assertEqual(s.allow_origins, ["*"])
        self.assertFalse(s.allow_credentials)
        self.assertTrue(s.wildcard)
        self.assertIn("allow_credentials", s.warning)

    def test_empty_same_as_wildcard(self) -> None:
        s = resolve_cors_settings("  ", is_production=False)
        self.assertTrue(s.wildcard)
        self.assertFalse(s.allow_credentials)

    def test_explicit_origins_keep_credentials(self) -> None:
        s = resolve_cors_settings(
            "https://mes.example.com, http://127.0.0.1:5180",
            allow_credentials_env="true",
            is_production=False,
        )
        self.assertEqual(
            s.allow_origins,
            ["https://mes.example.com", "http://127.0.0.1:5180"],
        )
        self.assertTrue(s.allow_credentials)
        self.assertFalse(s.wildcard)
        self.assertEqual(s.warning, "")

    def test_explicit_can_disable_credentials(self) -> None:
        s = resolve_cors_settings(
            "https://mes.example.com",
            allow_credentials_env="false",
            is_production=False,
        )
        self.assertFalse(s.allow_credentials)

    def test_production_rejects_wildcard(self) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            resolve_cors_settings("*", is_production=True)
        self.assertIn("生产环境禁止", str(ctx.exception))

    def test_production_allows_explicit(self) -> None:
        s = resolve_cors_settings(
            "https://mes.example.com",
            is_production=True,
        )
        self.assertEqual(s.allow_origins, ["https://mes.example.com"])
        self.assertTrue(s.allow_credentials)


if __name__ == "__main__":
    unittest.main()
