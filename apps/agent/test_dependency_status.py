"""依赖就绪摘要单测（无网络）。"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import dependency_status as ds


class DependencyStatusTests(unittest.TestCase):
    def test_hints_stable(self) -> None:
        with patch.object(ds, "llm_configured", return_value=True), patch.object(
            ds, "vision_configured", return_value=True
        ), patch.object(ds, "platform_base_configured", return_value=True), patch.object(
            ds, "cursor_api_configured", return_value=True
        ):
            s = ds.summarize_dependencies()
        self.assertEqual(s["hints"]["llm_missing"], ds.LLM_KEY_MISSING)
        self.assertEqual(s["hints"]["platform_unreachable"], ds.PLATFORM_UNREACHABLE)
        self.assertIn("VISION_API_KEY", s["hints"]["vision_missing"])
        self.assertTrue(s["critical_ready"])
        self.assertEqual(s["degrade"], [])

    def test_no_llm_is_critical(self) -> None:
        with patch.object(ds, "llm_configured", return_value=False), patch.object(
            ds, "vision_configured", return_value=True
        ), patch.object(ds, "platform_base_configured", return_value=True), patch.object(
            ds, "cursor_api_configured", return_value=True
        ):
            s = ds.summarize_dependencies()
        self.assertFalse(s["critical_ready"])
        ids = [d["id"] for d in s["degrade"]]
        self.assertIn("llm", ids)
        self.assertEqual(
            next(d for d in s["degrade"] if d["id"] == "llm")["severity"],
            "critical",
        )

    def test_vision_only_is_degraded(self) -> None:
        with patch.object(ds, "llm_configured", return_value=True), patch.object(
            ds, "vision_configured", return_value=False
        ), patch.object(ds, "platform_base_configured", return_value=True), patch.object(
            ds, "cursor_api_configured", return_value=False
        ):
            s = ds.summarize_dependencies()
        self.assertTrue(s["critical_ready"])
        by_id = {d["id"]: d for d in s["degrade"]}
        self.assertEqual(by_id["vision"]["severity"], "degraded")
        self.assertEqual(by_id["cursor_cloud"]["severity"], "optional")

    def test_platform_unreachable_copy_in_erp_client(self) -> None:
        api = Path(__file__).resolve().parent / "tools" / "platform_api.py"
        text = api.read_text(encoding="utf-8")
        self.assertIn(ds.PLATFORM_UNREACHABLE, text)

    def test_llm_missing_copy_in_build_model(self) -> None:
        agent = Path(__file__).resolve().parent / "agents" / "agent.py"
        text = agent.read_text(encoding="utf-8")
        self.assertIn(ds.LLM_KEY_MISSING, text)


if __name__ == "__main__":
    unittest.main()
