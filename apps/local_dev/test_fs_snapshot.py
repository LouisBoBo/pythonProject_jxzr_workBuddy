"""本机写码：沙照快照与 agent 配置。"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from local_dev.config import get_config
from local_dev.fs_snapshot import diff_snapshots, snapshot_sandbox


class FsSnapshotTests(unittest.TestCase):
    def test_detects_new_and_changed_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.txt").write_text("one", encoding="utf-8")
            (root / "skip_me").mkdir()
            (root / "node_modules").mkdir()
            (root / "node_modules" / "x.js").write_text("x", encoding="utf-8")
            before = snapshot_sandbox(root)
            self.assertIn("a.txt", before)
            self.assertNotIn("node_modules/x.js", before)

            (root / "a.txt").write_text("two", encoding="utf-8")
            (root / "b.txt").write_text("new", encoding="utf-8")
            (root / ".cursor-sdk-store").mkdir()
            (root / ".cursor-sdk-store" / "db").write_text("x", encoding="utf-8")
            after = snapshot_sandbox(root)
            changed = diff_snapshots(before, after)
            self.assertEqual(changed, ["a.txt", "b.txt"])
            self.assertNotIn(".cursor/state.json", after)
            self.assertNotIn(".cursor-sdk-store/db", after)


class LocalDevAgentConfigTests(unittest.TestCase):
    def test_default_agent_is_cursor_sdk(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LOCAL_DEV_AGENT", None)
            cfg = get_config()
            self.assertEqual(cfg.agent, "cursor_sdk")

    def test_llm_blocked_without_allow_flag(self):
        with mock.patch.dict(os.environ, {"LOCAL_DEV_AGENT": "deepseek"}, clear=False):
            os.environ.pop("LOCAL_DEV_ALLOW_LLM_FALLBACK", None)
            cfg = get_config()
            self.assertEqual(cfg.agent, "cursor_sdk")

    def test_llm_allowed_with_explicit_flag(self):
        with mock.patch.dict(
            os.environ,
            {"LOCAL_DEV_AGENT": "llm", "LOCAL_DEV_ALLOW_LLM_FALLBACK": "1"},
            clear=False,
        ):
            cfg = get_config()
            self.assertEqual(cfg.agent, "llm")


if __name__ == "__main__":
    unittest.main()
