"""D5：service 事件映射 + stream 路由可导入（不强制 LIVE Cloud）。"""
from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps"))

from cursor_dev.jobs import create_job, get_job  # noqa: E402
from cursor_dev.prompts import build_first_turn_prompt  # noqa: E402
from cursor_dev.service import run_job  # noqa: E402


def main() -> int:
    prompt = build_first_turn_prompt(
        user_message="给 README 加一行 Smoke D5",
        repo="owner/sandbox",
        work_branch="dev/wb/smoke",
        base_ref="hebo",
        create_pr=False,
    )
    events: list[dict] = []

    class FakeResult:
        status = "finished"
        result = "已更新 README。https://github.com/owner/sandbox/pull/1"
        id = "run-1"

    class FakeAssistantMsg:
        type = "assistant"

        class _Msg:
            content = [types.SimpleNamespace(type="text", text=FakeResult.result)]

        message = _Msg()

    class FakeRun:
        id = "run-1"

        def stream(self):
            yield FakeAssistantMsg()

        def messages(self):
            return self.stream()

        def wait(self):
            return FakeResult()

    class FakeAgent:
        agent_id = "bc-smoke"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def send(self, _prompt):
            return FakeRun()

    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp)
        job = create_job(
            data,
            user_id="1",
            username="tester",
            thread_id="t1",
            repo="owner/sandbox",
            ref="hebo",
            message="给 README 加一行 Smoke D5",
            create_pr=False,
            system_prompt=prompt,
        )

        fake_cfg = MagicMock()
        fake_cfg.availability.return_value = (True, "")
        fake_cfg.model = "composer-2.5"
        fake_cfg.api_key = "test-key"
        fake_cfg.starting_ref = "hebo"
        fake_cfg.auto_pr = True
        fake_cfg.skip_reviewer_request = True
        fake_cfg.starting_ref = "hebo"
        fake_cfg.branch_prefix = "dev/workbuddy-"

        fake_mod = types.ModuleType("cursor_sdk")
        fake_mod.Agent = type(
            "Agent",
            (),
            {"create": staticmethod(lambda **kwargs: FakeAgent())},
        )
        fake_mod.AgentOptions = object
        fake_mod.CloudAgentOptions = lambda **kw: types.SimpleNamespace(**kw)
        fake_mod.CloudRepository = lambda **kw: types.SimpleNamespace(**kw)
        fake_mod.CursorAgentError = type("CursorAgentError", (Exception,), {})

        with patch.dict(sys.modules, {"cursor_sdk": fake_mod}), patch(
            "cursor_dev.github_preflight.resolve_starting_ref",
            return_value={
                "ok": True,
                "ref": "hebo",
                "sha": "abc123",
                "default_branch": "hebo",
                "error": None,
            },
        ):
            out = run_job(data, job, sink=events.append, cfg=fake_cfg)

        assert out["status"] == "idle_for_followup", out
        assert out.get("agent_id") == "bc-smoke"
        types_seen = {e.get("type") for e in events}
        assert "status" in types_seen and "done" in types_seen, events
        assert "replace_text" in types_seen, events
        assert "merge_guide" in types_seen, events
        # 未勾选开 PR：不应留下成功态 pr 事件；job.pr_url 为空
        assert not any(e.get("type") == "pr" for e in events), events
        done_ev = next(e for e in events if e.get("type") == "done")
        assert done_ev.get("pr_url") in (None, "")
        mg = done_ev.get("merge_guide") or {}
        assert mg.get("merged_to_main") is False
        assert mg.get("work_branch")
        assert mg.get("compare_url") or mg.get("branch_url")
        token_texts = [e.get("text") for e in events if e.get("type") == "token"]
        assert token_texts[0] == FakeResult.result, token_texts  # 首段流式正文
        # wait() 不得再推同一全文 token（允许随后的「误开 PR」提示）
        assert token_texts.count(FakeResult.result) == 1, token_texts
        refreshed = get_job(data, job["id"])
        assert not refreshed.get("pr_url"), refreshed

    # 增量合并：累计快照只推 delta
    from cursor_dev.service import (  # noqa: E402
        _finalize_assistant_summary,
        _merge_assistant_delta,
        _strip_merge_guidance_from_summary,
    )

    full, d1, r1 = _merge_assistant_delta("", "hello")
    assert (full, d1, r1) == ("hello", "hello", False)
    full, d2, r2 = _merge_assistant_delta(full, "hello world")
    assert (full, d2, r2) == ("hello world", " world", False)
    full, d3, r3 = _merge_assistant_delta(full, "hello world")
    assert d3 == "" and r3 is False

    # 过程旁白 + 终稿 → 整段替换，禁止拼接
    chatter = "正在提交并推送到 `"
    report = "## 已完成\n\n在固定工作分支 **`hebo`** 上实现了登录页。"
    full, d, replaced = _merge_assistant_delta(chatter, report)
    assert replaced and full == report and d == ""

    messy = (
        "正在提交并推送到 `## 已完成\n\n短稿\n\n## 已完成\n\n"
        "在固定工作分支 **`hebo`** 上实现了登录页「企业编码」下拉选择，并已 push。\n\n"
        "### 改动说明\n\n**前端**\n- LoginView\n\n### 验收方式\n1. 可见下拉框\n"
    )
    cleaned = _finalize_assistant_summary(messy)
    assert cleaned.startswith("## 已完成"), cleaned[:80]
    assert "正在提交" not in cleaned
    assert cleaned.count("## 已完成") == 1
    assert "企业编码" in cleaned
    assert "验收" in cleaned

    # 合入指引卡存在时：正文去掉 push/合入尾巴，避免与卡片重复
    with_tail = (
        "## 已完成\n\n- `8abeb5c` fix(login): 企业编码默认选中\n\n"
        "代码已 push 至 origin/hebo 。如需合入 main，请本地自行合并。"
    )
    stripped = _strip_merge_guidance_from_summary(with_tail)
    assert "8abeb5c" in stripped
    assert "push" not in stripped.lower()
    assert "合入 main" not in stripped

    sys.path.insert(0, str(ROOT / "apps" / "api"))
    from routes import cursor_dev as cd_routes  # noqa: E402

    paths = {getattr(r, "path", "") for r in cd_routes.router.routes}
    assert any("/jobs/{job_id}/stream" in p for p in paths), paths

    print("smoke_cursor_dev_d5: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
