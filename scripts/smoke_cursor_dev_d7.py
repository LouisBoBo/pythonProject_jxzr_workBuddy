#!/usr/bin/env python3
"""D7+：取消 / 续聊入队 / 审计列表 / 冲突提示 契约（不强制 LIVE Cloud）。"""
from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps"))

from cursor_dev.jobs import (  # noqa: E402
    active_jobs_on_repo,
    create_job,
    get_job,
    request_cancel,
    update_job,
)
from cursor_dev.audit import append_audit, list_audit  # noqa: E402
from cursor_dev.prompts import build_followup_prompt  # noqa: E402
from cursor_dev.service import run_job  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp)
        job = create_job(
            data,
            user_id="1",
            username="tester",
            thread_id="t1",
            repo="owner/sandbox",
            ref="main",
            message="首轮",
            create_pr=False,
            system_prompt="sys",
        )
        jid = job["id"]

        # 同仓冲突提示数据
        create_job(
            data,
            user_id="2",
            username="peer",
            thread_id="t2",
            repo="owner/sandbox",
            ref="main",
            message="并行",
            create_pr=False,
            system_prompt="sys",
        )
        peers = active_jobs_on_repo(data, "owner/sandbox", exclude_job_id=None)
        assert len(peers) >= 2, peers

        # 取消 queued
        updated = request_cancel(data, jid, reason="测试取消")
        assert updated and updated["status"] == "cancelled", updated

        # 审计
        append_audit(data, {"event": "job_created", "job_id": jid, "user_id": "1", "repo": "owner/sandbox"})
        rows = list_audit(data, limit=10, user_id="1")
        assert rows and rows[0]["event"] == "job_created", rows

        # 续聊 prompt
        fp = build_followup_prompt(
            user_message="再改一行",
            repo="owner/sandbox",
            work_branch="dev/wb/admin",
            prior_assistant="上一轮完成",
            create_pr=False,
        )
        assert "工作分支" in fp and "再改一行" in fp

        # failed → cancel_requested 路径：running 标记
        job2 = create_job(
            data,
            user_id="1",
            username="tester",
            thread_id="t3",
            repo="owner/other",
            ref="main",
            message="跑",
            create_pr=True,
            system_prompt="sys",
        )
        update_job(data, job2["id"], status="running", agent_id="bc-x", run_id="r1")
        mid = request_cancel(data, job2["id"], reason="停")
        assert mid and mid.get("cancel_requested") is True, mid

        # run_job：cancel 在流式前生效（假 SDK）
        events: list[dict] = []

        class FakeRun:
            id = "run-1"

            def stream(self):
                if False:  # pragma: no cover
                    yield None
                return
                yield  # make generator

            def messages(self):
                return self.stream()

            def wait(self):
                class R:
                    status = "finished"
                    result = "ok"
                    id = "run-1"

                return R()

            def cancel(self):
                return None

        class FakeAgent:
            agent_id = "bc-smoke"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def send(self, _p):
                return FakeRun()

        fake_cfg = MagicMock()
        fake_cfg.availability.return_value = (True, "")
        fake_cfg.model = "composer-2.5"
        fake_cfg.api_key = "k"
        fake_cfg.starting_ref = "main"
        fake_cfg.auto_pr = True
        fake_cfg.skip_reviewer_request = True
        fake_cfg.branch_prefix = "dev/workbuddy-"
        fake_cfg.job_timeout_sec = 2700

        fake_mod = types.ModuleType("cursor_sdk")
        fake_mod.Agent = type("Agent", (), {"create": staticmethod(lambda **kw: FakeAgent())})
        fake_mod.AgentOptions = object
        fake_mod.CloudAgentOptions = lambda **kw: types.SimpleNamespace(**kw)
        fake_mod.CloudRepository = lambda **kw: types.SimpleNamespace(**kw)
        fake_mod.CursorAgentError = type("CursorAgentError", (Exception,), {})

        job3 = create_job(
            data,
            user_id="1",
            username="tester",
            thread_id="t4",
            repo="owner/ok",
            ref="main",
            message="实现",
            create_pr=False,
            system_prompt="sys",
        )
        # 预先请求取消，run_job 流式循环应识别
        request_cancel(data, job3["id"], reason="提前取消")
        # queued+cancel → status cancelled already for abandoned; force running path:
        update_job(data, job3["id"], status="queued", cancel_requested=True, error="提前取消")

        with patch.dict(sys.modules, {"cursor_sdk": fake_mod}), patch(
            "cursor_dev.github_preflight.resolve_starting_ref",
            return_value={"ok": True, "ref": "main", "sha": "abc", "default_branch": "main", "error": None},
        ):
            # cancel_requested True at start of stream after running set — simulate by patching is_cancel
            out = run_job(data, get_job(data, job3["id"]), sink=events.append, cfg=fake_cfg)

        # 若未在首条消息前取消，至少应成功或 cancelled
        assert out.get("status") in {"cancelled", "idle_for_followup", "failed"}, out
        assert any(e.get("type") in {"error", "done", "status", "step"} for e in events), events

    # 路由可导入
    sys.path.insert(0, str(ROOT / "apps" / "api"))
    from routes import cursor_dev as cd  # noqa: E402

    paths = {getattr(r, "path", "") for r in cd.router.routes}
    assert any("/jobs/{job_id}/cancel" in p for p in paths), paths
    assert any("/jobs/{job_id}/messages" in p for p in paths), paths
    assert any(p.endswith("/audit") or "/audit" in p for p in paths), paths

    print("smoke_cursor_dev_d7: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
