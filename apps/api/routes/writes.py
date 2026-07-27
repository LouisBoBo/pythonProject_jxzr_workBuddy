"""
写操作确认 / 取消 / 审计查询（M2）。

确认路径直接执行已挂起工具参数，不经 Agent 二次调用，避免重复写入与提示注入。
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from routes.auth import require_auth, UserInfo
from tools.platform_api import set_request_erp_token, reset_request_erp_token
from middleware.write_store import get_action, list_pending, mark_action, query_audit
from middleware.write_tools import WRITE_TOOLS
from tools.file_ops import import_file_to_platform

router = APIRouter(prefix="/api/writes", tags=["writes"])


class ActionResponse(BaseModel):
    action_id: str
    status: str
    tool: str | None = None
    thread_id: str | None = None
    preview: dict[str, Any] | None = None
    result: Any = None
    message: str = ""


def _assert_owner(action: dict[str, Any], user: UserInfo) -> None:
    """绑定操作人：优先 user_id，其次 username。"""
    aid = action.get("user_id")
    aname = (action.get("username") or "").strip()
    uid = user.user_id
    uname = (user.username or "").strip()
    if aid is not None and uid is not None and str(aid) == str(uid):
        return
    if aname and uname and aname == uname:
        return
    # 开发模式 AUTH_REQUIRED=false 时 user_id=0，放宽到同 username 或双方空用户
    if not aname and not uname:
        return
    raise HTTPException(status_code=403, detail="无权操作该写确认请求")


def _ensure_pending(action: dict[str, Any]) -> None:
    if action.get("status") != "pending":
        raise HTTPException(status_code=409, detail=f"操作已结束，当前状态：{action.get('status')}")
    expires = float(action.get("expires_at") or 0)
    if expires and time.time() > expires:
        mark_action(action["action_id"], status="expired")
        raise HTTPException(status_code=410, detail="确认已过期，请重新发起导入")


def _execute_write(action: dict[str, Any]) -> dict[str, Any]:
    tool = action.get("tool")
    args = dict(action.get("args") or {})
    if tool not in WRITE_TOOLS:
        return {"error": f"不支持的写工具: {tool}"}
    if tool == "import_file_to_platform":
        return import_file_to_platform(
            file_path=str(args.get("file_path") or ""),
            target_entity=str(args.get("target_entity") or args.get("entity") or ""),
            file_type=args.get("file_type"),
            sheet_name=str(args.get("sheet_name") or "Sheet1"),
        )
    return {"error": f"未实现执行器: {tool}"}


@router.get("/pending")
async def pending_writes(
    thread_id: str | None = Query(None),
    auth: tuple = Depends(require_auth),
):
    """列出当前用户待确认写操作。"""
    _token, user = auth
    items = list_pending(thread_id=thread_id, username=user.username or None)
    # 再按 user_id 过滤（list_pending 主要按 username）
    filtered = []
    for it in items:
        try:
            _assert_owner(it, user)
            filtered.append(
                {
                    "action_id": it.get("action_id"),
                    "status": it.get("status"),
                    "tool": it.get("tool"),
                    "thread_id": it.get("thread_id"),
                    "preview": it.get("preview"),
                    "created_at": it.get("created_at"),
                    "expires_at": it.get("expires_at"),
                }
            )
        except HTTPException:
            continue
    return {"items": filtered}


@router.get("/actions/{action_id}", response_model=ActionResponse)
async def get_write_action(action_id: str, auth: tuple = Depends(require_auth)):
    _token, user = auth
    action = get_action(action_id)
    if not action:
        raise HTTPException(status_code=404, detail="未找到该写操作")
    _assert_owner(action, user)
    return ActionResponse(
        action_id=action["action_id"],
        status=action.get("status") or "unknown",
        tool=action.get("tool"),
        thread_id=action.get("thread_id"),
        preview=action.get("preview"),
        result=action.get("result"),
    )


@router.post("/actions/{action_id}/confirm", response_model=ActionResponse)
async def confirm_write(action_id: str, auth: tuple = Depends(require_auth)):
    """用户确认后执行真实写操作。"""
    erp_token, user = auth
    action = get_action(action_id)
    if not action:
        raise HTTPException(status_code=404, detail="未找到该写操作")
    _assert_owner(action, user)
    _ensure_pending(action)

    tok = set_request_erp_token(erp_token)
    try:
        result = _execute_write(action)
    finally:
        reset_request_erp_token(tok)

    ok = isinstance(result, dict) and not result.get("error")
    status = "confirmed" if ok else "failed"
    updated = mark_action(
        action_id,
        status=status,
        result=result,
        actor_username=user.username,
    )
    if not updated:
        raise HTTPException(status_code=500, detail="更新写操作状态失败")

    if not ok:
        raise HTTPException(
            status_code=502,
            detail=str(result.get("error") if isinstance(result, dict) else result),
        )

    return ActionResponse(
        action_id=action_id,
        status=status,
        tool=updated.get("tool"),
        thread_id=updated.get("thread_id"),
        preview=updated.get("preview"),
        result=result,
        message="写入已执行",
    )


@router.post("/actions/{action_id}/cancel", response_model=ActionResponse)
async def cancel_write(action_id: str, auth: tuple = Depends(require_auth)):
    """取消写操作：不调用平台。"""
    _token, user = auth
    action = get_action(action_id)
    if not action:
        raise HTTPException(status_code=404, detail="未找到该写操作")
    _assert_owner(action, user)
    _ensure_pending(action)

    updated = mark_action(
        action_id,
        status="cancelled",
        result={"status": "cancelled"},
        actor_username=user.username,
    )
    return ActionResponse(
        action_id=action_id,
        status="cancelled",
        tool=(updated or action).get("tool"),
        thread_id=(updated or action).get("thread_id"),
        preview=(updated or action).get("preview"),
        result={"status": "cancelled"},
        message="已取消，未写入平台",
    )


@router.get("/audit")
async def audit_list(
    thread_id: str | None = Query(None),
    tool: str | None = Query(None),
    username: str | None = Query(None),
    event: str | None = Query(None),
    file_keyword: str | None = Query(None),
    since: str | None = Query(None, description="起始时间；不传则默认近 WRITE_AUDIT_DEFAULT_DAYS 天"),
    until: str | None = Query(None, description="结束时间（不含）"),
    lookback_days: int | None = Query(None, ge=1, le=3650, description="未传 since 时的默认天数"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    auth: tuple = Depends(require_auth),
):
    """只读审计：默认近 N 天 + 分页，不会全量查询。"""
    from datetime import datetime, timedelta
    import os
    from tools.write_audit_query import _parse_time

    _token, _user = auth
    since_ts = _parse_time(since)
    until_ts = _parse_time(until)
    default_days = int(os.getenv("WRITE_AUDIT_DEFAULT_DAYS", "30"))
    days = lookback_days or default_days
    applied_default = False
    if since_ts is None:
        since_ts = (datetime.now() - timedelta(days=days)).timestamp()
        since = datetime.fromtimestamp(since_ts).strftime("%Y-%m-%d %H:%M:%S")
        applied_default = True

    page = query_audit(
        thread_id=thread_id,
        tool=tool,
        username=username,
        event=event,
        file_keyword=file_keyword,
        since_ts=since_ts,
        until_ts=until_ts,
        offset=offset,
        limit=limit,
    )
    return {
        "items": page.get("items") or [],
        "count": len(page.get("items") or []),
        "has_more": page.get("has_more", False),
        "offset": page.get("offset", offset),
        "limit": page.get("limit", limit),
        "since": since,
        "until": until,
        "default_window_applied": applied_default,
        "lookback_days": days if applied_default else None,
        "truncated": True,
    }
