"""
写操作待确认 + 审计落盘。

存储：
  data/writes/pending/{action_id}.json
  data/writes/audit.jsonl

设计目标：可人工查看、可按文件回滚、不引入额外数据库依赖。
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from config import Config
from ha.fs_lock import InterProcessLock, instance_id

_LOCK = InterProcessLock("writes")

ACTION_TTL_SEC = int(os.getenv("WRITE_CONFIRM_TTL_SEC", "1800"))  # 默认 30 分钟
# 审计文件超过该行数时轮转：audit.jsonl → audit.jsonl.1（只保留一份备份）
AUDIT_MAX_LINES = int(os.getenv("WRITE_AUDIT_MAX_LINES", "50000"))


def _writes_root() -> Path:
    root = Path(Config.DATA_DIR) / "writes"
    root.mkdir(parents=True, exist_ok=True)
    (root / "pending").mkdir(parents=True, exist_ok=True)
    return root


def _pending_path(action_id: str) -> Path:
    safe = "".join(c for c in action_id if c.isalnum() or c in "-_")
    if not safe or safe != action_id:
        raise ValueError("非法 action_id")
    return _writes_root() / "pending" / f"{safe}.json"


def _audit_path() -> Path:
    return _writes_root() / "audit.jsonl"


def new_action_id() -> str:
    return uuid.uuid4().hex


def create_pending_action(
    *,
    tool: str,
    args: dict[str, Any],
    preview: dict[str, Any],
    thread_id: str,
    user_id: Any,
    username: str,
) -> dict[str, Any]:
    now = time.time()
    action = {
        "action_id": new_action_id(),
        "status": "pending",
        "tool": tool,
        "args": args,
        "preview": preview,
        "thread_id": thread_id or "default",
        "user_id": user_id,
        "username": username or "",
        "created_at": now,
        "expires_at": now + ACTION_TTL_SEC,
        "resolved_at": None,
        "result": None,
        "instance_id": instance_id(),
    }
    path = _pending_path(action["action_id"])
    with _LOCK:
        path.write_text(json.dumps(action, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        append_audit(
            {
                "event": "write_pending",
                "action_id": action["action_id"],
                "tool": tool,
                "thread_id": action["thread_id"],
                "user_id": user_id,
                "username": username,
                "args_summary": _brief_args(args),
                "preview_summary": _brief_preview(preview),
                "ts": now,
            }
        )
    return action


def get_action(action_id: str) -> dict[str, Any] | None:
    try:
        path = _pending_path(action_id)
    except ValueError:
        return None
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def list_pending(*, thread_id: str | None = None, username: str | None = None) -> list[dict[str, Any]]:
    root = _writes_root() / "pending"
    out: list[dict[str, Any]] = []
    now = time.time()
    with _LOCK:
        for path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            if data.get("status") != "pending":
                continue
            if float(data.get("expires_at") or 0) < now:
                data["status"] = "expired"
                data["resolved_at"] = now
                _save_action_unlocked(data)
                append_audit(
                    {
                        "event": "write_expired",
                        "action_id": data.get("action_id"),
                        "tool": data.get("tool"),
                        "thread_id": data.get("thread_id"),
                        "user_id": data.get("user_id"),
                        "username": data.get("username"),
                        "args_summary": _brief_args(data.get("args") or {}),
                        "ts": now,
                    }
                )
                continue
            if thread_id and data.get("thread_id") != thread_id:
                continue
            if username and data.get("username") and data.get("username") != username:
                continue
            out.append(data)
    return out


def claim_action(
    action_id: str,
    *,
    to_status: str,
    expected_statuses: tuple[str, ...] = ("pending",),
    actor_username: str | None = None,
    result: Any = None,
    audit: bool = False,
) -> dict[str, Any] | None:
    """原子状态迁移：仅当当前 status ∈ expected_statuses 时成功，用于防双确认。"""
    with _LOCK:
        action = get_action(action_id)
        if not action:
            return None
        cur = action.get("status")
        if cur not in expected_statuses:
            return None
        if cur == "pending":
            expires = float(action.get("expires_at") or 0)
            if expires and time.time() > expires:
                action["status"] = "expired"
                action["resolved_at"] = time.time()
                _save_action_unlocked(action)
                append_audit(
                    {
                        "event": "write_expired",
                        "action_id": action_id,
                        "tool": action.get("tool"),
                        "thread_id": action.get("thread_id"),
                        "user_id": action.get("user_id"),
                        "username": actor_username or action.get("username"),
                        "args_summary": _brief_args(action.get("args") or {}),
                        "ts": action["resolved_at"],
                    }
                )
                return None
        action["status"] = to_status
        if result is not None:
            action["result"] = result
        if actor_username:
            action["resolved_by"] = actor_username
        if to_status in ("confirmed", "cancelled", "expired", "failed"):
            action["resolved_at"] = time.time()
        _save_action_unlocked(action)
        if audit:
            append_audit(
                {
                    "event": f"write_{to_status}",
                    "action_id": action_id,
                    "tool": action.get("tool"),
                    "thread_id": action.get("thread_id"),
                    "user_id": action.get("user_id"),
                    "username": actor_username or action.get("username"),
                    "args_summary": _brief_args(action.get("args") or {}),
                    "result_summary": _brief_result(result),
                    "ts": action.get("resolved_at") or time.time(),
                }
            )
        return action


def mark_action(
    action_id: str,
    *,
    status: str,
    result: Any = None,
    actor_username: str | None = None,
    expected_statuses: tuple[str, ...] | None = None,
    write_audit: bool = True,
) -> dict[str, Any] | None:
    """更新写操作状态并写审计。

    若传入 expected_statuses，则仅在当前状态匹配时更新（CAS）；否则无条件覆盖。
    write_audit=False 时只改状态不写审计（用于执行失败回退 pending）。
    """
    with _LOCK:
        action = get_action(action_id)
        if not action:
            return None
        if expected_statuses is not None and action.get("status") not in expected_statuses:
            return None
        action["status"] = status
        if status == "pending":
            action["resolved_at"] = None
        else:
            action["resolved_at"] = time.time()
        action["result"] = result
        if actor_username:
            action["resolved_by"] = actor_username
        _save_action_unlocked(action)
        if write_audit:
            append_audit(
                {
                    "event": f"write_{status}",
                    "action_id": action_id,
                    "tool": action.get("tool"),
                    "thread_id": action.get("thread_id"),
                    "user_id": action.get("user_id"),
                    "username": actor_username or action.get("username"),
                    "args_summary": _brief_args(action.get("args") or {}),
                    "result_summary": _brief_result(result),
                    "ts": action.get("resolved_at") or time.time(),
                }
            )
        return action


def _save_action_unlocked(action: dict[str, Any]) -> None:
    path = _pending_path(str(action["action_id"]))
    path.write_text(json.dumps(action, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def append_audit(record: dict[str, Any]) -> None:
    """追加一行审计；超限时轮转旧文件。"""
    if "instance_id" not in record:
        record = {**record, "instance_id": instance_id()}
    line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
    path = _audit_path()
    with _LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
        _maybe_rotate_audit_unlocked(path)


def _maybe_rotate_audit_unlocked(path: Path) -> None:
    if AUDIT_MAX_LINES <= 0 or not path.exists():
        return
    try:
        # 粗略按行数：只在文件较大时统计，避免每次全读
        size = path.stat().st_size
        if size < 2_000_000:  # <2MB 先不查行数
            return
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) <= AUDIT_MAX_LINES:
            return
        keep = lines[-AUDIT_MAX_LINES :]
        bak = path.with_suffix(path.suffix + ".1")
        # 旧备份覆盖写入历史文件名
        if bak.exists():
            bak.unlink()
        path.rename(bak)
        path.write_text("\n".join(keep) + "\n", encoding="utf-8")
    except Exception:
        # 轮转失败不影响主流程
        pass


def query_audit(
    *,
    thread_id: str | None = None,
    tool: str | None = None,
    username: str | None = None,
    event: str | None = None,
    file_keyword: str | None = None,
    since_ts: float | None = None,
    until_ts: float | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """查询审计（默认应带 since_ts，避免全量扫描）。

    - 按文件末尾倒序（最新在前）
    - since_ts / until_ts：Unix 秒，区间 [since, until)
    - 扫到早于 since_ts 的记录立即停止（不会继续往更早翻）
    - 只取 offset+limit 一页；用 has_more 表示是否还有更新页内数据
    """
    path = _audit_path()
    empty = {
        "items": [],
        "returned": 0,
        "has_more": False,
        "offset": 0,
        "limit": limit,
        "since_ts": since_ts,
        "until_ts": until_ts,
        "truncated": True,
    }
    if not path.exists():
        return empty
    limit = max(1, min(int(limit or 50), 500))
    offset = max(0, int(offset or 0))
    file_kw = (file_keyword or "").strip().lower()
    need = offset + limit + 1  # +1 用于判断 has_more
    matched: list[dict[str, Any]] = []
    with _LOCK:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return {**empty, "offset": offset, "limit": limit}

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        try:
            ts = float(row.get("ts") or 0)
        except Exception:
            ts = 0.0
        # 已按时间倒序：早于 since 则后面更旧，直接停
        if since_ts is not None and ts < float(since_ts):
            break
        if until_ts is not None and ts >= float(until_ts):
            continue
        if thread_id and row.get("thread_id") != thread_id:
            continue
        if tool and row.get("tool") != tool:
            continue
        if username and str(row.get("username") or "") != username:
            continue
        if event and str(row.get("event") or "") != event:
            continue
        if file_kw:
            args = row.get("args_summary") if isinstance(row.get("args_summary"), dict) else {}
            prev = row.get("preview_summary") if isinstance(row.get("preview_summary"), dict) else {}
            blob = " ".join(
                [
                    str(args.get("file_path") or ""),
                    str(prev.get("file") or ""),
                    str(row.get("result_summary") or ""),
                ]
            ).lower()
            if file_kw not in blob:
                continue
        matched.append(row)
        if len(matched) >= need:
            break

    page = matched[offset : offset + limit]
    has_more = len(matched) > offset + limit
    return {
        "items": page,
        "returned": len(page),
        "has_more": has_more,
        "offset": offset,
        "limit": limit,
        "since_ts": since_ts,
        "until_ts": until_ts,
        "truncated": True,
        # 兼容旧字段名：仅表示本页，不是全库总数
        "total_matched": len(page),
    }


def list_audit(**kwargs: Any) -> list[dict[str, Any]]:
    return list(query_audit(**kwargs).get("items") or [])


def _brief_args(args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        return {"raw": str(args)[:200]}
    keys = ("file_path", "target_entity", "entity", "file_type", "sheet_name")
    return {k: args.get(k) for k in keys if k in args}


def _brief_preview(preview: Any) -> dict[str, Any]:
    if not isinstance(preview, dict):
        return {}
    return {
        "row_count": preview.get("row_count"),
        "columns": preview.get("columns"),
        "file": preview.get("file"),
        "target_entity": preview.get("target_entity"),
    }


def _brief_result(result: Any) -> Any:
    if result is None:
        return None
    if isinstance(result, dict):
        out = {}
        for k in ("status", "error", "rows_imported", "rows_read", "target_entity", "file"):
            if k in result:
                out[k] = result[k]
        return out or {k: result[k] for k in list(result)[:6]}
    return str(result)[:240]
