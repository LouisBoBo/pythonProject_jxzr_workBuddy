"""本机写码：审码门禁与 git 提交单测（无 LLM）。"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from local_dev.commit_gate import run_commit_review_gate
from local_dev.git_commit import (
    commit_synced_files,
    draft_chinese_commit_message,
    inspect_git_repo,
    resolve_work_branch,
    validate_chinese_commit_message,
)


class CommitGateTests(unittest.TestCase):
    def test_blocks_env_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".env").write_text("X=1\n", encoding="utf-8")
            (root / "app.py").write_text("print(1)\n", encoding="utf-8")
            with mock.patch("local_dev.commit_gate._try_ide_review", return_value=None):
                r = run_commit_review_gate(root, [".env", "app.py"], allow_blocked_override=False)
            self.assertGreaterEqual(r["blocking_count"], 1)
            self.assertFalse(r["can_commit"])

    def test_pass_clean_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "ok.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
            with mock.patch("local_dev.commit_gate._try_ide_review", return_value=None):
                r = run_commit_review_gate(root, ["ok.py"], allow_blocked_override=False)
            self.assertEqual(r["blocking_count"], 0)
            self.assertTrue(r["can_commit"])

    def test_eval_is_blocking(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bad.js").write_text("eval(userInput)\n", encoding="utf-8")
            with mock.patch("local_dev.commit_gate._try_ide_review", return_value=None):
                r = run_commit_review_gate(root, ["bad.js"])
            self.assertGreaterEqual(r["blocking_count"], 1)
            self.assertFalse(r["can_commit"])

    def test_uses_ide_review_when_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "ok.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
            fake = {
                "status": "ok",
                "findings": [
                    {
                        "severity": "P0",
                        "path": "ok.py",
                        "rule": "dangerous-eval",
                        "message": "eval",
                    }
                ],
            }
            with mock.patch("local_dev.commit_gate._try_ide_review", return_value=fake):
                r = run_commit_review_gate(
                    root, ["ok.py"], use_ide_review=True, use_skill_review=False
                )
            self.assertEqual(r["provider"], "ide_review+path")
            self.assertGreaterEqual(r["blocking_count"], 1)

    def test_uses_skill_review_when_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "ok.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
            fake_skill = {
                "ok": True,
                "provider": "commit-batch-review-skill",
                "review_method": "commit-batch-review Skill",
                "process_steps": ["① 读 checklist", "② 扫描本批"],
                "findings": [],
                "file_scans": [{"path": "ok.py", "status": "pass", "steps": ["内容检查通过"], "issues": []}],
                "blocking_count": 0,
                "warning_count": 0,
                "can_commit": True,
                "summary": "可提交",
                "verdict": "pass",
            }
            with mock.patch(
                "local_dev.commit_batch_review.run_commit_batch_skill_review",
                return_value=fake_skill,
            ):
                r = run_commit_review_gate(root, ["ok.py"], use_skill_review=True)
            self.assertEqual(r["provider"], "commit-batch-review-skill")
            self.assertEqual(len(r.get("process_steps") or []), 2)
            self.assertTrue(r["can_commit"])

    def test_hardcoded_secret_is_blocking(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cfg.py").write_text('password = "SuperSecret123"\n', encoding="utf-8")
            with mock.patch("local_dev.commit_gate._try_ide_review", return_value=None):
                r = run_commit_review_gate(root, ["cfg.py"], allow_blocked_override=False)
            self.assertGreaterEqual(r["blocking_count"], 1)
            self.assertFalse(r["can_commit"])
            self.assertEqual(r["verdict"], "blocked")

    def test_allow_blocked_override_permits_commit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bad.js").write_text("eval(x)\n", encoding="utf-8")
            with mock.patch("local_dev.commit_gate._try_ide_review", return_value=None):
                r = run_commit_review_gate(root, ["bad.js"], allow_blocked_override=True)
            self.assertGreaterEqual(r["blocking_count"], 1)
            self.assertTrue(r["can_commit"])


class GitCommitTests(unittest.TestCase):
    def _git(self, cwd: Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)

    def test_commit_on_work_branch_not_main(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._git(root, "init")
            self._git(root, "config", "user.email", "t@example.com")
            self._git(root, "config", "user.name", "t")
            (root / "a.txt").write_text("one\n", encoding="utf-8")
            self._git(root, "add", "a.txt")
            self._git(root, "commit", "-m", "init")
            # ensure on main/master
            code = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(root),
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn(code.stdout.strip().lower(), {"main", "master"})

            (root / "b.txt").write_text("two\n", encoding="utf-8")
            r = commit_synced_files(
                root,
                ["b.txt"],
                message="测试：新增 b.txt",
                work_branch="dev/wb/testuser",
                push=False,
            )
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["branch"], "dev/wb/testuser")
            self.assertTrue(r["commit"])
            info = inspect_git_repo(root)
            self.assertEqual(info["current_branch"], "dev/wb/testuser")

    def test_skips_gitignore_and_commits_rest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._git(root, "init")
            self._git(root, "config", "user.email", "t@example.com")
            self._git(root, "config", "user.name", "t")
            (root / ".gitignore").write_text("*.db\n", encoding="utf-8")
            (root / "a.py").write_text("print(1)\n", encoding="utf-8")
            (root / "erp.db").write_text("x", encoding="utf-8")
            self._git(root, "add", ".gitignore", "a.py")
            self._git(root, "commit", "-m", "init")
            (root / "b.py").write_text("print(2)\n", encoding="utf-8")
            (root / "erp.db").write_text("y", encoding="utf-8")
            r = commit_synced_files(
                root,
                ["b.py", "erp.db"],
                message="测试：新增 b.py 并跳过 db",
                work_branch="dev/wb/t",
                push=False,
            )
            self.assertTrue(r["ok"], r)
            self.assertTrue(r.get("commit"), r)
            self.assertIn("b.py", r.get("files") or [])
            self.assertIn("erp.db", r.get("skipped_ignored") or [])

    def test_push_only_when_no_synced_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._git(root, "init")
            self._git(root, "config", "user.email", "t@example.com")
            self._git(root, "config", "user.name", "t")
            (root / "a.txt").write_text("one\n", encoding="utf-8")
            self._git(root, "add", "a.txt")
            self._git(root, "commit", "-m", "init")
            self._git(root, "checkout", "-B", "dev/wb/t")
            with mock.patch("local_dev.git_commit._push_work_branch") as push:
                push.return_value = {"ok": True, "remote": "origin", "remote_url": "https://x.git"}
                r = commit_synced_files(
                    root,
                    [],
                    message="不应使用",
                    work_branch="dev/wb/t",
                    push=True,
                )
            self.assertTrue(r["ok"], r)
            self.assertTrue(r.get("skipped"))
            self.assertTrue(r.get("commit"))
            push.assert_called_once()

    def test_refuse_protected_work_branch_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._git(root, "init")
            r = commit_synced_files(
                root,
                ["x"],
                message="m",
                work_branch="main",
                push=False,
            )
            self.assertFalse(r["ok"])
            self.assertIn("保护", r["error"])

    def test_resolve_work_branch(self):
        with mock.patch.dict("os.environ", {"LOCAL_DEV_WORK_BRANCH": "hebo"}, clear=False):
            self.assertEqual(resolve_work_branch(username="other"), "hebo")


class ChineseCommitMessageTests(unittest.TestCase):
    def test_validate_requires_chinese(self):
        ok, err = validate_chinese_commit_message("update seed data")
        self.assertFalse(ok)
        self.assertIn("中文", err)
        ok2, _ = validate_chinese_commit_message("扩容工单样例数据到 100 条")
        self.assertTrue(ok2)

    def test_draft_from_files_when_generic_prompt(self):
        msg = draft_chinese_commit_message(
            user_message="提交今天的代码",
            files=["backend/seed_analytics.py", "frontend/a.js"],
        )
        self.assertTrue(validate_chinese_commit_message(msg)[0])
        self.assertIn("seed_analytics.py", msg)


class PendingCommitFilterTests(unittest.TestCase):
    def _git(self, cwd: Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)

    def test_filters_to_git_pending_intersection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._git(root, "init")
            self._git(root, "config", "user.email", "t@example.com")
            self._git(root, "config", "user.name", "t")
            (root / "old.py").write_text("a=1\n", encoding="utf-8")
            (root / "new.py").write_text("b=2\n", encoding="utf-8")
            self._git(root, "add", "old.py")
            self._git(root, "commit", "-m", "init")
            (root / "old.py").write_text("a=2\n", encoding="utf-8")
            from local_dev.git_commit import filter_pending_commit_files

            pool = ["old.py", "new.py", "gone.py"]
            r = filter_pending_commit_files(root, pool)
            self.assertIn("old.py", r["pending_files"])
            self.assertIn("new.py", r["pending_files"])
            self.assertNotIn("gone.py", r["pending_files"])
            self.assertEqual(r["synced_total"], 3)

    def test_excludes_non_business_from_pending(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._git(root, "init")
            self._git(root, "config", "user.email", "t@example.com")
            self._git(root, "config", "user.name", "t")
            (root / "Login.vue").write_text("<template>login</template>\n", encoding="utf-8")
            (root / "package.json").write_text('{"name":"x"}\n', encoding="utf-8")
            (root / "vite.config.ts").write_text("export default {}\n", encoding="utf-8")
            self._git(root, "add", "Login.vue")
            self._git(root, "commit", "-m", "init")
            (root / "Login.vue").write_text("<template>login v2</template>\n", encoding="utf-8")
            (root / "package.json").write_text('{"name":"x","version":"2"}\n', encoding="utf-8")
            from local_dev.git_commit import filter_pending_commit_files

            pool = ["Login.vue", "package.json", "vite.config.ts", "README.md"]
            r = filter_pending_commit_files(root, pool)
            self.assertEqual(r["pending_files"], ["Login.vue"])
            self.assertEqual(r["excluded_non_business_total"], 3)
            self.assertIn("package.json", r["excluded_non_business"])

    def test_is_git_network_error(self):
        from local_dev.git_commit import is_commit_result_retryable, is_git_network_error

        self.assertTrue(is_git_network_error("Failed to connect: Connection timed out"))
        self.assertTrue(
            is_git_network_error(
                "fatal: unable to access 'https://github.com/x/y.git/': Recv failure: Operation timed out"
            )
        )
        self.assertFalse(is_git_network_error("禁止提交到保护分支 main"))
        from local_dev.git_commit import is_push_retry_needed

        self.assertTrue(
            is_push_retry_needed(
                {
                    "commit": "abc",
                    "push": {"ok": False, "error": "Recv failure: Operation timed out"},
                }
            )
        )
        out = {
            "ok": True,
            "commit": "abc",
            "push": {"ok": False, "error": "Could not resolve host: github.com"},
        }
        self.assertTrue(is_commit_result_retryable(out))

    def test_excludes_dev_logs_noise(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._git(root, "init")
            logs = root / ".dev-logs"
            logs.mkdir()
            (logs / "backend.log").write_text("x\n", encoding="utf-8")
            from local_dev.git_commit import filter_pending_commit_files, is_commit_noise_path

            self.assertTrue(is_commit_noise_path(".dev-logs/backend.log"))
            r = filter_pending_commit_files(root, [".dev-logs/backend.log"])
            self.assertEqual(r["pending_files"], [])


if __name__ == "__main__":
    unittest.main()
