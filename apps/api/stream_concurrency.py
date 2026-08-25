"""流式对话并发控制。

原因：进程内 AsyncSqliteSaver 共用单条 aiosqlite 连接，并发 astream 会空流/掐断。
策略：进程内仍串行；抢不到锁时**快速失败**并给出中文说明（避免静默排队像卡死）。
真·多路并发需换可并发 checkpointer（如 Postgres）并评估 Agent 单例，不在本模块范围。
"""
from __future__ import annotations

import asyncio
import os

STREAM_BUSY_CODE = "stream_busy"
STREAM_BUSY_TEXT = (
    "当前已有一路对话在生成。请稍后再发，或先点「停止」结束上一轮。"
    "（本机 API 进程内同时只支持一路流式对话。）"
)


def stream_lock_wait_seconds() -> float:
    """等待锁的秒数；环境变量 WORKBUDDY_STREAM_LOCK_WAIT_SEC，默认 0.15。"""
    raw = (os.environ.get("WORKBUDDY_STREAM_LOCK_WAIT_SEC") or "0.15").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.15


def stream_busy_event() -> dict:
    return {
        "type": "error",
        "code": STREAM_BUSY_CODE,
        "text": STREAM_BUSY_TEXT,
        "error": STREAM_BUSY_TEXT,
    }


async def try_acquire_stream_lock(
    lock: asyncio.Lock,
    wait_sec: float | None = None,
) -> bool:
    """在 wait_sec 内抢到锁返回 True；超时返回 False（调用方勿 release）。"""
    timeout = stream_lock_wait_seconds() if wait_sec is None else max(0.0, float(wait_sec))
    if timeout <= 0:
        if lock.locked():
            return False
        await lock.acquire()
        return True
    try:
        await asyncio.wait_for(lock.acquire(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        return False
