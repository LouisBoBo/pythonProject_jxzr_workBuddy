"""
实体守卫中间件（可选）：拦一批「明显选错实体」的查询。

策略见 entity_guard_rules.guard_mismatch_tip。
默认关闭（ENABLE_ENTITY_GUARD=true 才启用），避免误伤模糊说法。
"""
from __future__ import annotations

from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage

from middleware.entity_guard_rules import GUARD_TOOLS, guard_mismatch_tip


class EntityGuardMiddleware(AgentMiddleware):
    name = "MesEntityGuardMiddleware"

    def wrap_tool_call(self, request: Any, handler: Any) -> Any:
        blocked = _maybe_block(request)
        if blocked is not None:
            return blocked
        return handler(request)

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        blocked = _maybe_block(request)
        if blocked is not None:
            return blocked
        return await handler(request)


def _maybe_block(request: Any) -> ToolMessage | None:
    tc = getattr(request, "tool_call", None) or {}
    if not isinstance(tc, dict):
        return None
    name = tc.get("name") or ""
    if name not in GUARD_TOOLS:
        return None

    args = tc.get("args") or {}
    entity = str(args.get("entity") or args.get("target_entity") or "")
    user_text = _latest_user_text(request)
    tip = guard_mismatch_tip(entity, user_text)
    if not tip:
        return None
    call_id = tc.get("id") or tc.get("tool_call_id") or "entity-guard"
    return ToolMessage(content=tip, tool_call_id=call_id)


def _latest_user_text(request: Any) -> str:
    state = getattr(request, "state", None) or {}
    messages = state.get("messages") if isinstance(state, dict) else None
    if not messages:
        return ""
    for msg in reversed(list(messages)):
        role = getattr(msg, "type", None) or getattr(msg, "role", None)
        if role in ("human", "user"):
            content = getattr(msg, "content", "")
            return content if isinstance(content, str) else str(content)
    return ""
