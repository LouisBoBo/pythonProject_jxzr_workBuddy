#!/usr/bin/env python3
"""无 LLM：嵌入身份 / 历史归属 / 页上下文前缀冒烟。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
AGENT = ROOT / "apps" / "agent"
sys.path.insert(0, str(API))
sys.path.insert(0, str(AGENT))


def _fail(name: str, detail: str) -> None:
    print(f"FAIL {name}: {detail}")
    raise SystemExit(1)


def _ok(name: str) -> None:
    print(f"OK   {name}")


def test_history_ownership() -> None:
    from routes.auth import UserInfo
    from routes.history import _owned_by

    class Row(dict):
        def keys(self):
            return super().keys()

        def __getitem__(self, k):
            return super().__getitem__(k)

    alice = UserInfo(username="alice", user_id="1")
    bob = UserInfo(username="bob", user_id="2")
    row_a = Row(user_id="1", username="alice")
    row_b = Row(user_id="2", username="bob")
    legacy = Row(user_id="", username="")

    if not _owned_by(row_a, alice):
        _fail("own_alice", "alice should own her row")
    if _owned_by(row_a, bob):
        _fail("leak_bob", "bob must not own alice row")
    if _owned_by(row_b, alice):
        _fail("leak_alice", "alice must not own bob row")
    # 升级前无主会话：已登录用户可见（避免历史消失），再由 list 认领
    if not _owned_by(legacy, alice):
        _fail("legacy", "logged-in user should see unowned legacy rows")
    _ok("history ownership")


def test_page_context_prefix() -> None:
    from middleware.request_context import (
        reset_request_agent_context,
        set_request_agent_context,
    )
    from agent_wrapper import AgentRunner

    tokens = set_request_agent_context(
        thread_id="session-alice-1",
        user_id="1",
        username="alice",
        page_context={"entity": "production-plans", "plan_no": "PP-0801"},
    )
    try:
        msg = AgentRunner._build_message(AgentRunner.__new__(AgentRunner), "这个计划怎样？")
        if "[平台上下文]" not in msg or "PP-0801" not in msg:
            _fail("page_ctx", msg[:120])
        if not msg.endswith("这个计划怎样？") and "这个计划怎样？" not in msg:
            _fail("page_ctx_body", msg)
    finally:
        reset_request_agent_context(tokens)
    _ok("page context prefix")


def test_thread_default_rewrite_logic() -> None:
    # 与 chat 路由一致的轻量逻辑
    def rewrite(thread_id: str, username: str) -> str:
        tid = (thread_id or "").strip() or f"session-{(username or 'anon')}"
        if tid == "default" and username:
            tid = f"session-{username}"
        return tid

    if rewrite("default", "admin") != "session-admin":
        _fail("rewrite", rewrite("default", "admin"))
    if rewrite("session-admin-1", "admin") != "session-admin-1":
        _fail("keep", "should keep explicit thread")
    _ok("thread_id rewrite")


def main() -> None:
    test_history_ownership()
    test_thread_default_rewrite_logic()
    test_page_context_prefix()
    print("SMOKE_OK embed-identity")


if __name__ == "__main__":
    main()
