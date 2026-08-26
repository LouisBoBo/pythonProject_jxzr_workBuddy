"""commit-batch-review Skill 执行器单测。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from local_dev.commit_batch_review import (
    _build_llm_usage,
    _estimate_tokens,
    _extract_json,
    _normalize_skill_result,
    _read_batch_contents,
    _usage_from_response,
    load_skill_bundle,
)


class CommitBatchReviewTests(unittest.TestCase):
    def test_load_skill_bundle_nonempty(self):
        bundle = load_skill_bundle()
        self.assertIn("commit-batch-review", bundle)
        self.assertIn("output-schema", bundle.lower())

    def test_read_batch_skips_db_and_keeps_vue(self):
        """批审读盘不得把 .db 等非业务源码送进 LLM。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "LoginView.vue").write_text("<template></template>\n", encoding="utf-8")
            (root / "erp.db").write_bytes(b"SQLite\x00format")
            out = _read_batch_contents(root, ["LoginView.vue", "erp.db", "package.json"])
            paths = [x["path"] for x in out]
            self.assertIn("LoginView.vue", paths)
            self.assertNotIn("erp.db", paths)
            self.assertNotIn("package.json", paths)

    def test_extract_json_from_fence(self):
        raw = '```json\n{"verdict":"pass","summary":"ok","findings":[]}\n```'
        data = _extract_json(raw)
        self.assertEqual(data.get("verdict"), "pass")

    def test_normalize_marks_p1_blocking(self):
        out = _normalize_skill_result(
            {
                "verdict": "blocked",
                "summary": "有阻断",
                "findings": [
                    {
                        "severity": "P1",
                        "path": "a.py",
                        "rule": "secret",
                        "message": "硬编码密钥",
                        "blocking": False,
                    }
                ],
                "file_scans": [],
            },
            synced=["a.py"],
        )
        self.assertEqual(out["blocking_count"], 1)
        self.assertFalse(out["can_commit"])

    def test_estimate_tokens_rough(self):
        self.assertEqual(_estimate_tokens(""), 0)
        self.assertGreaterEqual(_estimate_tokens("abcd"), 2)
        self.assertEqual(_estimate_tokens("中文测试"), 2)

    def test_usage_from_response_usage_metadata(self):
        resp = SimpleNamespace(
            usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
            response_metadata={},
        )
        u = _usage_from_response(resp)
        self.assertEqual(u["prompt_tokens"], 100)
        self.assertEqual(u["completion_tokens"], 20)
        self.assertEqual(u["total_tokens"], 120)

    def test_build_llm_usage_prefers_api_tokens(self):
        resp = SimpleNamespace(
            usage_metadata={"input_tokens": 50, "output_tokens": 10},
            response_metadata={},
        )
        usage = _build_llm_usage(
            model_name="deepseek-v4-flash",
            system="sys",
            user="user text",
            output_text="out",
            resp=resp,
            elapsed_ms=12,
            file_count=1,
        )
        self.assertEqual(usage["model"], "deepseek-v4-flash")
        self.assertEqual(usage["source"], "api")
        self.assertEqual(usage["prompt_tokens"], 50)
        self.assertEqual(usage["completion_tokens"], 10)
        self.assertIn("estimated_total_tokens", usage)

    def test_normalize_attaches_llm_usage(self):
        out = _normalize_skill_result(
            {"verdict": "pass", "summary": "ok", "findings": [], "file_scans": []},
            synced=["a.py"],
            llm_usage={"model": "deepseek-v4-flash", "estimated_total_tokens": 100},
        )
        self.assertEqual(out["llm_usage"]["model"], "deepseek-v4-flash")


if __name__ == "__main__":
    unittest.main()
