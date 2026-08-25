"""对话 SSE 防代理攒包：可配置填充与短延迟。

历史硬编码 2048 空格 + sleep(0.04) 带宽/延迟浪费大。
默认改为较小填充 + 仅 yield 事件循环（sleep 0）；遇顽固代理可调环境变量恢复。
"""
from __future__ import annotations

import os

# 过程事件（status/step/confirm）需要额外冲刷，避免与后续 token 被代理并包
PROCESS_EVENT_TYPES = frozenset({"status", "step", "confirm"})


def sse_pad_bytes() -> int:
    raw = (os.environ.get("WORKBUDDY_SSE_PAD_BYTES") or "512").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 512


def sse_flush_sleep_sec() -> float:
    """过程事件后额外 sleep；默认 0（仅依赖 await sleep(0) 让出事件循环）。"""
    raw = (os.environ.get("WORKBUDDY_SSE_FLUSH_SLEEP_SEC") or "0").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.0


def sse_comment_pad(pad_bytes: int | None = None) -> str:
    """SSE 注释行填充，用于冲掉代理/内核缓冲。"""
    n = sse_pad_bytes() if pad_bytes is None else max(0, int(pad_bytes))
    if n <= 0:
        return ":\n\n"
    return ": " + (" " * n) + "\n\n"


def needs_process_flush(event_type: object) -> bool:
    return str(event_type or "") in PROCESS_EVENT_TYPES
