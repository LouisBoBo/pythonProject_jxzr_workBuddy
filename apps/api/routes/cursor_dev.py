"""Cursor 研发写码旁路 HTTP API。"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from routes.auth import require_auth
from routes_config import DATA_DIR

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

from cursor_dev.allowlist import is_allowed, normalize_repo  # noqa: E402
from cursor_dev.audit import append_audit, list_audit  # noqa: E402
from cursor_dev.config import reload_config, user_allowed  # noqa: E402
from cursor_dev import jobs as job_store  # noqa: E402
from cursor_dev.prompts import build_first_turn_prompt, build_followup_prompt  # noqa: E402
from cursor_dev.project_inspect import inspect_repo  # noqa: E402
from cursor_dev.user_branch import user_work_branch  # noqa: E402
from cursor_dev.readiness import build_readiness  # noqa: E402
from cursor_dev.github_preflight import resolve_starting_ref  # noqa: E402

router = APIRouter(prefix="/api/cursor-dev", tags=["cursor-dev"])

_MAX_MESSAGE_LEN = 4000


class ReadinessCheck(BaseModel):
    id: str
    ok: bool
    title: str
    detail: str = ""
    admin_only: bool = True
    manual: bool = False


class ReadinessPayload(BaseModel):
    ready: bool
    summary: str = ""
    colleague_zero_config: bool = True
    checks: list[ReadinessCheck] = Field(default_factory=list)


class StatusResponse(BaseModel):
    available: bool
    reason: str = ""
    enabled: bool
    allowlist_count: int = 0
    default_repo: str = ""
    starting_ref: str = ""
    model: str = ""
    user_allowed: bool = True
    sdk_installed: bool = False
    # 管理员上线闸门；同事侧只需 available=true 即可开箱写码
    readiness: ReadinessPayload | None = None


class ReposResponse(BaseModel):
    available: bool
    reason: str = ""
    repos: list[str] = Field(default_factory=list)
    default_repo: str = ""
    starting_ref: str = ""


class CreateJobBody(BaseModel):
    repo: str = Field(..., min_length=1)
    ref: str = ""
    message: str = Field(..., min_length=1)
    thread_id: str = ""
    create_pr: bool = False
    confirmed: bool = False


class JobResponse(BaseModel):
    id: str
    status: str
    repo: str
    ref: str = ""
    thread_id: str = ""
    create_pr: bool = False
    agent_id: str | None = None
    run_id: str | None = None
    pr_url: str | None = None
    error: str | None = None
    runtime: str = "cloud"
    review_job_id: str | None = None
    message_count: int = 0
    created_at: int = 0
    updated_at: int = 0
    warnings: list[str] = Field(default_factory=list)


class FollowUpBody(BaseModel):
    message: str = Field(..., min_length=1)
    create_pr: bool | None = None
    confirmed: bool = True


class CancelBody(BaseModel):
    reason: str = "用户取消"


def _job_to_response(job: dict[str, Any], *, warnings: list[str] | None = None) -> JobResponse:
    return JobResponse(
        id=job["id"],
        status=job.get("status") or "",
        repo=job.get("repo") or "",
        ref=job.get("ref") or "",
        thread_id=job.get("thread_id") or "",
        create_pr=bool(job.get("create_pr")),
        agent_id=job.get("agent_id"),
        run_id=job.get("run_id"),
        pr_url=job.get("pr_url"),
        error=job.get("error"),
        runtime=job.get("runtime") or "cloud",
        review_job_id=job.get("review_job_id"),
        message_count=len(job.get("messages") or []),
        created_at=int(job.get("created_at") or 0),
        updated_at=int(job.get("updated_at") or 0),
        warnings=list(warnings or []),
    )


def _auth_user(auth: tuple):
    _token, user = auth
    return user


@router.get("/status", response_model=StatusResponse)
async def cursor_dev_status(auth: tuple = Depends(require_auth)):
    user = _auth_user(auth)
    cfg = reload_config()
    ok, reason = cfg.availability()
    allowed = user_allowed(getattr(user, "username", None), getattr(user, "user_id", None))
    if ok and not allowed:
        ok = False
        reason = "当前用户不在 CURSOR_DEV_ALLOWED_USERS 授权名单"
    default_repo = cfg.repo_allowlist[0] if cfg.repo_allowlist else ""
    readiness = ReadinessPayload(**build_readiness(cfg))
    return StatusResponse(
        available=ok,
        reason=reason,
        enabled=cfg.enabled,
        allowlist_count=len(cfg.repo_allowlist),
        default_repo=default_repo,
        starting_ref=cfg.starting_ref,
        model=cfg.model,
        user_allowed=allowed,
        sdk_installed=cfg.sdk_ok,
        readiness=readiness,
    )


@router.get("/repos", response_model=ReposResponse)
async def cursor_dev_repos(auth: tuple = Depends(require_auth)):
    user = _auth_user(auth)
    cfg = reload_config()
    ok, reason = cfg.availability()
    allowed = user_allowed(getattr(user, "username", None), getattr(user, "user_id", None))
    if not allowed:
        return ReposResponse(available=False, reason="当前用户未授权写码车道", repos=[])
    repos = list(cfg.repo_allowlist)
    return ReposResponse(
        available=ok,
        reason="" if ok else reason,
        repos=repos,
        default_repo=repos[0] if repos else "",
        starting_ref=cfg.starting_ref,
    )


@router.get("/repos/inspect")
async def cursor_dev_repo_inspect(
    repo: str,
    ref: str = "",
    auth: tuple = Depends(require_auth),
):
    """现场读 GitHub 仓库摘要（不落库）。新开对话选「已有项目」后调用。"""
    user = _auth_user(auth)
    if not user_allowed(getattr(user, "username", None), getattr(user, "user_id", None)):
        raise HTTPException(status_code=403, detail="当前用户未授权写码车道")
    cfg = reload_config()
    normalized = normalize_repo(repo)
    if not normalized:
        raise HTTPException(status_code=400, detail="仓库格式无效")
    if not is_allowed(normalized, cfg.repo_allowlist):
        raise HTTPException(status_code=403, detail="仓库不在白名单")
    result = inspect_repo(
        normalized,
        preferred_ref=ref or None,
        data_dir=DATA_DIR,
        username=getattr(user, "username", None),
        user_id=getattr(user, "user_id", None),
        branch_prefix=cfg.branch_prefix,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "读取仓库失败")
    return result


@router.post("/jobs", response_model=JobResponse, status_code=201)
async def create_cursor_dev_job(body: CreateJobBody, auth: tuple = Depends(require_auth)):
    """开写码会话（落盘 queued）。D4 不执行 Cloud；D5 再跑 Agent。"""
    user = _auth_user(auth)
    cfg = reload_config()

    if not user_allowed(getattr(user, "username", None), getattr(user, "user_id", None)):
        raise HTTPException(status_code=403, detail="当前用户未授权写码车道")

    if not body.confirmed:
        raise HTTPException(status_code=400, detail="须 confirmed=true（启动前确认）")

    repo = normalize_repo(body.repo)
    if not repo:
        raise HTTPException(status_code=400, detail="仓库格式无效，请使用 owner/repo 或 HTTPS URL")

    if not is_allowed(repo, cfg.repo_allowlist):
        raise HTTPException(
            status_code=400,
            detail=f"仓库不在白名单：{repo}（管理员可配置 CURSOR_DEV_REPO_ALLOWLIST；空=不限制）",
        )

    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message 不能为空")
    if len(message) > _MAX_MESSAGE_LEN:
        raise HTTPException(status_code=400, detail=f"message 过长（>{_MAX_MESSAGE_LEN}）")

    ok, reason = cfg.availability()
    # D4：允许在 sdk 未就绪时仍创建 job（queued），便于联调落盘；执行留给 D5
    if not cfg.enabled:
        raise HTTPException(status_code=503, detail=reason or "CURSOR_DEV_ENABLED 未开启")
    if not cfg.api_key:
        raise HTTPException(status_code=503, detail="未配置 CURSOR_API_KEY")

    uid = getattr(user, "user_id", None)
    # 上次确认后若未真正 stream（卡在 queued），先释放名额，避免「并发已满」死锁
    freed = job_store.cancel_abandoned_queued(
        DATA_DIR,
        user_id=str(uid) if uid is not None else None,
    )
    if freed:
        append_audit(
            DATA_DIR,
            {
                "event": "jobs_auto_cancelled",
                "job_ids": freed,
                "user_id": "" if uid is None else str(uid),
                "reason": "new_job_replaces_abandoned_queued",
            },
        )

    active = {"queued", "running", "creating_pr"}
    global_n = job_store.count_jobs_by_status(DATA_DIR, active)
    if global_n >= cfg.max_concurrent:
        raise HTTPException(
            status_code=429,
            detail=(
                f"写码任务全局并发已满（{global_n}/{cfg.max_concurrent}）。"
                "请稍后再试，或到 https://cursor.com/dashboard/usage / Agents 停掉卡住的 Cloud 任务。"
            ),
        )
    if uid is not None:
        user_n = job_store.count_jobs_by_status(DATA_DIR, active, user_id=str(uid))
        if user_n >= cfg.max_concurrent_per_user:
            raise HTTPException(
                status_code=429,
                detail=f"你的写码任务并发已满（{user_n}/{cfg.max_concurrent_per_user}），请等待完成或取消后再开。",
            )

    warnings: list[str] = []
    peers = job_store.active_jobs_on_repo(DATA_DIR, repo)
    if peers:
        who = ", ".join(
            f"{(p.get('username') or p.get('user_id') or '?')}[{p.get('status')}]" for p in peers[:5]
        )
        warnings.append(
            f"同仓库已有 {len(peers)} 个进行中的写码任务（{who}）。并行可能改到相同文件，合入时注意冲突。"
        )

    username = getattr(user, "username", None)
    work_branch = user_work_branch(
        branch_prefix=cfg.branch_prefix,
        username=username,
        user_id=uid,
        fixed_branch=cfg.work_branch,
    )
    # 一人一支：job.ref 固定为用户工作分支；Cloud 起始优先已有工作分支，否则从历史功能分支/默认分支分叉
    from cursor_dev.project_inspect import continuity_from_jobs

    continuity = continuity_from_jobs(
        DATA_DIR,
        repo,
        username=username,
        user_id=uid,
        preferred_work_branch=work_branch,
    )
    legacy = str(continuity.get("legacy_branch") or "").strip()
    base_ref = ""
    pre_work = resolve_starting_ref(repo, work_branch)
    if pre_work.get("ok") and pre_work.get("ref") == work_branch:
        base_ref = work_branch
    elif legacy:
        pre_legacy = resolve_starting_ref(repo, legacy)
        if pre_legacy.get("ok"):
            base_ref = legacy
        elif pre_legacy.get("soft"):
            base_ref = legacy
    if not base_ref:
        preferred_base = (cfg.starting_ref or "").strip() or None
        pre_base = resolve_starting_ref(repo, preferred_base)
        if pre_base.get("ok"):
            base_ref = str(pre_base.get("ref") or "")
        elif pre_work.get("soft"):
            base_ref = work_branch
        else:
            base_ref = preferred_base or "main"

    system_prompt = build_first_turn_prompt(
        user_message=message,
        repo=repo,
        work_branch=work_branch,
        base_ref=base_ref or "main",
        create_pr=bool(body.create_pr),
    )
    job = job_store.create_job(
        DATA_DIR,
        user_id=uid,
        username=username,
        thread_id=body.thread_id or "",
        repo=repo,
        ref=work_branch,
        message=message,
        create_pr=body.create_pr,
        system_prompt=system_prompt,
    )
    append_audit(
        DATA_DIR,
        {
            "event": "job_created",
            "job_id": job["id"],
            "user_id": job.get("user_id"),
            "username": job.get("username"),
            "repo": repo,
            "ref": work_branch,
            "base_ref": base_ref,
            "thread_id": job.get("thread_id"),
            "status": job.get("status"),
            "create_pr": bool(body.create_pr),
            "sdk_ready": ok,
            "sdk_reason": "" if ok else reason,
            "peer_jobs": len(peers),
        },
    )
    return _job_to_response(job, warnings=warnings)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_cursor_dev_job(job_id: str, auth: tuple = Depends(require_auth)):
    user = _auth_user(auth)
    job = job_store.get_job(DATA_DIR, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    uid = getattr(user, "user_id", None)
    # 有 user_id 时做归属校验；本地 AUTH_REQUIRED=false 的 user_id=0 仍可读
    if uid not in (None, 0, "0") and str(job.get("user_id") or "") not in ("", str(uid)):
        raise HTTPException(status_code=403, detail="无权查看该任务")
    return _job_to_response(job)


def _assert_job_owner(job: dict[str, Any], user) -> None:
    uid = getattr(user, "user_id", None)
    if uid not in (None, 0, "0") and str(job.get("user_id") or "") not in ("", str(uid)):
        raise HTTPException(status_code=403, detail="无权操作该任务")


@router.get("/jobs/{job_id}/stream")
async def stream_cursor_dev_job(job_id: str, auth: tuple = Depends(require_auth)):
    """执行 queued job 并通过 SSE 推送进度。不经过 Deep Agents。"""
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    from cursor_dev.service import run_job

    user = _auth_user(auth)
    job = job_store.get_job(DATA_DIR, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    _assert_job_owner(job, user)

    status = job.get("status")
    if status == "running":
        raise HTTPException(status_code=409, detail="任务正在执行中")
    # queued 首跑 / failed 重试 / idle_for_followup 经 messages 重新入队后也可 stream
    if status not in {"queued", "failed"}:
        raise HTTPException(
            status_code=409,
            detail=f"任务状态不可执行：{status}（续聊请先 POST /jobs/{{id}}/messages）",
        )

    cfg = reload_config()
    ok, reason = cfg.availability()
    if not ok:
        raise HTTPException(status_code=503, detail=reason or "写码车道不可用")

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def sink(event: dict[str, Any]) -> None:
        # run_job 在线程池；asyncio.Queue 须经 call_soon_threadsafe
        loop.call_soon_threadsafe(queue.put_nowait, event)

    async def produce() -> None:
        try:
            job_store.update_job(DATA_DIR, job_id, status="queued", error=None)
            fresh = job_store.get_job(DATA_DIR, job_id)
            await asyncio.to_thread(run_job, DATA_DIR, fresh, sink=sink, cfg=cfg)
        except Exception as exc:  # noqa: BLE001
            await queue.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
            job_store.update_job(DATA_DIR, job_id, status="failed", error=str(exc))
        finally:
            await queue.put({"type": "_end"})

    async def event_gen():
        task = asyncio.create_task(produce())
        try:
            yield f"data: {json.dumps({'type': 'status', 'text': '写码任务开始', 'phase': 'start'}, ensure_ascii=False)}\n\n"
            while True:
                event = await queue.get()
                if event.get("type") == "_end":
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
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


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_cursor_dev_job(
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
    append_audit(
        DATA_DIR,
        {
            "event": "job_cancel_requested",
            "job_id": job_id,
            "user_id": "" if getattr(user, "user_id", None) is None else str(user.user_id),
            "status": (updated or {}).get("status"),
            "reason": reason,
        },
    )
    return _job_to_response(updated or job)


@router.post("/jobs/{job_id}/messages", response_model=JobResponse)
async def followup_cursor_dev_job(
    job_id: str,
    body: FollowUpBody,
    auth: tuple = Depends(require_auth),
):
    """续聊：追加用户消息并重新入队，随后客户端再调 /stream。"""
    user = _auth_user(auth)
    cfg = reload_config()
    job = job_store.get_job(DATA_DIR, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    _assert_job_owner(job, user)

    if not body.confirmed:
        raise HTTPException(status_code=400, detail="须 confirmed=true")

    status = job.get("status")
    if status not in {"idle_for_followup", "failed", "succeeded"}:
        raise HTTPException(status_code=409, detail=f"当前状态不可续聊：{status}")

    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message 不能为空")
    if len(message) > _MAX_MESSAGE_LEN:
        raise HTTPException(status_code=400, detail=f"message 过长（>{_MAX_MESSAGE_LEN}）")

    ok, reason = cfg.availability()
    if not ok:
        raise HTTPException(status_code=503, detail=reason or "写码车道不可用")

    prior_as = ""
    for m in reversed(job.get("messages") or []):
        if m.get("role") == "assistant":
            prior_as = str(m.get("content") or "")
            break

    create_pr = job.get("create_pr") if body.create_pr is None else bool(body.create_pr)
    work_branch = (job.get("ref") or "").strip() or user_work_branch(
        branch_prefix=cfg.branch_prefix,
        username=job.get("username"),
        user_id=job.get("user_id"),
        fixed_branch=cfg.work_branch,
    )
    system_prompt = build_followup_prompt(
        user_message=message,
        repo=job.get("repo") or "",
        work_branch=work_branch,
        prior_assistant=prior_as,
        create_pr=bool(create_pr),
    )
    job_store.append_message(DATA_DIR, job_id, role="user", content=message)
    updated = job_store.update_job(
        DATA_DIR,
        job_id,
        status="queued",
        error=None,
        cancel_requested=False,
        system_prompt=system_prompt,
        create_pr=create_pr,
        ref=work_branch,
    )
    append_audit(
        DATA_DIR,
        {
            "event": "job_followup_queued",
            "job_id": job_id,
            "user_id": job.get("user_id"),
            "repo": job.get("repo"),
        },
    )
    return _job_to_response(updated or job)


@router.get("/audit")
async def cursor_dev_audit(
    limit: int = 50,
    event: str | None = None,
    repo: str | None = None,
    auth: tuple = Depends(require_auth),
):
    """写码审计列表（按当前用户过滤；本地无 user_id 时返回最近记录）。"""
    user = _auth_user(auth)
    uid = getattr(user, "user_id", None)
    rows = list_audit(
        DATA_DIR,
        limit=limit,
        event=event,
        user_id=str(uid) if uid not in (None, 0, "0") else None,
        repo=repo,
    )
    return {"items": rows, "count": len(rows)}
