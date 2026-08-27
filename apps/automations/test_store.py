"""自动化 store 安全边界单测。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automations import store


class AutomationStoreTests(unittest.TestCase):
    def test_sanitize_cwds_rejects_outside_repo(self) -> None:
        repo = store._repo_root_for_cwds()
        self.assertIsNotNone(repo)
        outside = str(Path(tempfile.gettempdir()).resolve())
        if outside == str(repo):
            outside = str((repo / "..").resolve())
        cwds = store._sanitize_cwds([outside, "/etc"])
        self.assertEqual(cwds, [])

    def test_sanitize_cwds_accepts_repo_subdir(self) -> None:
        repo = store._repo_root_for_cwds()
        self.assertIsNotNone(repo)
        cwds = store._sanitize_cwds([str(repo / "apps")])
        self.assertEqual(cwds, [str((repo / "apps").resolve())])

    def test_unsafe_automation_id_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            self.assertIsNone(store.get_automation(data, "../etc"))
            self.assertFalse(store.delete_automation(data, "auto/../x"))
            self.assertIsNone(store.update_automation(data, "auto%00x", {"name": "x"}))

    def test_run_records_capped_at_max(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            base = 1_700_000_000
            for i in range(store.MAX_RUN_RECORDS + 5):
                store.append_run(
                    data,
                    {
                        "automation_id": "auto-test",
                        "automation_name": "t",
                        "status": "succeeded",
                        "started_at": base + i,
                    },
                )
            items, total = store.list_runs(data, page=1, page_size=store.MAX_RUN_RECORDS)
            self.assertEqual(total, store.MAX_RUN_RECORDS)
            self.assertEqual(len(items), store.MAX_RUN_RECORDS)
            self.assertEqual(items[0]["started_at"], base + store.MAX_RUN_RECORDS + 4)
            self.assertEqual(items[-1]["started_at"], base + 5)


if __name__ == "__main__":
    unittest.main()
