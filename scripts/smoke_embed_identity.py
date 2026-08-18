#!/usr/bin/env python3
"""无 LLM：嵌入身份 / 历史归属 / 页上下文前缀冒烟。"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
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


def _fake_jwt(*, sub: str, username: str | None = None, exp_offset: int = 3600) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    payload_obj: dict = {"sub": sub, "exp": int(time.time()) + exp_offset}
    if username is not None:
        payload_obj["username"] = username
    payload = base64.urlsafe_b64encode(json.dumps(payload_obj).encode()).decode().rstrip("=")
    return f"{header}.{payload}.x"


def test_history_ownership() -> None:
    from routes.auth import UserInfo
    from routes.history import _owned_by, _strict_owned_by

    class Row(dict):
        def keys(self):
            return super().keys()

        def __getitem__(self, k):
            return super().__getitem__(k)

    alice = UserInfo(username="alice", user_id="1")
    bob = UserInfo(username="bob", user_id="2")
    # 有效 token 属 alice，但伪造用户名 bob —— 不得靠用户名打开 bob 的已归属会话
    spoof = UserInfo(username="bob", user_id="1")
    row_a = Row(user_id="1", username="alice")
    row_b = Row(user_id="2", username="bob")
    legacy = Row(user_id="", username="")

    if not _strict_owned_by(row_a, alice):
        _fail("own_alice", "alice should own her row")
    if _strict_owned_by(row_a, bob):
        _fail("leak_bob", "bob must not own alice row")
    if _strict_owned_by(row_b, alice):
        _fail("leak_alice", "alice must not own bob row")
    if _strict_owned_by(row_b, spoof):
        _fail("spoof_uname", "user_id=1 + username=bob must not own bob's row")
    # 列表：无主不可见
    if _strict_owned_by(legacy, alice):
        _fail("list_legacy", "unowned must not appear in strict list ownership")
    # 已知 thread_id：可认领
    if not _owned_by(legacy, alice, allow_legacy_claim=True):
        _fail("claim_legacy", "known-id claim should allow unowned")
    if _owned_by(legacy, alice, allow_legacy_claim=False):
        _fail("no_claim", "without claim flag unowned must be denied")
    _ok("history ownership")


def test_require_auth_jwt_first() -> None:
    from routes import auth as auth_mod
    from session_jwt import issue_session_jwt

    prev = auth_mod.AUTH_REQUIRED
    prev_secret = os.environ.get("WORKBUDDY_JWT_SECRET")
    os.environ["WORKBUDDY_JWT_SECRET"] = "smoke-embed-jwt"
    auth_mod.AUTH_REQUIRED = True
    try:
        token, _exp = issue_session_jwt(user_id="42", username="from-jwt")
        _, user = auth_mod.require_auth(
            authorization=f"Bearer {token}",
            x_user_name="spoofed-header",
        )
        if str(user.user_id) != "42":
            _fail("jwt_sub", f"user_id={user.user_id}")
        if user.username != "from-jwt":
            _fail("jwt_name", f"username={user.username} (header must not win)")

        token2, _exp2 = issue_session_jwt(user_id="7", username="")
        _, user2 = auth_mod.require_auth(
            authorization=f"Bearer {token2}",
            x_user_name="login-user",
        )
        if user2.username != "user-7":
            _fail("jwt_default_name", f"expected user-7 got {user2.username}")
        if str(user2.user_id) != "7":
            _fail("jwt_sub2", f"user_id={user2.user_id}")

        fake = _fake_jwt(sub="99", username="forged")
        try:
            auth_mod.require_auth(authorization=f"Bearer {fake}", x_user_name="x")
            _fail("alg_none", "unsigned JWT must be rejected")
        except Exception as exc:
            if "401" not in str(exc) and "无效" not in str(exc) and "过期" not in str(exc):
                # HTTPException str 可能不含中文，至少不能成功返回
                from fastapi import HTTPException

                if not isinstance(exc, HTTPException) or exc.status_code != 401:
                    _fail("alg_none_exc", str(exc))
    finally:
        auth_mod.AUTH_REQUIRED = prev
        if prev_secret is None:
            os.environ.pop("WORKBUDDY_JWT_SECRET", None)
        else:
            os.environ["WORKBUDDY_JWT_SECRET"] = prev_secret
    _ok("require_auth jwt-first")


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
    test_require_auth_jwt_first()
    test_thread_default_rewrite_logic()
    test_page_context_prefix()
    print("SMOKE_OK embed-identity")


if __name__ == "__main__":
    main()
