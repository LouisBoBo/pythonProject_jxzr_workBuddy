"""
历史记录接口：会话持久化（SQLite 本地存储），按登录用户隔离。
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import sys

_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from routes_config import HISTORY_DIR
from routes.auth import UserInfo, require_auth

router = APIRouter(prefix="/api", tags=["history"])

os.makedirs(HISTORY_DIR, exist_ok=True)
DB_PATH = os.path.join(HISTORY_DIR, "conversations.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # 多实例读写下降低锁冲突
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
    except Exception:
        pass
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
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
    cols = {r[1] for r in conn.execute("PRAGMA table_info(conversations)").fetchall()}
    if "user_id" not in cols:
        conn.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT")
    if "username" not in cols:
        conn.execute("ALTER TABLE conversations ADD COLUMN username TEXT")
    conn.commit()
    return conn


def _user_keys(user: UserInfo) -> tuple[str, str]:
    uid = "" if user.user_id is None else str(user.user_id)
    uname = (user.username or "").strip()
    return uid, uname


def _row_owner(row: sqlite3.Row | dict) -> tuple[str, str]:
    keys = row.keys() if hasattr(row, "keys") else row
    row_uid = (row["user_id"] if "user_id" in keys else None) or ""
    row_uname = (row["username"] if "username" in keys else None) or ""
    return str(row_uid).strip(), str(row_uname).strip()


def _is_legacy_unowned(row: sqlite3.Row | dict) -> bool:
    row_uid, row_uname = _row_owner(row)
    return not row_uid and not row_uname


def _owned_by(row: sqlite3.Row | dict, user: UserInfo) -> bool:
    """本人会话，或升级前无归属的旧会话（可被当前用户认领）。"""
    uid, uname = _user_keys(user)
    row_uid, row_uname = _row_owner(row)
    if uid and row_uid and str(row_uid) == uid:
        return True
    if uname and row_uname and row_uname == uname:
        return True
    # #5 之前写入的会话无 user 字段：对已登录用户可见，避免历史「消失」
    if _is_legacy_unowned(row) and (uname or uid):
        return True
    if not row_uid and not row_uname and not uid and uname in ("", "dev"):
        return True
    return False


def _claim_legacy(db: sqlite3.Connection, thread_id: str, user: UserInfo) -> None:
    """把无主旧会话挂到当前用户，避免一直处在共享态。"""
    uid, uname = _user_keys(user)
    if not uid and not uname:
        return
    db.execute(
        """UPDATE conversations
           SET user_id = COALESCE(NULLIF(user_id, ''), ?),
               username = COALESCE(NULLIF(username, ''), ?)
           WHERE id = ?
             AND (user_id IS NULL OR user_id = '')
             AND (username IS NULL OR username = '')""",
        (uid or None, uname or None, thread_id),
    )


class SaveRequest(BaseModel):
    thread_id: str
    title: str | None = None
    messages: list[dict] = []


@router.get("/history")
async def list_history(limit: int = 50, auth: tuple = Depends(require_auth)):
    """获取当前用户的历史会话列表，按更新时间倒序。"""
    _, user = auth
    db = get_db()
    rows = db.execute(
        "SELECT id, title, created_at, updated_at, user_id, username "
        "FROM conversations ORDER BY updated_at DESC LIMIT ?",
        (max(limit * 5, 100),),
    ).fetchall()
    out = []
    claimed = False
    for r in rows:
        if not _owned_by(r, user):
            continue
        if _is_legacy_unowned(r):
            _claim_legacy(db, r["id"], user)
            claimed = True
        out.append(
            {
                "id": r["id"],
                "title": r["title"] or "未命名会话",
                "created_at": datetime.fromtimestamp(r["created_at"]).isoformat(),
                "updated_at": datetime.fromtimestamp(r["updated_at"]).isoformat(),
            }
        )
        if len(out) >= limit:
            break
    if claimed:
        db.commit()
    db.close()
    return out


@router.get("/history/{thread_id}")
async def get_history(thread_id: str, auth: tuple = Depends(require_auth)):
    """获取某次会话的完整对话记录（仅本人）。"""
    _, user = auth
    db = get_db()
    row = db.execute("SELECT * FROM conversations WHERE id = ?", (thread_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(status_code=404, detail="会话不存在")
    if not _owned_by(row, user):
        db.close()
        raise HTTPException(status_code=404, detail="会话不存在")
    if _is_legacy_unowned(row):
        _claim_legacy(db, thread_id, user)
        db.commit()
    messages = json.loads(row["messages"])
    db.close()
    return {
        "id": row["id"],
        "title": row["title"],
        "created_at": datetime.fromtimestamp(row["created_at"]).isoformat(),
        "updated_at": datetime.fromtimestamp(row["updated_at"]).isoformat(),
        "messages": messages,
    }


@router.post("/history/save")
async def save_history(req: SaveRequest, auth: tuple = Depends(require_auth)):
    """保存或更新会话记录（绑定当前用户）。"""
    _, user = auth
    uid, uname = _user_keys(user)
    now = time.time()
    db = get_db()
    existing = db.execute("SELECT * FROM conversations WHERE id = ?", (req.thread_id,)).fetchone()
    if existing and not _owned_by(existing, user):
        db.close()
        raise HTTPException(status_code=403, detail="无权覆盖他人会话")

    title = req.title
    if not title and req.messages:
        first_user = next(
            (m["content"] for m in req.messages if m.get("role") == "user"), ""
        )
        title = first_user[:30] + ("..." if len(first_user) > 30 else "")

    if existing:
        db.execute(
            """UPDATE conversations SET
               title=COALESCE(?, title),
               updated_at=?,
               messages=?,
               user_id=COALESCE(?, user_id),
               username=COALESCE(?, username)
               WHERE id=?""",
            (
                title or None,
                now,
                json.dumps(req.messages, ensure_ascii=False),
                uid or None,
                uname or None,
                req.thread_id,
            ),
        )
    else:
        db.execute(
            """INSERT INTO conversations
               (id, title, created_at, updated_at, messages, user_id, username)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                req.thread_id,
                title or "未命名会话",
                now,
                now,
                json.dumps(req.messages, ensure_ascii=False),
                uid or None,
                uname or None,
            ),
        )
    db.commit()
    db.close()
    return {"status": "ok"}


@router.delete("/history/{thread_id}")
async def delete_history(thread_id: str, auth: tuple = Depends(require_auth)):
    """删除某次会话（仅本人）。"""
    _, user = auth
    db = get_db()
    row = db.execute("SELECT * FROM conversations WHERE id = ?", (thread_id,)).fetchone()
    if not row:
        db.close()
        return {"status": "ok"}
    if not _owned_by(row, user):
        db.close()
        raise HTTPException(status_code=404, detail="会话不存在")
    db.execute("DELETE FROM conversations WHERE id = ?", (thread_id,))
    db.commit()
    db.close()
    return {"status": "ok"}
