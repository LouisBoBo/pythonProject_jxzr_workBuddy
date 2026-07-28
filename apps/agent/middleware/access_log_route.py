"""
访问日志路由中间件：拦截对 .jsonl/.log 上传日志的错误工具调用。

Agent 常误用 read_file / ls / transform_file / build_api_catalog 处理访问日志，
而上传目录又不在 FilesystemBackend 虚拟根内。本中间件：
- 识别访问日志路径
- 自动改走 import_external_api_logs，并提示下一步 analyze_api_errors_from_logs
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage

_MISROUTE_TOOLS = frozenset(
    {
        "read_file",
        "ls",
        "glob",
        "grep",
        "transform_file",
        "preview_file",
        "build_api_catalog",
    }
)

_LOG_SUFFIXES = (".jsonl", ".log")


def _tool_call(request: Any) -> tuple[str, dict[str, Any], str]:
    tc = getattr(request, "tool_call", None) or {}
    if not isinstance(tc, dict):
        return "", {}, ""
    name = str(tc.get("name") or "")
    args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
    call_id = str(tc.get("id") or tc.get("tool_call_id") or "access-log-route")
    return name, args, call_id


def _extract_path(name: str, args: dict[str, Any]) -> str:
    for key in ("file_path", "path", "file", "docs_url"):
        v = args.get(key)
        if v:
            return str(v).strip()
    return ""


def _looks_like_access_log(path: str) -> bool:
    if not path:
        return False
    lower = path.lower().replace("\\", "/")
    if lower.endswith(_LOG_SUFFIXES):
        return True
    # 上传目录下的 jsonl/log 变体
    if "/uploads/" in lower or "/data/uploads/" in lower:
        name = Path(lower).name
        if name.endswith(_LOG_SUFFIXES):
            return True
        if "access" in name or "api_access" in name or "nginx" in name:
            return True
    return False


def _reroute_to_import(path: str, *, from_tool: str) -> dict[str, Any]:
    from tools.api_log_tool.api_health import import_external_api_logs

    result = import_external_api_logs(file_path=path, format="auto")
    if not isinstance(result, dict):
        result = {"status": "ok", "raw": result}
    result = dict(result)
    result["_rerouted_from"] = from_tool
    if result.get("error"):
        result["hint"] = (
            result.get("hint")
            or "请确认 [附件路径] 正确；可只传文件名，将在 data/uploads/ 下查找。"
        )
        result["next"] = "import_external_api_logs(file_path=绝对路径或文件名)"
    else:
        result["note"] = (
            f"已拦截误用工具 `{from_tool}`：该文件是访问日志，不是 OpenAPI/表格。"
            "已自动执行 import_external_api_logs。"
            "下一步必须调用 analyze_api_errors_from_logs(source_filter='import')，"
            "并用返回的 report_markdown 回复（只谈本次日志的调用与错误/正常接口；"
            "不要 with_catalog / docs_url，不要把文档接口总数写进报告）。"
            "禁止再调用 read_file / ls / transform_file / build_api_catalog 处理此文件。"
        )
        result["next"] = "analyze_api_errors_from_logs(source_filter='import')"
    return result


class AccessLogRouteMiddleware(AgentMiddleware):
    name = "MesAccessLogRouteMiddleware"

    def wrap_tool_call(self, request: Any, handler: Any) -> Any:
        redirected = _maybe_reroute(request)
        if redirected is not None:
            return redirected
        return handler(request)

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        redirected = _maybe_reroute(request)
        if redirected is not None:
            return redirected
        return await handler(request)


def _maybe_reroute(request: Any) -> ToolMessage | None:
    name, args, call_id = _tool_call(request)
    if name not in _MISROUTE_TOOLS:
        return None
    path = _extract_path(name, args)
    if not _looks_like_access_log(path):
        # build_api_catalog 无 path 时不拦
        return None

    payload = _reroute_to_import(path, from_tool=name)
    return ToolMessage(
        content=json.dumps(payload, ensure_ascii=False, default=str),
        tool_call_id=call_id,
        name=name,
    )
