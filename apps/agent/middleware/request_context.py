"""请求级会话上下文：thread_id / 操作人（供写确认与审计使用）。"""
from __future__ import annotations

import contextvars
from typing import Any

_thread_id: contextvars.ContextVar[str] = contextvars.ContextVar("mes_thread_id", default="default")
_user_id: contextvars.ContextVar[Any] = contextvars.ContextVar("mes_user_id", default=None)
_username: contextvars.ContextVar[str] = contextvars.ContextVar("mes_username", default="")


def set_request_agent_context(
    *,
    thread_id: str | None = None,
    user_id: Any = None,
    username: str | None = None,
) -> tuple[Any, Any, Any]:
    """返回三个 token，供 finally 里 reset。"""
    t1 = _thread_id.set(thread_id or "default")
    t2 = _user_id.set(user_id)
    t3 = _username.set((username or "").strip())
    return t1, t2, t3


def reset_request_agent_context(tokens: tuple[Any, Any, Any]) -> None:
    t1, t2, t3 = tokens
    _thread_id.reset(t1)
    _user_id.reset(t2)
    _username.reset(t3)


def get_thread_id() -> str:
    return _thread_id.get() or "default"


def get_user_id() -> Any:
    return _user_id.get()


def get_username() -> str:
    return _username.get() or ""
