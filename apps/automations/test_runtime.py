"""自动化 runtime 僵尸锁回收单测。"""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from automations import runtime as rt


class AutomationRuntimeTests(unittest.TestCase):
    def test_stale_lock_reclaimed(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            aid = "auto-stale"
            self.assertTrue(rt.mark_running(data_dir, aid, "run-old"))
            # 伪造超期 started_at
            path = data_dir / "automations" / "runtime.json"
            path.write_text(
                '{"running":{"auto-stale":{"run_id":"run-old","started_at":1}}}\n',
                encoding="utf-8",
            )
            self.assertFalse(rt.is_running(data_dir, aid))
            self.assertTrue(rt.mark_running(data_dir, aid, "run-new"))
            self.assertTrue(rt.is_running(data_dir, aid))
            rt.clear_running(data_dir, aid, "run-new")
            self.assertFalse(rt.is_running(data_dir, aid))

    def test_fresh_lock_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            aid = "auto-fresh"
            self.assertTrue(rt.mark_running(data_dir, aid, "run-a"))
            self.assertFalse(rt.mark_running(data_dir, aid, "run-b"))
            rt.clear_running(data_dir, aid, "run-a")
            self.assertTrue(rt.mark_running(data_dir, aid, "run-b"))


if __name__ == "__main__":
    unittest.main()
