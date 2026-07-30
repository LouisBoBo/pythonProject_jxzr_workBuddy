"""IDE Bridge HTTP API：注册 / 心跳 / 长轮询取任务 / 回传结果 / 状态。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from routes.auth import require_auth
from tools.ide_review import bridge_store

router = APIRouter(prefix="/api/ide/bridge", tags=["ide-bridge"])


class RegisterBody(BaseModel):
    bridge_id: str = Field(..., min_length=1)
    workspace_root: str = ""
    carrier: str = "vscode"
    workspace_ready: bool | None = None
    recent_workspaces: list[dict[str, Any]] = Field(default_factory=list)


class HeartbeatBody(BaseModel):
    bridge_id: str = Field(..., min_length=1)
    workspace_root: str | None = None
    workspace_ready: bool | None = None
    recent_workspaces: list[dict[str, Any]] | None = None


class ResultBody(BaseModel):
    """Bridge 回传；必须显式收录 file_contents，否则 Pydantic 会丢掉扩展带来的源码。"""

    task_id: str = Field(..., min_length=1)
    status: str = "ok"
    findings: list[dict[str, Any]] = Field(default_factory=list)
    file_contents: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics_count: dict[str, int] | None = None
    raw_summary: str = ""
    workspace_root: str = ""
    files: list[str] = Field(default_factory=list)
    provider: str = "bridge"
    errors: list[str] = Field(default_factory=list)
    hint: str = ""
    sources: list[str] = Field(default_factory=list)
    review_empty: bool | None = None
    mcp_tool: str | None = None
    mcp_error: str | None = None
    mcp_tools_available: list[str] = Field(default_factory=list)
    bridge_version: str = ""


@router.post("/register")
async def bridge_register(body: RegisterBody, auth: tuple = Depends(require_auth)):
    if not bridge_store.feature_enabled():
        raise HTTPException(status_code=404, detail="IDE 审核未启用（IDE_REVIEW_ENABLED）")
    _token, user = auth
    session = bridge_store.register_bridge(
        user_id=user.user_id,
        username=user.username,
        bridge_id=body.bridge_id.strip(),
        workspace_root=(body.workspace_root or "").strip(),
        carrier=(body.carrier or "vscode").strip(),
        workspace_ready=body.workspace_ready,
        recent_workspaces=body.recent_workspaces,
    )
    return {"ok": True, "session": session}


@router.post("/heartbeat")
async def bridge_heartbeat(body: HeartbeatBody, auth: tuple = Depends(require_auth)):
    if not bridge_store.feature_enabled():
        raise HTTPException(status_code=404, detail="IDE 审核未启用（IDE_REVIEW_ENABLED）")
    _token, user = auth
    try:
        session = bridge_store.heartbeat(
            user.user_id,
            body.bridge_id.strip(),
            workspace_root=body.workspace_root,
            workspace_ready=body.workspace_ready,
            recent_workspaces=body.recent_workspaces,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="请先 register") from None
    except PermissionError:
        raise HTTPException(status_code=403, detail="bridge_id 不匹配") from None
    return {
        "ok": True,
        "last_heartbeat": session.get("last_heartbeat"),
        "workspace_ready": session.get("workspace_ready"),
        "workspace_root": session.get("workspace_root"),
    }


@router.get("/poll")
async def bridge_poll(
    bridge_id: str = Query(..., min_length=1),
    wait_sec: float = Query(25.0, ge=0, le=60),
    auth: tuple = Depends(require_auth),
):
    import asyncio

    if not bridge_store.feature_enabled():
        raise HTTPException(status_code=404, detail="IDE 审核未启用（IDE_REVIEW_ENABLED）")
    _token, user = auth
    try:
        task = await asyncio.to_thread(
            bridge_store.poll_task,
            user.user_id,
            bridge_id.strip(),
            wait_sec,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="bridge_id 不匹配或未注册") from None
    if not task:
        return {"task": None}
    return {"task": task}


@router.post("/result")
async def bridge_result(body: ResultBody, auth: tuple = Depends(require_auth)):
    if not bridge_store.feature_enabled():
        raise HTTPException(status_code=404, detail="IDE 审核未启用（IDE_REVIEW_ENABLED）")
    _token, user = auth
    result: dict[str, Any] = {
        "status": body.status,
        "findings": body.findings,
        "file_contents": body.file_contents,
        "diagnostics_count": body.diagnostics_count
        or {"P0": 0, "P1": 0, "P2": 0},
        "raw_summary": body.raw_summary,
        "workspace_root": body.workspace_root,
        "files": body.files,
        "provider": body.provider or "bridge",
        "errors": body.errors,
        "hint": body.hint,
        "sources": body.sources,
    }
    if body.review_empty is not None:
        result["review_empty"] = body.review_empty
    if body.mcp_tool:
        result["mcp_tool"] = body.mcp_tool
    if body.mcp_error:
        result["mcp_error"] = body.mcp_error
    if body.mcp_tools_available:
        result["mcp_tools_available"] = body.mcp_tools_available
    if body.bridge_version:
        result["bridge_version"] = body.bridge_version
    try:
        saved = bridge_store.put_result(user.user_id, body.task_id.strip(), result)
    except PermissionError as e:
        detail = str(e) or "forbidden"
        if detail == "task_owner_mismatch":
            raise HTTPException(status_code=403, detail="无权回传该任务结果") from e
        if detail == "unknown_task":
            raise HTTPException(status_code=403, detail="未知任务或无权访问") from e
        raise HTTPException(status_code=403, detail=detail) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "task_id": saved.get("task_id")}


class PairCreateResponse(BaseModel):
    code: str
    expires_in: int
    expires_at: float
    hint: str = ""


class PairRedeemBody(BaseModel):
    code: str = Field(..., min_length=4, max_length=16)


@router.post("/pairing/create", response_model=PairCreateResponse)
async def pairing_create(auth: tuple = Depends(require_auth)):
    """网页登录用户签发短时配对码，供 VS Code 扩展兑换 token。"""
    if not bridge_store.feature_enabled():
        raise HTTPException(status_code=404, detail="IDE 审核未启用（IDE_REVIEW_ENABLED）")
    token, user = auth
    try:
        out = bridge_store.create_pairing_code(
            user_id=user.user_id,
            username=user.username,
            access_token=token,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return PairCreateResponse(**out)


@router.post("/pairing/redeem")
async def pairing_redeem(body: PairRedeemBody):
    """扩展用配对码兑换 access_token（无需事先持有 JWT；一次性）。"""
    if not bridge_store.feature_enabled():
        raise HTTPException(status_code=404, detail="IDE 审核未启用（IDE_REVIEW_ENABLED）")
    try:
        return bridge_store.redeem_pairing_code(body.code)
    except KeyError:
        raise HTTPException(status_code=400, detail="配对码无效或已使用") from None
    except PermissionError:
        raise HTTPException(status_code=400, detail="配对码已过期，请在网页重新配对") from None


@router.get("/status")
async def bridge_status(auth: tuple = Depends(require_auth)):
    """始终可调：feature_enabled=false 时前端隐藏入口。"""
    _token, user = auth
    return bridge_store.get_status(user.user_id)


@router.get("/audit")
async def bridge_audit(
    event: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    auth: tuple = Depends(require_auth),
):
    """运维：当前用户相关的 IDE Bridge 审计（不含文件正文/密钥）。"""
    if not bridge_store.feature_enabled():
        raise HTTPException(status_code=404, detail="IDE 审核未启用（IDE_REVIEW_ENABLED）")
    _token, user = auth
    from tools.ide_review.ide_audit import query_ide_audit

    rows = query_ide_audit(user_id=user.user_id, event=event, limit=limit)
    return {"ok": True, "items": rows, "count": len(rows)}
