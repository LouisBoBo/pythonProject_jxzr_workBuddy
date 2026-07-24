"""
历史记录接口：会话持久化（SQLite 本地存储）。
"""
import json
import os
import sqlite3
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import sys, os
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from routes_config import HISTORY_DIR
from routes.auth import require_auth

router = APIRouter(prefix="/api", tags=["history"])

os.makedirs(HISTORY_DIR, exist_ok=True)
DB_PATH = os.path.join(HISTORY_DIR, "conversations.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at REAL,
            updated_at REAL,
            messages TEXT DEFAULT '[]'
        )
    """)
    conn.commit()
    return conn


class SaveRequest(BaseModel):
    thread_id: str
    title: str | None = None
    messages: list[dict] = []


@router.get("/history")
async def list_history(limit: int = 50, _auth: tuple = Depends(require_auth)):
    """获取历史会话列表，按更新时间倒序。"""
    db = get_db()
    rows = db.execute(
        "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    db.close()
    return [
        {
            "id": r["id"],
            "title": r["title"] or "未命名会话",
            "created_at": datetime.fromtimestamp(r["created_at"]).isoformat(),
            "updated_at": datetime.fromtimestamp(r["updated_at"]).isoformat(),
        }
        for r in rows
    ]


@router.get("/history/{thread_id}")
async def get_history(thread_id: str, _auth: tuple = Depends(require_auth)):
    """获取某次会话的完整对话记录。"""
    db = get_db()
    row = db.execute(
        "SELECT * FROM conversations WHERE id = ?", (thread_id,)
    ).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "id": row["id"],
        "title": row["title"],
        "created_at": datetime.fromtimestamp(row["created_at"]).isoformat(),
        "updated_at": datetime.fromtimestamp(row["updated_at"]).isoformat(),
        "messages": json.loads(row["messages"]),
    }


@router.post("/history/save")
async def save_history(req: SaveRequest, _auth: tuple = Depends(require_auth)):
    """保存或更新会话记录。"""
    now = time.time()
    db = get_db()
    # 自动提取标题：取第一条用户消息的前 30 字
    title = req.title
    if not title and req.messages:
        first_user = next(
            (m["content"] for m in req.messages if m.get("role") == "user"), ""
        )
        title = first_user[:30] + ("..." if len(first_user) > 30 else "")
    db.execute(
        """INSERT INTO conversations (id, title, created_at, updated_at, messages)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
           title=COALESCE(excluded.title, conversations.title),
           updated_at=excluded.updated_at,
           messages=excluded.messages""",
        (req.thread_id, title or "未命名会话", now, now, json.dumps(req.messages, ensure_ascii=False)),
    )
    db.commit()
    db.close()
    return {"status": "ok"}


@router.delete("/history/{thread_id}")
async def delete_history(thread_id: str, _auth: tuple = Depends(require_auth)):
    """删除某次会话。"""
    db = get_db()
    db.execute("DELETE FROM conversations WHERE id = ?", (thread_id,))
    db.commit()
    db.close()
    return {"status": "ok"}
