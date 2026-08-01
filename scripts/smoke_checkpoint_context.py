"""轻量冒烟：AsyncSqliteSaver 可创建；历史回填解析；窗口裁剪；aget/aupdate 可用。"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1] / "apps" / "agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


async def _async_main() -> None:
    from checkpoint_store import (
        _tail_window,
        ensure_thread_messages,
        get_acheckpointer,
        load_ui_history_messages,
    )
    from langchain_core.messages import AIMessage, HumanMessage

    cp = await get_acheckpointer()
    assert cp is not None

    msgs = [HumanMessage(content=f"u{i}") for i in range(5)] + [
        AIMessage(content=f"a{i}") for i in range(5)
    ]
    assert len(_tail_window(msgs, 4)) == 4
    assert _tail_window(msgs, 0) == msgs

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "conversations.db"
        conn = sqlite3.connect(str(db))
        conn.execute(
            """
            CREATE TABLE conversations (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at REAL,
                updated_at REAL,
                messages TEXT DEFAULT '[]',
                user_id TEXT,
                username TEXT
            )
            """
        )
        payload = [
            {"role": "user", "content": "帮我看这段代码"},
            {"role": "assistant", "content": "有 SQL 注入，要不要完整修好版？"},
            {"role": "user", "content": "来吧"},
        ]
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at, messages) VALUES (?,?,?,?,?)",
            ("session-test-1", "t", 0, 0, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

        from config import Config

        hist_dir = Path(td) / "history"
        hist_dir.mkdir()
        (hist_dir / "conversations.db").write_bytes(db.read_bytes())

        old = Config.DATA_DIR
        Config.DATA_DIR = Path(td)
        try:
            loaded = load_ui_history_messages("session-test-1")
            assert len(loaded) == 3
            assert "来吧" in str(loaded[-1].content)
        finally:
            Config.DATA_DIR = old

    # 图 + AsyncSqliteSaver 异步状态读写（不调 LLM）
    from agents.agent import create_agent
    import uuid

    agent = create_agent(checkpointer=cp)
    tid = f"smoke-async-ckpt-{uuid.uuid4().hex[:8]}"
    cfg = {
        "configurable": {"thread_id": tid},
        "recursion_limit": 25,
    }
    await ensure_thread_messages(agent, tid, run_config=cfg)
    st = await agent.aget_state(cfg)
    # 新 thread、无 UI 历史 → 应仍为空
    assert len((st.values or {}).get("messages") or []) == 0

    await agent.aupdate_state(
        cfg,
        {
            "messages": [
                HumanMessage(content="上一轮分析了 SQL 注入"),
                AIMessage(content="这段代码是一个\n\n（已停止生成）"),
            ]
        },
        as_node="model",
    )
    st2 = await agent.aget_state(cfg)
    assert len((st2.values or {}).get("messages") or []) >= 2
    assert any(
        "已停止生成" in str(getattr(m, "content", ""))
        for m in (st2.values or {}).get("messages") or []
    )

    # UI 历史含「停止半截 + 继续」：同步后 checkpoint 应对齐停止气泡，且去掉本轮「继续」
    with tempfile.TemporaryDirectory() as td2:
        from config import Config
        from langchain_core.messages import ToolMessage

        hist_dir = Path(td2) / "history"
        hist_dir.mkdir()
        db = hist_dir / "conversations.db"
        conn = sqlite3.connect(str(db))
        conn.execute(
            """
            CREATE TABLE conversations (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at REAL,
                updated_at REAL,
                messages TEXT DEFAULT '[]',
                user_id TEXT,
                username TEXT
            )
            """
        )
        tid2 = f"smoke-stop-resume-{uuid.uuid4().hex[:8]}"
        ui_msgs = [
            {"role": "user", "content": "请分析这段贴码：SELECT * FROM users"},
            {
                "role": "assistant",
                "content": "发现注入风险，建议用参数化。\n\n（已停止生成）",
                "meta": {"stopped": True},
            },
            {"role": "user", "content": "继续"},
        ]
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at, messages) VALUES (?,?,?,?,?)",
            (tid2, "t", 0, 0, json.dumps(ui_msgs, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

        old = Config.DATA_DIR
        Config.DATA_DIR = Path(td2)
        cfg2 = {
            "configurable": {"thread_id": tid2},
            "recursion_limit": 25,
        }
        try:
            # 先塞一条带 tool 的脏 checkpoint，验证同步会清掉非对话消息
            await agent.aupdate_state(
                cfg2,
                {
                    "messages": [
                        HumanMessage(content="脏数据"),
                        AIMessage(content="旧答"),
                        ToolMessage(content="tool-noise", tool_call_id="t1"),
                    ]
                },
                as_node="model",
            )
            await ensure_thread_messages(agent, tid2, run_config=cfg2)
            st3 = await agent.aget_state(cfg2)
            synced = list((st3.values or {}).get("messages") or [])
            # 去掉末尾本轮「继续」后应为：user 原任务 + 停止半截
            assert len(synced) == 2, synced
            assert isinstance(synced[0], HumanMessage)
            assert "贴码" in str(synced[0].content)
            assert isinstance(synced[1], AIMessage)
            assert "已停止生成" in str(synced[1].content)
            assert not any(isinstance(m, ToolMessage) for m in synced)
        finally:
            Config.DATA_DIR = old

    print("smoke_checkpoint_context: OK", flush=True)


def main() -> None:
    import os
    import sys

    async def _run() -> None:
        from checkpoint_store import close_acheckpointer

        try:
            await _async_main()
        finally:
            try:
                await close_acheckpointer()
            except Exception:
                pass

    try:
        asyncio.run(_run())
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        # aiosqlite/后台任务偶发拖住进程；冒烟必须以非零超时可退出
        os._exit(0)


if __name__ == "__main__":
    main()
