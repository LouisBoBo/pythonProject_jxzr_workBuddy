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
        assert any(e.get("type") == "pr" for e in events), events
        token_texts = [e.get("text") for e in events if e.get("type") == "token"]
        assert token_texts == [FakeResult.result], token_texts  # 流式+wait 不得重复推全文
        refreshed = get_job(data, job["id"])
        assert refreshed["pr_url"] and "pull/1" in refreshed["pr_url"]

    # 增量合并：累计快照只推 delta
    from cursor_dev.service import _merge_assistant_delta  # noqa: E402

    full, d1 = _merge_assistant_delta("", "hello")
    assert (full, d1) == ("hello", "hello")
    full, d2 = _merge_assistant_delta(full, "hello world")
    assert (full, d2) == ("hello world", " world")
    full, d3 = _merge_assistant_delta(full, "hello world")
    assert d3 == ""

    sys.path.insert(0, str(ROOT / "apps" / "api"))
    from routes import cursor_dev as cd_routes  # noqa: E402

    paths = {getattr(r, "path", "") for r in cd_routes.router.routes}
    assert any("/jobs/{job_id}/stream" in p for p in paths), paths

    print("smoke_cursor_dev_d5: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
