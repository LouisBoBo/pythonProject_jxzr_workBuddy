"""
工具调用审计中间件：在每次 Tool 调用前后打日志。

适合：排障、统计「Agent 实际调了哪些实体」、合规留痕。
"""
from __future__ import annotations

import logging
import time
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware

logger = logging.getLogger("mes.agent.audit")


class AuditToolMiddleware(AgentMiddleware):
    """记录 tool 名称、关键参数摘要与耗时。"""

    # 自定义 name，避免与 Deep Agents 内置中间件重名冲突
    name = "MesAuditToolMiddleware"

    def wrap_tool_call(self, request: Any, handler: Any) -> Any:
        tool_name = getattr(request, "tool_call", None) or {}
        if isinstance(tool_name, dict):
            name = tool_name.get("name", "?")
            args = tool_name.get("args") or {}
        else:
            # 兼容不同 request 形态
            name = getattr(request, "name", None) or getattr(request, "tool_name", "?")
            args = getattr(request, "args", None) or getattr(request, "tool_input", {}) or {}

        summary = _brief_args(args)
        t0 = time.perf_counter()
        logger.info("tool_start name=%s args=%s", name, summary)
        try:
            result = handler(request)
            ms = (time.perf_counter() - t0) * 1000
            logger.info("tool_ok name=%s duration_ms=%.1f", name, ms)
            return result
        except Exception:
            ms = (time.perf_counter() - t0) * 1000
            logger.exception("tool_fail name=%s duration_ms=%.1f", name, ms)
            raise

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        tool_name = getattr(request, "tool_call", None) or {}
        if isinstance(tool_name, dict):
            name = tool_name.get("name", "?")
            args = tool_name.get("args") or {}
        else:
            name = getattr(request, "name", None) or getattr(request, "tool_name", "?")
            args = getattr(request, "args", None) or getattr(request, "tool_input", {}) or {}

        summary = _brief_args(args)
        t0 = time.perf_counter()
        logger.info("tool_start name=%s args=%s", name, summary)
        try:
            result = await handler(request)
            ms = (time.perf_counter() - t0) * 1000
            logger.info("tool_ok name=%s duration_ms=%.1f", name, ms)
            return result
        except Exception:
            ms = (time.perf_counter() - t0) * 1000
            logger.exception("tool_fail name=%s duration_ms=%.1f", name, ms)
            raise


def _brief_args(args: Any) -> str:
    if not isinstance(args, dict):
        return str(args)[:120]
    keys = ("entity", "target_entity", "file_path", "filters", "limit", "output_format")
    parts = [f"{k}={args.get(k)!r}" for k in keys if k in args]
    extra = [k for k in args if k not in keys]
    if extra:
        parts.append(f"+{len(extra)}keys")
    return "{" + ", ".join(parts) + "}"
