"""
实体守卫中间件（可选）：拦一批「明显选错实体」的查询。

示例策略：当 tool 为 query_platform_data / describe_entity / export_platform_data，
且用户消息里出现「生产计划/排产/排程」，却传了 work-orders → 直接返回错误提示，
迫使 Agent 改用 production-plans。

默认关闭（ENABLE_ENTITY_GUARD=true 才启用），避免误伤模糊说法。
"""
from __future__ import annotations

from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage

_PLAN_HINTS = ("生产计划", "排产", "排程", "production-plan", "production plan")
_GUARD_TOOLS = {
    "query_platform_data",
    "describe_entity",
    "export_platform_data",
    "import_file_to_platform",
}


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
    if name not in _GUARD_TOOLS:
        return None

    args = tc.get("args") or {}
    entity = str(args.get("entity") or args.get("target_entity") or "")
    if entity != "work-orders":
        return None

    # 从 state 里取最近用户话（若 request 带 state）
    user_text = _latest_user_text(request)
    if not user_text:
        return None
    if not any(h in user_text for h in _PLAN_HINTS):
        return None

    tip = (
        "实体守卫：用户在问生产计划/排产/排程，但工具参数用了 work-orders。"
        "请改用 entity='production-plans' 后重试，不要用工单数据充数。"
    )
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
