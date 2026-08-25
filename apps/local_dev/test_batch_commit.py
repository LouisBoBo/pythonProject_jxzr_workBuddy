"""人触发本批提交：汇文件 + 不取消写码任务（无 LLM）。"""
from __future__ import annotations

import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from local_dev import jobs as job_store
from local_dev.batch_commit import collect_batch_synced_files, finalize_commit_batch, start_commit_batch


class BatchCommitTests(unittest.TestCase):
    def _git(self, cwd: Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)

    def _init_repo_with_file(self, ws: Path, rel: str = "a.py") -> None:
        self._git(ws, "init")
        self._git(ws, "config", "user.email", "t@example.com")
        self._git(ws, "config", "user.name", "t")
        (ws / rel).write_text("print(1)\n", encoding="utf-8")

    def test_collect_today_files_from_succeeded_jobs(self):
        with tempfile.TemporaryDirectory() as td:
            data = Path(td)
            ws = data / "proj"
            ws.mkdir()
            (ws / "a.py").write_text("x=1\n", encoding="utf-8")
            (ws / "b.py").write_text("y=2\n", encoding="utf-8")
            now = int(time.time())
            job_store.write_job_document(
                data,
                {
                    "id": "ldj-old1",
                    "user_id": "u1",
                    "username": "t",
                    "thread_id": "",
                    "workspace": str(ws),
                    "status": "succeeded",
                    "runtime": "cursor_local",
                    "synced_files": ["a.py"],
                    "messages": [],
                    "created_at": now,
                    "updated_at": now,
                },
            )
            job_store.write_job_document(
                data,
                {
                    "id": "ldj-old2",
                    "user_id": "u1",
                    "username": "t",
                    "thread_id": "",
                    "workspace": str(ws),
                    "status": "succeeded",
                    "runtime": "cursor_local",
                    "synced_files": ["b.py", "a.py"],
                    "messages": [],
                    "created_at": now,
                    "updated_at": now,
                },
            )
            # 其它用户 / 其它目录不应混入
            job_store.write_job_document(
                data,
                {
                    "id": "ldj-other",
                    "user_id": "u2",
                    "username": "x",
                    "thread_id": "",
                    "workspace": str(ws),
                    "status": "succeeded",
                    "runtime": "cursor_local",
                    "synced_files": ["nope.py"],
                    "messages": [],
                    "created_at": now,
                    "updated_at": now,
                },
            )
            batch = collect_batch_synced_files(
                data, user_id="u1", workspace=str(ws), today_only=True, now=float(now)
            )
            self.assertEqual(set(batch["files"]), {"a.py", "b.py"})

    def test_start_does_not_cancel_running_dev_job(self):
        with tempfile.TemporaryDirectory() as td:
            data = Path(td)
            ws = data / "proj"
            ws.mkdir()
            self._init_repo_with_file(ws, "a.py")
            now = int(time.time())
            job_store.write_job_document(
                data,
                {
                    "id": "ldj-run1",
                    "user_id": "u1",
                    "username": "t",
                    "thread_id": "",
                    "workspace": str(ws),
                    "status": "running",
                    "runtime": "cursor_local",
                    "synced_files": [],
                    "messages": [],
                    "created_at": now,
                    "updated_at": now,
                    "cancel_requested": False,
                },
            )
            job_store.write_job_document(
                data,
                {
                    "id": "ldj-ok1",
                    "user_id": "u1",
                    "username": "t",
                    "thread_id": "",
                    "workspace": str(ws),
                    "status": "succeeded",
                    "runtime": "cursor_local",
                    "synced_files": ["a.py"],
                    "messages": [],
                    "created_at": now,
                    "updated_at": now,
                },
            )
            with mock.patch("local_dev.batch_commit.run_commit_review_gate") as gate:
                gate.return_value = {
                    "ok": True,
                    "summary": "ok",
                    "findings": [],
                    "blocking_count": 0,
                    "warning_count": 0,
                    "can_commit": True,
                }
                out = start_commit_batch(
                    data,
                    user_id="u1",
                    username="t",
                    thread_id="th",
                    workspace=str(ws),
                    message="提交今天的代码",
                    today_only=True,
                )
            self.assertTrue(out["ok"], out)
            running = job_store.get_job(data, "ldj-run1")
            self.assertEqual(running.get("status"), "running")
            self.assertFalse(running.get("cancel_requested"))
            self.assertEqual(out["job"]["runtime"], "commit_batch")
            self.assertEqual(out["job"]["status"], "awaiting_commit")

    def test_start_supersedes_pending_commit_batch(self):
        """再次提交时自动跳过旧 awaiting_commit，避免死锁。"""
        with tempfile.TemporaryDirectory() as td:
            data = Path(td)
            ws = data / "proj"
            ws.mkdir()
            self._init_repo_with_file(ws, "a.py")
            now = int(time.time())
            old_id = "ldj-pending1"
            job_store.write_job_document(
                data,
                {
                    "id": old_id,
                    "user_id": "u1",
                    "username": "t",
                    "thread_id": "",
                    "workspace": str(ws),
                    "status": "awaiting_commit",
                    "runtime": "commit_batch",
                    "synced_files": ["a.py"],
                    "commit_gate": {"can_commit": True, "work_branch": "dev/wb/t"},
                    "messages": [{"role": "user", "content": "提交", "at": now}],
                    "created_at": now,
                    "updated_at": now,
                },
            )
            job_store.write_job_document(
                data,
                {
                    "id": "ldj-ok1",
                    "user_id": "u1",
                    "username": "t",
                    "thread_id": "",
                    "workspace": str(ws),
                    "status": "succeeded",
                    "runtime": "cursor_local",
                    "synced_files": ["a.py"],
                    "messages": [],
                    "created_at": now,
                    "updated_at": now,
                },
            )
            with mock.patch("local_dev.batch_commit.run_commit_review_gate") as gate:
                gate.return_value = {
                    "ok": True,
                    "summary": "ok",
                    "findings": [],
                    "blocking_count": 0,
                    "warning_count": 0,
                    "can_commit": True,
                }
                out = start_commit_batch(
                    data,
                    user_id="u1",
                    username="t",
                    thread_id="th",
                    workspace=str(ws),
                    message="提交今天的代码",
                    today_only=True,
                )
            self.assertTrue(out["ok"], out)
            self.assertIn(old_id, out.get("superseded_job_ids") or [])
            old = job_store.get_job(data, old_id)
            self.assertEqual(old.get("status"), "succeeded")
            self.assertEqual(old.get("commit_decision"), "skip")
            self.assertTrue((old.get("commit_result") or {}).get("superseded"))
            self.assertEqual(out["job"]["status"], "awaiting_commit")
            self.assertNotEqual(out["job"]["id"], old_id)

    def test_finalize_skip(self):
        with tempfile.TemporaryDirectory() as td:
            data = Path(td)
            ws = data / "proj"
            ws.mkdir()
            now = int(time.time())
            jid = "ldj-batch1"
            job_store.write_job_document(
                data,
                {
                    "id": jid,
                    "user_id": "u1",
                    "username": "t",
                    "thread_id": "",
                    "workspace": str(ws),
                    "status": "awaiting_commit",
                    "runtime": "commit_batch",
                    "synced_files": ["a.py"],
                    "commit_gate": {"can_commit": True, "work_branch": "dev/wb/t"},
                    "commit_decision": "skip",
                    "messages": [{"role": "user", "content": "提交", "at": now}],
                    "created_at": now,
                    "updated_at": now,
                },
            )
            out = finalize_commit_batch(data, jid, "skip")
            self.assertTrue(out["ok"])
            job = out["job"]
            self.assertEqual(job["status"], "succeeded")
            self.assertTrue(job["commit_result"].get("skipped"))

    def test_finalize_commit_rejected_when_gate_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            data = Path(td)
            ws = data / "proj"
            ws.mkdir()
            now = int(time.time())
            jid = "ldj-block1"
            job_store.write_job_document(
                data,
                {
                    "id": jid,
                    "user_id": "u1",
                    "username": "t",
                    "thread_id": "",
                    "workspace": str(ws),
                    "status": "awaiting_commit",
                    "runtime": "commit_batch",
                    "synced_files": ["bad.js"],
                    "commit_gate": {
                        "can_commit": False,
                        "blocking_count": 1,
                        "work_branch": "dev/wb/t",
                    },
                    "messages": [{"role": "user", "content": "提交", "at": now}],
                    "created_at": now,
                    "updated_at": now,
                },
            )
            with mock.patch("local_dev.batch_commit.commit_synced_files") as commit:
                out = finalize_commit_batch(
                    data,
                    jid,
                    "commit",
                    commit_message="测试：不应执行提交",
                )
                commit.assert_not_called()
            self.assertTrue(out["ok"])
            cr = out["commit_result"]
            self.assertFalse(cr.get("ok"))
            self.assertTrue(cr.get("skipped"))

    def test_finalize_commit_retryable_on_network_push_failure(self):
        with tempfile.TemporaryDirectory() as td:
            data = Path(td)
            ws = data / "proj"
            ws.mkdir()
            now = int(time.time())
            jid = "ldj-net1"
            job_store.write_job_document(
                data,
                {
                    "id": jid,
                    "user_id": "u1",
                    "username": "t",
                    "thread_id": "",
                    "workspace": str(ws),
                    "status": "awaiting_commit",
                    "runtime": "commit_batch",
                    "synced_files": ["a.py"],
                    "commit_gate": {"can_commit": True, "work_branch": "dev/wb/t"},
                    "commit_decision": "commit",
                    "messages": [{"role": "user", "content": "提交", "at": now}],
                    "created_at": now,
                    "updated_at": now,
                },
            )
            fake = {
                "ok": True,
                "skipped": False,
                "error": "",
                "branch": "dev/wb/t",
                "commit": "abc123",
                "files": ["a.py"],
                "message": "测试：更新 a.py",
                "push": {
                    "ok": False,
                    "error": "fatal: unable to access: Failed to connect to github.com port 443: Connection timed out",
                },
            }
            with mock.patch("local_dev.batch_commit.commit_synced_files", return_value=fake):
                out = finalize_commit_batch(
                    data,
                    jid,
                    "commit",
                    push=True,
                    commit_message="测试：更新 a.py",
                )
            self.assertTrue(out.get("retryable"))
            job = out["job"]
            self.assertEqual(job["status"], "awaiting_commit")
            self.assertIsNone(job.get("commit_decision"))
            self.assertTrue(job["commit_result"].get("retryable"))
            self.assertTrue(job["commit_result"].get("push_retry"))

    def test_finalize_push_retry_even_for_non_network_push_error(self):
        with tempfile.TemporaryDirectory() as td:
            data = Path(td)
            ws = data / "proj"
            ws.mkdir()
            now = int(time.time())
            jid = "ldj-push1"
            job_store.write_job_document(
                data,
                {
                    "id": jid,
                    "user_id": "u1",
                    "username": "t",
                    "thread_id": "",
                    "workspace": str(ws),
                    "status": "awaiting_commit",
                    "runtime": "commit_batch",
                    "synced_files": ["a.py"],
                    "commit_gate": {"can_commit": True, "work_branch": "dev/wb/t"},
                    "commit_decision": "commit",
                    "messages": [{"role": "user", "content": "提交", "at": now}],
                    "created_at": now,
                    "updated_at": now,
                },
            )
            fake = {
                "ok": True,
                "skipped": False,
                "branch": "dev/wb/t",
                "commit": "abc123",
                "files": ["a.py"],
                "message": "测试：更新 a.py",
                "push": {"ok": False, "error": "permission denied"},
            }
            with mock.patch("local_dev.batch_commit.commit_synced_files", return_value=fake):
                out = finalize_commit_batch(
                    data,
                    jid,
                    "commit",
                    push=True,
                    commit_message="测试：更新 a.py",
                )
            self.assertTrue(out.get("retryable"))
            self.assertTrue(out["commit_result"].get("push_retry"))
            self.assertEqual(out["job"]["status"], "awaiting_commit")

    def test_reopen_succeeded_job_for_push_retry(self):
        with tempfile.TemporaryDirectory() as td:
            data = Path(td)
            ws = data / "proj"
            ws.mkdir()
            now = int(time.time())
            jid = "ldj-reopen1"
            job_store.write_job_document(
                data,
                {
                    "id": jid,
                    "user_id": "u1",
                    "username": "t",
                    "thread_id": "",
                    "workspace": str(ws),
                    "status": "succeeded",
                    "runtime": "commit_batch",
                    "synced_files": ["LoginView.vue"],
                    "commit_decision": "commit",
                    "commit_result": {
                        "ok": True,
                        "commit": "646b701d34ea",
                        "branch": "hebo",
                        "message": "更新 LoginView.vue（1 个文件）",
                        "files": ["LoginView.vue"],
                        "push": {
                            "ok": False,
                            "error": "Recv failure: Operation timed out",
                        },
                    },
                    "commit_gate": {"can_commit": True, "work_branch": "hebo"},
                    "messages": [],
                    "created_at": now,
                    "updated_at": now,
                },
            )
            from local_dev.batch_commit import ensure_push_retry_confirmable

            reopened = ensure_push_retry_confirmable(data, jid, user_id="u1")
            self.assertEqual(reopened["status"], "awaiting_commit")
            self.assertIsNone(reopened.get("commit_decision"))
            self.assertIsNone(ensure_push_retry_confirmable(data, jid, user_id="other"))

    def test_finalize_push_retry_with_empty_synced_files(self):
        with tempfile.TemporaryDirectory() as td:
            data = Path(td)
            ws = data / "proj"
            ws.mkdir()
            now = int(time.time())
            jid = "ldj-empty-push"
            job_store.write_job_document(
                data,
                {
                    "id": jid,
                    "user_id": "u1",
                    "workspace": str(ws),
                    "status": "awaiting_commit",
                    "runtime": "commit_batch",
                    "synced_files": [],
                    "commit_gate": {"can_commit": True, "work_branch": "dev/wb/t"},
                    "commit_result": {
                        "ok": True,
                        "commit": "abc123",
                        "branch": "dev/wb/t",
                        "message": "测试：更新文件",
                        "files": ["LoginView.vue"],
                        "push": {"ok": False, "error": "timeout"},
                    },
                    "messages": [],
                    "created_at": now,
                    "updated_at": now,
                },
            )
            fake = {
                "ok": True,
                "skipped": True,
                "commit": "abc123",
                "branch": "dev/wb/t",
                "files": [],
                "message": "push only",
                "push": {"ok": True, "remote": "origin"},
            }
            with mock.patch("local_dev.batch_commit.commit_synced_files", return_value=fake):
                out = finalize_commit_batch(
                    data,
                    jid,
                    "commit",
                    push=True,
                    commit_message="测试：更新文件",
                )
            self.assertTrue(out.get("ok"))
            self.assertTrue(out["commit_result"]["push"]["ok"])


if __name__ == "__main__":
    unittest.main()
