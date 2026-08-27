"""repo_digest 单测（mock git）。"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from automations.repo_digest import build_weekly_repo_digest


class RepoDigestTests(unittest.TestCase):
    @patch("automations.repo_digest._run_git")
    @patch("automations.repo_digest._repo_root")
    def test_digest_with_commits(self, mock_root, mock_git):
        mock_root.return_value = Path("/fake/repo")
        mock_git.side_effect = [
            (0, "true", ""),
            (
                0,
                "abc1234|2026-08-27|hebo|feat: 自动化任务与联网搜索\n"
                "def5678|2026-08-26|hebo|fix: 周报展示",
                "",
            ),
            (0, "apps/web/src/views/AutomationsView.vue\napps/automations/executor.py", ""),
            (0, " 2 files changed, 120 insertions(+), 5 deletions(-)", ""),
            (0, "", ""),
            (0, "", ""),
        ]
        out = build_weekly_repo_digest()
        self.assertIn("提交数：2", out)
        self.assertIn("自动化任务", out)
        self.assertIn("AutomationsView.vue", out)
        self.assertIn("禁止编造", out)

    @patch("automations.repo_digest._run_git")
    @patch("automations.repo_digest._repo_root")
    def test_digest_no_commits(self, mock_root, mock_git):
        mock_root.return_value = Path("/fake/repo")
        mock_git.side_effect = [
            (0, "true", ""),
            (0, "", ""),
            (0, "", ""),
            (0, "", ""),
            (0, "", ""),
            (0, "", ""),
        ]
        out = build_weekly_repo_digest()
        self.assertIn("暂无 git 提交", out)


if __name__ == "__main__":
    unittest.main()
