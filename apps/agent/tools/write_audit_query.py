"""
查询本助手的写操作审计（谁导入了哪个文件）。

说明：ERP 平台本身通常没有「导入操作人」明细；
本工具读取 WorkBuddy M2 落盘的 data/writes/audit.jsonl。

默认只查「近 N 天」+ 分页，不会每次全表扫描。
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from middleware.write_store import query_audit

# 未指定 since 时的默认回溯天数（可用环境变量覆盖）
DEFAULT_LOOKBACK_DAYS = int(os.getenv("WRITE_AUDIT_DEFAULT_DAYS", "30"))


def _parse_time(value: str | None) -> float | None:
    """支持 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS。"""
    if not value or not str(value).strip():
        return None
    s = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).timestamp()
        except ValueError:
            continue
    try:
        return float(s)
    except Exception:
        return None


def query_write_audit(
    event: Annotated[
        Literal[
            "write_confirmed",
            "write_cancelled",
            "write_pending",
            "write_failed",
            "all",
        ],
        "事件类型：write_confirmed（默认）/ write_cancelled / write_pending / write_failed / all",
    ] = "write_confirmed",
    username: Annotated[str | None, "操作人用户名，如 admin"] = None,
    file_keyword: Annotated[str | None, "文件名关键字"] = None,
    thread_id: Annotated[str | None, "会话 thread_id"] = None,
    since: Annotated[
        str | None,
        "起始时间（含），格式 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS；不传则用近 lookback_days 天",
    ] = None,
    until: Annotated[
        str | None, "结束时间（不含），格式同上"
    ] = None,
    offset: Annotated[int, "分页偏移，从 0 开始"] = 0,
    limit: Annotated[int, "每页条数，默认 20，最大 100"] = 20,
    lookback_days: Annotated[
        int | None, "未传 since 时的默认回溯天数；传 since 则忽略"
    ] = None,
) -> dict[str, Any]:
    """查询「谁导入/取消了哪个文件」——读取助手写操作审计，不是 ERP 工单表。

    默认行为（重要）：
    - 未传 since 时，只查近 lookback_days 天（默认 30 天），不会查全部历史
    - 每页最多 limit 条（默认 20，最大 100），用 offset 翻页
    - 时间倒序扫描，早于 since 即停止
    """
    limit = max(1, min(int(limit or 20), 100))
    offset = max(0, int(offset or 0))
    event_filter = None if event in (None, "", "all") else event

    since_ts = _parse_time(since)
    until_ts = _parse_time(until)
    applied_default_window = False
    days = DEFAULT_LOOKBACK_DAYS if lookback_days is None else max(1, int(lookback_days))
    if since_ts is None:
        since_ts = (datetime.now() - timedelta(days=days)).timestamp()
        applied_default_window = True
        since = datetime.fromtimestamp(since_ts).strftime("%Y-%m-%d %H:%M:%S")

    page = query_audit(
        thread_id=thread_id,
        tool="import_file_to_platform",
        username=username,
        event=event_filter,
        file_keyword=file_keyword,
        since_ts=since_ts,
        until_ts=until_ts,
        offset=offset,
        limit=limit,
    )
    rows = page.get("items") or []

    records: list[dict[str, Any]] = []
    for row in rows:
        args = row.get("args_summary") if isinstance(row.get("args_summary"), dict) else {}
        prev = row.get("preview_summary") if isinstance(row.get("preview_summary"), dict) else {}
        result = row.get("result_summary") if isinstance(row.get("result_summary"), dict) else {}
        file_path = str(args.get("file_path") or "")
        file_name = str(prev.get("file") or result.get("file") or "")
        if not file_name and file_path:
            file_name = file_path.rstrip("/").split("/")[-1]
        ts = row.get("ts")
        try:
            time_text = datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
        except Exception:
            time_text = str(ts or "")
        records.append(
            {
                "time": time_text,
                "ts": ts,
                "username": row.get("username") or "",
                "user_id": row.get("user_id"),
                "event": row.get("event"),
                "file": file_name,
                "target_entity": args.get("target_entity")
                or prev.get("target_entity")
                or result.get("target_entity"),
                "rows_imported": result.get("rows_imported"),
                "thread_id": row.get("thread_id"),
                "action_id": row.get("action_id"),
            }
        )

    window_note = (
        f"默认只查近 {days} 天（since={since}），不是全量历史；"
        if applied_default_window
        else f"时间窗 since={since or '-'} until={until or '-'}；"
    )
    tip = (
        window_note
        + f"本页 {len(records)} 条，limit={limit}。"
        + ("还有更多可用 offset 翻页。" if page.get("has_more") else "本窗内已无更多。")
        + " 数据来自助手写操作审计，非 ERP 工单表。"
    )
    return {
        "returned": len(records),
        "has_more": bool(page.get("has_more")),
        "offset": page.get("offset", offset),
        "limit": page.get("limit", limit),
        "event_filter": event_filter or "all",
        "since": since,
        "until": until,
        "default_window_applied": applied_default_window,
        "lookback_days": days if applied_default_window else None,
        "records": records,
        "note": tip,
    }
