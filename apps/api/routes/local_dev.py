"""本机目录写码 API（沙箱隔离）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from routes.auth import require_auth
from routes_config import DATA_DIR
import user_prefs

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

from local_dev import jobs as job_store  # noqa: E402
from local_dev.config import get_config  # noqa: E402
from local_dev.folder_picker import pick_local_folder  # noqa: E402
from local_dev.workspace import validate_workspace  # noqa: E402

router = APIRouter(prefix="/api/local-dev", tags=["本机写码"])

_MAX_MESSAGE_LEN = 8000


class CreateLocalJobBody(BaseModel):
    workspace: str = Field(..., min_length=1, description="本机目标目录绝对路径")
    message: str = Field(..., min_length=1, description="需求摘要")
    thread_id: str = Field("", description="会话 thread_id")
    confirmed: bool = Field(False, description="必须为 true 才会创建任务")


class JobResponse(BaseModel):
    id: str
    status: str
    workspace: str = ""
    thread_id: str = ""
    error: str | None = None
    runtime: str = "cursor_local"
    changed_files: list[str] = Field(default_factory=list)
    synced_files: list[str] = Field(default_factory=list)
    sandbox_path: str | None = None
    preview_url: str | None = None
    preview: dict[str, Any] | None = None
    message_count: int = 0
    created_at: int = 0
    updated_at: int = 0
    last_assistant: str = ""


class CancelBody(BaseModel):
    reason: str = Field("用户取消", description="取消原因")


class WorkspaceCheckResponse(BaseModel):
    ok: bool
    path: str = ""
    exists: bool = False
    writable: bool = False
    empty: bool = False
    looks_like_project: bool = False
    project_markers: list[str] = Field(default_factory=list)
    error: str = ""


def _auth_user(auth: tuple):
    _token, user = auth
    return user


def _job_to_response(job: dict[str, Any]) -> JobResponse:
    last_as = ""
    for m in reversed(job.get("messages") or []):
        if m.get("role") == "assistant":
            last_as = str(m.get("content") or "")
            break
    return JobResponse(
        id=job["id"],
        status=job.get("status") or "",
        workspace=job.get("workspace") or "",
        thread_id=job.get("thread_id") or "",
        error=job.get("error"),
        runtime=job.get("runtime") or "cursor_local",
        changed_files=list(job.get("changed_files") or []),
        synced_files=list(job.get("synced_files") or []),
        sandbox_path=job.get("sandbox_path"),
        preview_url=(str(job.get("preview_url") or "").strip() or None),
        preview=job.get("preview") if isinstance(job.get("preview"), dict) else None,
        message_count=len(job.get("messages") or []),
        created_at=int(job.get("created_at") or 0),
        updated_at=int(job.get("updated_at") or 0),
        last_assistant=last_as[:8000],
    )


def _assert_job_owner(job: dict[str, Any], user: Any) -> None:
    """任务须归属当前登录用户；有 user_id 时只认 user_id（禁止仅凭用户名越权）。"""
    uid = str(getattr(user, "user_id", "") or "").strip()
    uname = str(getattr(user, "username", "") or "").strip()
    job_uid = str(job.get("user_id") or "").strip()
    job_uname = str(job.get("username") or "").strip()
    if job_uid:
        if uid and uid == job_uid:
            return
        raise HTTPException(status_code=403, detail="无权访问该任务")
    # 旧任务可能只有 username
    if job_uname and uname and uname == job_uname:
        return
    raise HTTPException(status_code=403, detail="无权访问该任务")


@router.get(
    "/status",
    summary="本机写码可用性",
    description=(
        "检查本机写码是否开启。"
        "默认执行器为 Cursor SDK Local Agent（需 CURSOR_API_KEY）；"
        "LOCAL_DEV_AGENT=llm 仅当 LOCAL_DEV_ALLOW_LLM_FALLBACK=1 时生效。"
    ),
)
async def local_dev_status(auth: tuple = Depends(require_auth)):
    _auth_user(auth)
    cfg = get_config()
    reason = ""
    available = bool(cfg.enabled)
    runtime = "cursor_local" if (cfg.agent or "") == "cursor_sdk" else "local_sandbox"
    cursor_model = ""
    if not available:
        reason = "LOCAL_DEV_ENABLED 未开启"
    elif runtime == "cursor_local":
        from local_dev.cursor_local_agent import cursor_local_availability

        ok, why, model = cursor_local_availability()
        cursor_model = model
        if not ok:
            available = False
            reason = why or "Cursor 本机写码不可用"
    else:
        try:
            agent_root = Path(__file__).resolve().parents[2] / "agent"
            if str(agent_root) not in sys.path:
                sys.path.insert(0, str(agent_root))
            from config import Config  # type: ignore

            if not (Config.LLM_API_KEY or "").strip():
                available = False
                reason = "未配置对话模型 API Key"
        except Exception as e:  # noqa: BLE001
            available = False
            reason = f"无法读取模型配置：{e}"
    return {
        "available": available,
        "reason": reason,
        "enabled": cfg.enabled,
        "runtime": runtime,
        "agent": cfg.agent,
        "llm_fallback_allowed": os.getenv("LOCAL_DEV_ALLOW_LLM_FALLBACK", "").lower()
        in ("1", "true", "yes"),
        "cursor_model": cursor_model,
    }


@router.get(
    "/workspace/check",
    response_model=WorkspaceCheckResponse,
    summary="校验本机目标目录",
    description=(
        "确认卡选择本地路径时调用：检查存在、可写；"
        "拒绝用户主目录/桌面等过宽路径；非空目录须具备工程特征（如 package.json、"
        "requirements.txt、frontend/backend）；空目录允许新建项目。"
    ),
)
async def check_workspace(
    path: str = Query(..., description="本机绝对路径"),
    auth: tuple = Depends(require_auth),
):
    _auth_user(auth)
    return WorkspaceCheckResponse(**validate_workspace(path))


@router.post(
    "/pick-folder",
    summary="弹出本机选文件夹对话框",
    description=(
        "在运行 API 的本机弹出系统原生「选择文件夹」对话框，返回绝对路径。"
        "仅适合浏览器与 API 同机（本地开发）；远程部署时对话框会出现在服务器上，请改用手填路径。"
    ),
)
async def pick_folder_dialog(
    prompt: str = Query("选择工程目录", description="对话框提示文案"),
    auth: tuple = Depends(require_auth),
):
    import asyncio

    _auth_user(auth)
    result = await asyncio.to_thread(pick_local_folder, prompt=prompt or "选择工程目录")
    return result


@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=201,
    summary="创建本机写码任务",
    description="确认本地目录与需求后创建任务；默认用 Cursor SDK 在沙箱改码，成功后再同步到目标目录。",
)
async def create_local_dev_job(body: CreateLocalJobBody, auth: tuple = Depends(require_auth)):
    user = _auth_user(auth)
    cfg = get_config()
    if not cfg.enabled:
        raise HTTPException(status_code=503, detail="本机写码未开启")
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="须 confirmed=true（启动前确认）")

    runtime = "cursor_local" if (cfg.agent or "") == "cursor_sdk" else "local_sandbox"
    if runtime == "cursor_local":
        from local_dev.cursor_local_agent import cursor_local_availability

        ok, why, _model = cursor_local_availability()
        if not ok:
            raise HTTPException(
                status_code=503,
                detail=why or "Cursor 本机写码不可用（需 CURSOR_API_KEY + cursor-sdk）",
            )
    else:
        try:
            agent_root = Path(__file__).resolve().parents[2] / "agent"
            if str(agent_root) not in sys.path:
                sys.path.insert(0, str(agent_root))
            from config import Config  # type: ignore

            if not (Config.LLM_API_KEY or "").strip():
                raise HTTPException(status_code=503, detail="未配置对话模型 API Key")
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=f"无法读取模型配置：{e}") from e

    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message 不能为空")
    if len(message) > _MAX_MESSAGE_LEN:
        raise HTTPException(status_code=400, detail=f"message 过长（>{_MAX_MESSAGE_LEN}）")

    check = validate_workspace(body.workspace)
    if not check.get("ok"):
        raise HTTPException(status_code=400, detail=check.get("error") or "目标目录无效")

    uid = getattr(user, "user_id", None)
    username = getattr(user, "username", None)

    # 一人同时一个本机写码任务
    active = {"queued", "running"}
    if uid is not None:
        for old in job_store.list_jobs(DATA_DIR, statuses=active, user_id=str(uid)):
            oid = str(old.get("id") or "")
            if oid:
                job_store.request_cancel(DATA_DIR, oid, reason="开新本机写码任务，自动结束上一任务")

    global_n = job_store.count_jobs_by_status(DATA_DIR, active)
    if global_n >= cfg.max_concurrent:
        raise HTTPException(
            status_code=429,
            detail=f"本机写码全局并发已满（{global_n}/{cfg.max_concurrent}）",
        )
    if uid is not None:
        user_n = job_store.count_jobs_by_status(DATA_DIR, active, user_id=str(uid))
        if user_n >= cfg.max_concurrent_per_user:
            raise HTTPException(
                status_code=429,
                detail=f"你的本机写码并发已满（{user_n}/{cfg.max_concurrent_per_user}）",
            )

    job = job_store.create_job(
        DATA_DIR,
        user_id=uid,
        username=username,
        thread_id=(body.thread_id or "").strip(),
        workspace=check["path"],
        message=message,
        empty_target=bool(check.get("empty")),
        runtime=runtime,
    )
    user_prefs.set_last_local_workspace(DATA_DIR, username, check["path"])
    return _job_to_response(job)


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    summary="查询本机写码任务",
    description="按任务 id 查询状态、同步文件与预览地址；仅任务归属用户可访问。",
)
async def get_local_dev_job(job_id: str, auth: tuple = Depends(require_auth)):
    user = _auth_user(auth)
    job = job_store.get_job(DATA_DIR, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    _assert_job_owner(job, user)
    return _job_to_response(job)


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=JobResponse,
    summary="取消本机写码任务",
    description="请求取消进行中的本机写码；已取消任务不可再被写成成功。仅归属用户可操作。",
)
async def cancel_local_dev_job(
    job_id: str,
    body: CancelBody | None = None,
    auth: tuple = Depends(require_auth),
):
    user = _auth_user(auth)
    job = job_store.get_job(DATA_DIR, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    _assert_job_owner(job, user)
    reason = (body.reason if body else None) or "用户取消"
    updated = job_store.request_cancel(DATA_DIR, job_id, reason=reason)
    return _job_to_response(updated or job)


@router.get(
    "/jobs/{job_id}/stream",
    summary="本机写码任务 SSE",
    description="执行 queued 任务并推送 step/token/done/error；失败不同步宿主机目标目录。",
)
async def stream_local_dev_job(job_id: str, auth: tuple = Depends(require_auth)):
    import asyncio
    import json
    import time as _time

    from fastapi.responses import StreamingResponse
    from local_dev.service import run_job

    user = _auth_user(auth)
    job = job_store.get_job(DATA_DIR, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    _assert_job_owner(job, user)

    status = job.get("status")
    if status in {"succeeded", "failed", "cancelled"}:

        async def terminal_gen():
            cur = job_store.get_job(DATA_DIR, job_id) or job
            st = cur.get("status")
            if st == "succeeded":
                summary = ""
                for m in reversed(cur.get("messages") or []):
                    if m.get("role") == "assistant":
                        summary = str(m.get("content") or "")
                        break
                summary = summary or "本机写码已完成"
                yield f"data: {json.dumps({'type': 'done', 'job_id': job_id, 'text': summary, 'status': st, 'workspace': cur.get('workspace'), 'changed_files': cur.get('synced_files') or [], 'preview_url': cur.get('preview_url') or '', 'preview': cur.get('preview') if isinstance(cur.get('preview'), dict) else {}}, ensure_ascii=False)}\n\n"
            else:
                err = cur.get("error") or "本机写码未成功"
                yield f"data: {json.dumps({'type': 'error', 'message': err}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            terminal_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    if status == "running":
        raise HTTPException(status_code=409, detail="任务已在执行，请稍后查询或取消后重试")
    if status not in {"queued", "failed"}:
        raise HTTPException(status_code=409, detail=f"任务状态不可执行：{status}")

    # 原子抢占，避免双 SSE 同时 run_job
    claimed = job_store.try_claim_job(DATA_DIR, job_id)
    if not claimed:
        cur = job_store.get_job(DATA_DIR, job_id) or job
        st = cur.get("status")
        if st == "running":
            raise HTTPException(status_code=409, detail="任务已在执行，请稍后查询或取消后重试")
        if st == "cancelled" or cur.get("cancel_requested"):
            raise HTTPException(status_code=409, detail="任务已取消")
        raise HTTPException(status_code=409, detail=f"任务状态不可执行：{st}")

    cfg = get_config()
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def sink(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    async def produce() -> None:
        try:
            fresh = job_store.get_job(DATA_DIR, job_id) or claimed
            if not fresh or fresh.get("status") == "cancelled" or fresh.get("cancel_requested"):
                await queue.put({"type": "error", "message": "任务已取消"})
            else:
                await asyncio.to_thread(run_job, DATA_DIR, fresh, sink=sink, cfg=cfg)
        except Exception as exc:  # noqa: BLE001
            await queue.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
            job_store.update_job(DATA_DIR, job_id, status="failed", error=str(exc))
        finally:
            await queue.put({"type": "_end"})

    async def event_gen():
        task = asyncio.create_task(produce())
        started = _time.time()
        saw_terminal = False
        try:
            yield f"data: {json.dumps({'type': 'status', 'text': '本机沙箱写码开始', 'phase': 'start'}, ensure_ascii=False)}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    elapsed = max(1, int(_time.time() - started))
                    yield f"data: {json.dumps({'type': 'status', 'text': f'沙箱写码进行中…{elapsed}s', 'phase': 'heartbeat', 'elapsed_sec': elapsed}, ensure_ascii=False)}\n\n"
                    continue
                if event.get("type") == "_end":
                    break
                if event.get("type") in {"done", "error"}:
                    saw_terminal = True
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if not saw_terminal:
                cur = job_store.get_job(DATA_DIR, job_id) or {}
                if cur.get("status") == "succeeded":
                    yield f"data: {json.dumps({'type': 'done', 'job_id': job_id, 'text': '本机写码已完成', 'status': 'succeeded'}, ensure_ascii=False)}\n\n"
                elif cur.get("status") in {"failed", "cancelled"}:
                    yield f"data: {json.dumps({'type': 'error', 'message': cur.get('error') or '失败'}, ensure_ascii=False)}\n\n"
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except Exception:
                    pass

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
