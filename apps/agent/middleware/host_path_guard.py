"""拦截对本机绝对路径的 Filesystem 工具调用。

Deep Agents 的 read_file/ls/glob/grep 绑定 virtual_mode，只能访问 apps/agent。
模型常误读 /Users/.../Desktop 下的 ERP 工程 → File not found / path_not_found。
本中间件短路并返回中文说明，避免过程区堆失败步骤。
"""
from __future__ import annotations

import json
import re
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage

_FS_TOOLS = frozenset({"read_file", "ls", "glob", "grep", "edit_file", "write_file"})

_HOST_ABS_RE = re.compile(
    r"^(?:"
    r"/Users/|"
    r"/home/|"
    r"/Volumes/|"
    r"/private/|"
    r"[A-Za-z]:[/\\]|"  # Windows
    r"\\\\"  # UNC
    r")"
)


def _tool_call(request: Any) -> tuple[str, dict[str, Any], str]:
    tc = getattr(request, "tool_call", None) or {}
    if not isinstance(tc, dict):
        return "", {}, ""
    name = str(tc.get("name") or "")
    args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
    call_id = str(tc.get("id") or tc.get("tool_call_id") or "host-path-guard")
    return name, args, call_id


def _extract_paths(name: str, args: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("file_path", "path", "file", "target_file", "directory"):
        v = args.get(key)
        if v:
            out.append(str(v).strip())
    # glob/grep 的 pattern 若以绝对路径开头也拦
    for key in ("pattern", "glob"):
        v = args.get(key)
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    return [p for p in out if p]


def _is_host_absolute(path: str) -> bool:
    p = (path or "").strip().replace("\\", "/")
    if not p:
        return False
    if _HOST_ABS_RE.match(p):
        return True
    # 少数模型会传 file://
    if p.startswith("file:///Users/") or p.startswith("file:///home/"):
        return True
    return False


def _block_payload(name: str, path: str) -> dict[str, Any]:
    return {
        "status": "error",
        "error": "host_path_blocked",
        "tool": name,
        "path": path,
        "message": (
            f"已拦截：不能用 `{name}` 读本机绝对路径 `{path}`。"
            "服务端虚拟文件系统只能访问 Agent 工作区，读不到 Desktop/本机工程。"
        ),
        "hint": (
            "【写码】默认本机目录：输出 :::cursor_dev_propose（target 缺省 local，可带 workspace 绝对路径），"
            "由确认卡经沙箱同步落盘；不要用本工具直写 /Users。"
            "改 GitHub 仓时 target=github，走 Cursor Cloud。"
            "【审核】请用 request_ide_*（VS Code 配对）或 request_git_*（公开仓）。"
        ),
        "next": "勿重试本机绝对路径；写码用确认卡（本机沙箱或 GitHub），审核用 IDE/Git 工具。",
    }


class HostPathGuardMiddleware(AgentMiddleware):
    name = "MesHostPathGuardMiddleware"

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
    name, args, call_id = _tool_call(request)
    if name not in _FS_TOOLS:
        return None
    for path in _extract_paths(name, args):
        if _is_host_absolute(path):
            payload = _block_payload(name, path)
            return ToolMessage(
                content=json.dumps(payload, ensure_ascii=False, default=str),
                tool_call_id=call_id,
                name=name,
            )
    return None
