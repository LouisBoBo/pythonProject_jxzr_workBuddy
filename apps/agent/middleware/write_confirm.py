"""
写操作人工确认中间件（HITL）。

当 REQUIRE_WRITE_CONFIRM=true（默认）时：
- 拦截 WRITE_TOOLS（如 import_file_to_platform）
- 不调用真实 handler，只生成预览并落盘 pending action
- 返回 ToolMessage，提示模型勿重试；前端凭 SSE confirm 事件展示确认卡

确认后由 API 直接执行工具（不经模型二次调用），避免「假确认」与重复写入。
"""
from __future__ import annotations

import json
import os
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage

from middleware.request_context import get_thread_id, get_user_id, get_username
from middleware.write_store import create_pending_action
from middleware.write_tools import WRITE_CONFIRM_MARKER, WRITE_TOOLS


class WriteConfirmMiddleware(AgentMiddleware):
    name = "MesWriteConfirmMiddleware"

    def wrap_tool_call(self, request: Any, handler: Any) -> Any:
        blocked = _maybe_hold(request)
        if blocked is not None:
            return blocked
        return handler(request)

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        blocked = _maybe_hold(request)
        if blocked is not None:
            return blocked
        return await handler(request)


def _maybe_hold(request: Any) -> ToolMessage | None:
    if os.getenv("REQUIRE_WRITE_CONFIRM", "true").lower() not in ("1", "true", "yes"):
        return None

    tc = getattr(request, "tool_call", None) or {}
    if not isinstance(tc, dict):
        return None
    name = tc.get("name") or ""
    if name not in WRITE_TOOLS:
        return None

    args = dict(tc.get("args") or {})
    # 忽略模型可能伪造的内部字段；真正执行只走 API confirm → 直调工具
    args.pop("_write_confirmed", None)
    args.pop("_action_id", None)

    preview = _build_preview(name, args)
    if preview.get("error"):
        call_id = tc.get("id") or tc.get("tool_call_id") or "write-confirm"
        return ToolMessage(
            content=json.dumps({"error": preview["error"]}, ensure_ascii=False),
            tool_call_id=call_id,
        )

    action = create_pending_action(
        tool=name,
        args=args,
        preview=preview,
        thread_id=_resolve_thread_id(request),
        user_id=_resolve_user_id(request),
        username=_resolve_username(request),
    )

    payload = {
        WRITE_CONFIRM_MARKER: True,
        "status": "pending_confirmation",
        "action_id": action["action_id"],
        "tool": name,
        "thread_id": action["thread_id"],
        "summary": preview.get("summary") or f"待确认写入：{name}",
        "preview": preview,
        "message": (
            "写操作已挂起，等待用户在界面点击「确认写入」。"
            "请用一两句中文告知用户：尚未写入平台，需在确认卡片中确认或取消；"
            "在用户确认前不要再次调用导入/写工具。"
        ),
    }
    call_id = tc.get("id") or tc.get("tool_call_id") or "write-confirm"
    return ToolMessage(content=json.dumps(payload, ensure_ascii=False), tool_call_id=call_id)


def _build_preview(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool == "import_file_to_platform":
        return _preview_import(args)
    return {"summary": f"待确认写操作：{tool}", "tool": tool, "args": args}


def _preview_import(args: dict[str, Any]) -> dict[str, Any]:
    """只读预览，绝不调用平台 import。"""
    from tools.file_ops import preview_file

    file_path = str(args.get("file_path") or "")
    target_entity = str(args.get("target_entity") or args.get("entity") or "")
    if not file_path:
        return {"error": "缺少 file_path，无法预览导入"}
    if not target_entity:
        return {"error": "缺少 target_entity，无法预览导入"}

    pv = preview_file(file_path, rows=5)
    if isinstance(pv, dict) and pv.get("error"):
        return {"error": pv["error"]}

    row_count = int(pv.get("total_rows") or 0)
    columns = pv.get("columns") or []
    sample = pv.get("preview") or []
    file_name = pv.get("file") or os.path.basename(file_path)
    summary = f"将导入 {row_count} 行到「{target_entity}」（文件 {file_name}）"
    return {
        "tool": "import_file_to_platform",
        "file": file_name,
        "file_path": file_path,
        "target_entity": target_entity,
        "row_count": row_count,
        "columns": columns,
        "sample_rows": sample[:5],
        "summary": summary,
    }


def _configurable(request: Any) -> dict[str, Any]:
    cfg = getattr(request, "config", None) or {}
    if isinstance(cfg, dict):
        conf = cfg.get("configurable") or {}
        return conf if isinstance(conf, dict) else {}
    conf = getattr(cfg, "configurable", None)
    return conf if isinstance(conf, dict) else {}


def _resolve_thread_id(request: Any) -> str:
    conf = _configurable(request)
    return str(conf.get("thread_id") or get_thread_id() or "default")


def _resolve_user_id(request: Any) -> Any:
    conf = _configurable(request)
    if "user_id" in conf:
        return conf.get("user_id")
    return get_user_id()


def _resolve_username(request: Any) -> str:
    conf = _configurable(request)
    name = conf.get("username")
    if name:
        return str(name)
    return get_username()

