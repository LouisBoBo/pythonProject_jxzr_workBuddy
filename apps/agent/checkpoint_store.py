"""Agent 会话 checkpoint：按 thread_id 持久化多轮消息。

流式对话走 astream_events，必须用 AsyncSqliteSaver（同步 SqliteSaver 会直接报错）。
每轮以 UI 历史为真相源同步到 checkpoint（去掉本轮即将写入的 user），
避免「停止生成」后门店有半截回复、Agent 却丢上下文，导致用户说「继续」接不上。
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, RemoveMessage

from config import Config

logger = logging.getLogger(__name__)

_init_lock = asyncio.Lock()
_acheckpointer = None
_aconn = None


def checkpoint_db_path() -> Path:
    raw = (Config.AGENT_CHECKPOINT_PATH or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Config.DATA_DIR / "agent_checkpoints.sqlite").resolve()


async def get_acheckpointer():
    """进程内单例 AsyncSqliteSaver，供 astream_events / ainvoke / aget_state 使用。"""
    global _acheckpointer, _aconn
    if _acheckpointer is not None:
        return _acheckpointer
    async with _init_lock:
        if _acheckpointer is not None:
            return _acheckpointer
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        path = checkpoint_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _aconn = await aiosqlite.connect(str(path))
        try:
            await _aconn.execute("PRAGMA journal_mode=WAL")
            await _aconn.execute("PRAGMA busy_timeout=30000")
            await _aconn.commit()
        except Exception:
            pass
        saver = AsyncSqliteSaver(_aconn)
        await saver.setup()
        _acheckpointer = saver
        logger.info("agent async checkpointer ready: %s", path)
        return _acheckpointer


async def close_acheckpointer() -> None:
    """关闭单例连接（冒烟/测试进程退出用；线上常驻进程一般不调用）。"""
    global _acheckpointer, _aconn
    async with _init_lock:
        saver = _acheckpointer
        conn = _aconn
        _acheckpointer = None
        _aconn = None
        if saver is not None:
            closer = getattr(saver, "aclose", None) or getattr(saver, "close", None)
            if closer is not None:
                try:
                    res = closer()
                    if asyncio.iscoroutine(res):
                        await res
                except Exception:
                    pass
        if conn is not None:
            try:
                await conn.close()
            except Exception:
                pass


def _history_db_path() -> Path:
    return (Config.DATA_DIR / "history" / "conversations.db").resolve()


def load_ui_history_messages(thread_id: str) -> list[BaseMessage]:
    """从前端持久化的 conversations 表读取 user/assistant 正文，转为 LangChain 消息。"""
    tid = (thread_id or "").strip()
    if not tid:
        return []
    db = _history_db_path()
    if not db.is_file():
        return []
    try:
        conn = sqlite3.connect(str(db), timeout=10.0)
        try:
            row = conn.execute(
                "SELECT messages FROM conversations WHERE id = ?", (tid,)
            ).fetchone()
        finally:
            conn.close()
    except Exception as e:
        logger.warning("read ui history failed thread=%s: %s", tid, e)
        return []
    if not row or not row[0]:
        return []
    try:
        raw = json.loads(row[0])
    except Exception:
        return []
    out: list[BaseMessage] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = (item.get("role") or "").strip().lower()
        content = item.get("content")
        if content is None:
            continue
        text = str(content).strip()
        if not text:
            continue
        max_chars = Config.CONTEXT_MAX_CHARS_PER_MSG
        if max_chars > 0 and len(text) > max_chars:
            text = text[:max_chars] + "\n…(已截断)"
        if role in ("user", "human"):
            out.append(HumanMessage(content=text))
        elif role in ("assistant", "ai", "bot"):
            out.append(AIMessage(content=text))
    return out


def _tail_window(messages: list[BaseMessage], max_n: int) -> list[BaseMessage]:
    if max_n <= 0 or len(messages) <= max_n:
        return messages
    return messages[-max_n:]


def _msg_text(m: BaseMessage) -> str:
    c = getattr(m, "content", "")
    if isinstance(c, str):
        return c
    return str(c or "")


def _plain_fingerprint(messages: list[BaseMessage]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for m in messages:
        if isinstance(m, HumanMessage):
            out.append(("human", _msg_text(m)))
        elif isinstance(m, AIMessage):
            out.append(("ai", _msg_text(m)))
    return out


def _drop_trailing_current_user(hist: list[BaseMessage]) -> list[BaseMessage]:
    """UI 在开跑前已写入本轮 user；invoke 还会再写一条，这里先去掉末尾 user。"""
    if hist and isinstance(hist[-1], HumanMessage):
        return hist[:-1]
    return hist


def _update_as_node(agent: Any) -> str:
    """deepagents 图有多节点写 messages，aupdate_state 必须带 as_node。"""
    nodes = getattr(agent, "nodes", None) or {}
    keys = list(nodes.keys()) if hasattr(nodes, "keys") else []
    for preferred in ("model", "agent"):
        if preferred in keys:
            return preferred
    for k in keys:
        if k not in ("__start__", "__end__"):
            return k
    return "model"


async def _replace_checkpoint_messages(
    agent: Any, config: dict[str, Any], keep: list[BaseMessage]
) -> None:
    from langgraph.graph.message import REMOVE_ALL_MESSAGES

    # 整表替换：先清光再写入 UI 窗口（含无 id 的脏消息 / tool 残留）
    ops: list[Any] = [RemoveMessage(id=REMOVE_ALL_MESSAGES), *keep]
    await agent.aupdate_state(
        config, {"messages": ops}, as_node=_update_as_node(agent)
    )


async def ensure_thread_messages(
    agent: Any, thread_id: str, *, run_config: dict[str, Any]
) -> None:
    """用 UI 历史同步 checkpoint（不含本轮 user），并做窗口裁剪。"""
    tid = (thread_id or "").strip() or "default"
    config = run_config
    snap = None
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            snap = await agent.aget_state(config)
            last_err = None
            break
        except Exception as e:
            last_err = e
            logger.warning(
                "aget_state failed thread=%s attempt=%s: %s", tid, attempt + 1, e
            )
            await asyncio.sleep(0.05 * (attempt + 1))
    if snap is None:
        logger.error("aget_state gave up thread=%s: %s", tid, last_err)
        return

    values = getattr(snap, "values", None) or {}
    existing = list(values.get("messages") or [])

    hist = await asyncio.to_thread(load_ui_history_messages, tid)
    hist = _drop_trailing_current_user(hist)
    keep = _tail_window(hist, Config.CONTEXT_MAX_MESSAGES)

    existing_plain = _plain_fingerprint(
        [m for m in existing if isinstance(m, (HumanMessage, AIMessage))]
    )
    keep_plain = _plain_fingerprint(keep)

    # 仅 human/ai 指纹一致时，若夹杂 tool 等其它消息仍整表替换为 UI 对话窗
    non_chat = [
        m
        for m in existing
        if not isinstance(m, (HumanMessage, AIMessage))
    ]
    need_replace = keep_plain != existing_plain or (
        bool(non_chat) and bool(keep_plain)
    )

    if need_replace:
        try:
            await _replace_checkpoint_messages(agent, config, keep)
            logger.info(
                "synced thread=%s checkpoint from ui history msgs=%s "
                "(had_stopped=%s non_chat_dropped=%s)",
                tid,
                len(keep),
                any("已停止生成" in t for _, t in keep_plain),
                len(non_chat) if keep_plain == existing_plain else 0,
            )
        except Exception as e:
            logger.warning("sync checkpoint from ui failed thread=%s: %s", tid, e)
        return

    # 指纹一致且无多余非对话消息：仅按条数裁剪
    if existing and Config.CONTEXT_MAX_MESSAGES > 0:
        n = len(existing)
        max_n = Config.CONTEXT_MAX_MESSAGES
        if n > max_n:
            to_drop = existing[: n - max_n]
            removals = [
                RemoveMessage(id=m.id)
                for m in to_drop
                if getattr(m, "id", None)
            ]
            if removals:
                try:
                    await agent.aupdate_state(
                        config,
                        {"messages": removals},
                        as_node=_update_as_node(agent),
                    )
                    logger.info(
                        "trimmed thread=%s dropped=%s keep<=%s",
                        tid,
                        len(removals),
                        max_n,
                    )
                except Exception as e:
                    logger.warning("trim failed thread=%s: %s", tid, e)
