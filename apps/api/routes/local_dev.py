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
    write_scope: list[str] = Field(
        default_factory=list,
        description="可选写范围：相对工程根的文件/目录路径；空=不限制（整仓可同步）",
    )
    file_paths: list[str] = Field(
        default_factory=list,
        description="本轮截图/附件路径（上传目录内）；用于注入【截图理解】",
    )


class ScopeConfirmBody(BaseModel):
    decision: str = Field(
        ...,
        description="include=同步范围外文件；skip=仅保留已同步范围内文件",
    )


class CommitConfirmBody(BaseModel):
    decision: str = Field(
        ...,
        description="commit=提交工作分支；skip=跳过提交（文件仍已同步）",
    )
    commit_message: str = Field(
        "",
        description="git 提交说明（中文，概括本次修改）；decision=commit 时必填",
    )
    push: bool | None = Field(
        None,
        description=(
            "是否 push 到远程工作分支。"
            "人触发 commit_batch：默认 true（完整闭环）；"
            "传 false=仅本地 commit。"
            "未传时回落 LOCAL_DEV_COMMIT_PUSH。"
        ),
    )
    remote_url: str = Field(
        "",
        description="可选：对话框填写的远程仓地址（HTTPS 或 SSH）；有则按此推送，不必事先 git remote add",
    )
    save_remote: bool = Field(
        False,
        description="是否把 remote_url 写入本地 origin（下次默认可推）",
    )


class CommitBatchBody(BaseModel):
    workspace: str = Field(..., min_length=1, description="本机工程根绝对路径")
    message: str = Field("", description="用户原话（如「提交今天的代码」）")
    thread_id: str = Field("", description="会话 thread_id")
    today_only: bool = Field(
        True,
        description="优先只汇总今日已成功同步的文件；若为空则放宽到该工作区历史同步批",
    )
    files: list[str] = Field(
        default_factory=list,
        description="可选：已由 prepare 汇总的相对路径；传入则跳过再汇总",
    )


class CommitBatchPrepareBody(BaseModel):
    workspace: str = Field(..., min_length=1, description="本机工程根绝对路径")
    today_only: bool = Field(True, description="优先只汇总今日已成功同步的文件")


class DeployPrepareBody(BaseModel):
    message: str = Field("", description="用户原话（如「部署到预发」）")
    env: str = Field("", description="目标环境；空则从原话猜测（默认 staging）")
    ref: str = Field("", description="可选：已推送的 branch / tag / commit")
    thread_id: str = Field("", description="会话 thread_id")


class WorkspaceTreeBody(BaseModel):
    workspace: str = Field(..., min_length=1, description="工程根绝对路径")
    subdir: str = Field("", description="相对工程根的子目录，空=根")


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
    commit_gate: dict[str, Any] | None = Field(
        None, description="提交门禁结果（awaiting_commit / commit_batch 时有）"
    )
    commit_decision: str | None = Field(None, description="commit | skip | 空")
    commit_result: dict[str, Any] | None = Field(
        None, description="git 提交结果（ok/skipped/error/commit 等）"
    )


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
    gate = job.get("commit_gate") if isinstance(job.get("commit_gate"), dict) else None
    decision = job.get("commit_decision")
    commit_result = (
        job.get("commit_result") if isinstance(job.get("commit_result"), dict) else None
    )
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
        commit_gate=gate,
        commit_decision=str(decision) if decision else None,
        commit_result=commit_result,
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
    active = {"queued", "running", "awaiting_scope", "awaiting_commit"}
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

    image_paths: list[str] = []
    try:
        agent_root = Path(__file__).resolve().parents[2] / "agent"
        if str(agent_root) not in sys.path:
            sys.path.insert(0, str(agent_root))
        from tools.upload_paths import sanitize_client_file_paths  # type: ignore

        image_paths = sanitize_client_file_paths(
            [str(p).strip() for p in (body.file_paths or []) if str(p).strip()],
            data_dir=DATA_DIR,
        )
    except Exception:
        image_paths = []

    job = job_store.create_job(
        DATA_DIR,
        user_id=uid,
        username=username,
        thread_id=(body.thread_id or "").strip(),
        workspace=check["path"],
        message=message,
        empty_target=bool(check.get("empty")),
        runtime=runtime,
        write_scope=list(body.write_scope or []),
        file_paths=image_paths,
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
    "/workspace/tree",
    summary="浏览工程目录树（下钻）",
    description="列出工程下一层文件/文件夹；用于写码确认卡勾选写范围。不下钻敏感与依赖目录。",
)
async def workspace_tree(body: WorkspaceTreeBody, auth: tuple = Depends(require_auth)):
    _auth_user(auth)
    check = validate_workspace(body.workspace)
    if not check.get("ok"):
        raise HTTPException(status_code=400, detail=check.get("error") or "目标目录无效")
    from local_dev.path_scope import list_workspace_entries

    return list_workspace_entries(Path(check["path"]), subdir=body.subdir or "")


@router.post(
    "/jobs/{job_id}/confirm-scope",
    response_model=JobResponse,
    summary="确认是否同步写范围外文件",
    description="任务处于 awaiting_scope 时：include 一并同步；skip 仅保留范围内已同步文件。",
)
async def confirm_local_dev_scope(
    job_id: str,
    body: ScopeConfirmBody,
    auth: tuple = Depends(require_auth),
):
    user = _auth_user(auth)
    job = job_store.get_job(DATA_DIR, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    _assert_job_owner(job, user)
    if str(job.get("status") or "") != "awaiting_scope":
        raise HTTPException(status_code=409, detail="当前任务不在等待范围确认状态")
    if job.get("scope_decision") in {"include", "skip"}:
        raise HTTPException(status_code=409, detail="范围确认已提交，请勿重复操作")
    decision = str(body.decision or "").strip().lower()
    if decision not in {"include", "skip"}:
        raise HTTPException(status_code=400, detail="decision 须为 include 或 skip")
    updated = job_store.update_job(DATA_DIR, job_id, scope_decision=decision)
    final = updated or job
    if str(final.get("scope_decision") or "") != decision:
        raise HTTPException(status_code=409, detail="范围确认已被其他请求处理")
    return _job_to_response(final)


@router.post(
    "/jobs/{job_id}/confirm-commit",
    response_model=JobResponse,
    summary="确认是否提交到工作分支（可选推远程）",
    description=(
        "任务处于 awaiting_commit 时："
        "commit=在工作分支提交本批文件（须门禁 can_commit，且须中文提交说明）；"
        "push=true（默认，人触发提交批次）时再 push 到 origin 工作分支；"
        "push=false 仅本地 commit；"
        "skip=跳过提交，文件仍保留在目标目录。"
        "不合主干；不经模型。"
    ),
)
async def confirm_local_dev_commit(
    job_id: str,
    body: CommitConfirmBody,
    auth: tuple = Depends(require_auth),
):
    user = _auth_user(auth)
    job = job_store.get_job(DATA_DIR, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    _assert_job_owner(job, user)
    from local_dev.batch_commit import ensure_push_retry_confirmable

    job = ensure_push_retry_confirmable(
        DATA_DIR, job_id, user_id=str(getattr(user, "user_id", "") or "")
    ) or job
    if str(job.get("status") or "") != "awaiting_commit":
        raise HTTPException(status_code=409, detail="当前任务不在等待提交确认状态")
    if job.get("commit_decision") in {"commit", "skip"}:
        raise HTTPException(status_code=409, detail="提交确认已提交，请勿重复操作")
    decision = str(body.decision or "").strip().lower()
    if decision not in {"commit", "skip"}:
        raise HTTPException(status_code=400, detail="decision 须为 commit 或 skip")
    gate = job.get("commit_gate") if isinstance(job.get("commit_gate"), dict) else {}
    if decision == "commit" and not gate.get("can_commit"):
        raise HTTPException(
            status_code=400,
            detail="审码门禁未通过或非 git 仓，不能提交；请选择 skip 或修复后再写码",
        )
    commit_msg = (body.commit_message or "").strip()
    if decision == "commit":
        from local_dev.git_commit import is_push_retry_needed, validate_chinese_commit_message

        cr = job.get("commit_result") if isinstance(job.get("commit_result"), dict) else {}
        # 推送重试：说明仅作展示，过长/污染时用上次成功 commit 的短说明
        if is_push_retry_needed(cr):
            cleaned = commit_msg
            if "推送失败" in cleaned:
                cleaned = cleaned.split("推送失败", 1)[0].rstrip("：:。. \t")
            cleaned = cleaned.strip()[:200]
            prior = str(cr.get("message") or "").strip()
            if "推送失败" in prior:
                prior = prior.split("推送失败", 1)[0].rstrip("：:。. \t")
            prior = prior[:200]
            commit_msg = cleaned or prior or "已提交本批改动"
        else:
            ok_msg, msg_err = validate_chinese_commit_message(commit_msg)
            if not ok_msg:
                raise HTTPException(status_code=400, detail=msg_err)
    updated = job_store.update_job(
        DATA_DIR,
        job_id,
        commit_decision=decision,
        commit_message=commit_msg if decision == "commit" else None,
    )
    final = updated or job
    if str(final.get("commit_decision") or "") != decision:
        raise HTTPException(status_code=409, detail="提交确认已被其他请求处理")

    # 人触发的 commit_batch：确认后由 API 直执 git（不经 run_job / 模型）
    if str(final.get("runtime") or "") == "commit_batch":
        from local_dev.batch_commit import finalize_commit_batch
        from local_dev.config import get_config as _ld_cfg

        cfg = _ld_cfg()
        # 人触发提交批次：未传 push 时默认推远程；显式 false=仅本地；env 显式=0 可关掉默认推
        if decision != "commit":
            do_push = False
        elif body.push is not None:
            do_push = bool(body.push)
        else:
            raw_push = os.getenv("LOCAL_DEV_COMMIT_PUSH")
            if raw_push is not None and str(raw_push).strip() != "":
                do_push = bool(cfg.commit_push)
            else:
                do_push = True
        done = finalize_commit_batch(
            DATA_DIR,
            job_id,
            decision,
            push=do_push,
            push_url=(body.remote_url or "").strip() or None,
            save_remote=bool(body.save_remote),
            commit_message=commit_msg if decision == "commit" else None,
        )
        if not done.get("ok"):
            raise HTTPException(status_code=400, detail=done.get("error") or "提交收尾失败")
        return _job_to_response(done.get("job") or job_store.get_job(DATA_DIR, job_id) or final)

    return _job_to_response(final)


@router.post(
    "/commit-batch/prepare",
    summary="人触发提交：仅汇总本批文件",
    description=(
        "快速返回本批已同步文件清单，供前端展示过程步骤；"
        "随后再调 /commit-batch 做审码门禁。不创建提交任务。"
    ),
)
async def prepare_local_dev_commit_batch(
    body: CommitBatchPrepareBody,
    auth: tuple = Depends(require_auth),
):
    user = _auth_user(auth)
    cfg = get_config()
    if not cfg.enabled:
        raise HTTPException(status_code=503, detail="本机写码未开启")
    check = validate_workspace(body.workspace)
    if not check.get("ok"):
        raise HTTPException(status_code=400, detail=check.get("error") or "目标目录无效")
    from local_dev.batch_commit import prepare_commit_batch

    uid = getattr(user, "user_id", None)
    result = prepare_commit_batch(
        DATA_DIR,
        user_id=uid,
        workspace=check["path"],
        today_only=bool(body.today_only),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "无法汇总本批文件")
    return result


@router.post(
    "/commit-batch",
    summary="人触发：审本批已同步文件并进入提交确认",
    description=(
        "不自动挂在写码收尾上。"
        "可先调 /commit-batch/prepare；也可直接本接口汇总。"
        "做本机路径批审门禁后创建 commit_batch 任务（awaiting_commit）。"
        "若已有待确认提交任务，自动跳过旧任务并以本批为准（避免丢确认卡后无法再提交）。"
        "不取消进行中的写码任务；不经 Deep Agents / 全仓 GitHub / IDE Bridge。"
    ),
)
async def start_local_dev_commit_batch(
    body: CommitBatchBody,
    auth: tuple = Depends(require_auth),
):
    user = _auth_user(auth)
    cfg = get_config()
    if not cfg.enabled:
        raise HTTPException(status_code=503, detail="本机写码未开启")
    check = validate_workspace(body.workspace)
    if not check.get("ok"):
        raise HTTPException(status_code=400, detail=check.get("error") or "目标目录无效")

    from local_dev.batch_commit import start_commit_batch

    uid = getattr(user, "user_id", None)
    username = getattr(user, "username", None)
    pre_files = [str(p).strip() for p in (body.files or []) if str(p).strip()]
    result = start_commit_batch(
        DATA_DIR,
        user_id=uid,
        username=username,
        thread_id=(body.thread_id or "").strip(),
        workspace=check["path"],
        message=(body.message or "").strip() or "提交本批代码",
        today_only=bool(body.today_only),
        allow_blocked=bool(cfg.commit_allow_blocked),
        files=pre_files or None,
    )
    if not result.get("ok"):
        err = result.get("error") or "无法启动提交批次"
        # 兼容旧客户端：若仍带回待确认 job_id，用结构化 detail 便于前端恢复确认卡
        if result.get("job_id"):
            raise HTTPException(
                status_code=409,
                detail={
                    "message": err,
                    "code": "pending_commit",
                    "job_id": result.get("job_id"),
                },
            )
        raise HTTPException(status_code=400, detail=err)
    job = result.get("job") or {}
    gate = result.get("commit_gate") or {}
    return {
        "ok": True,
        "job_id": job.get("id"),
        "status": job.get("status"),
        "workspace": job.get("workspace"),
        "files": result.get("files") or [],
        "commit_gate": gate,
        "runtime": "commit_batch",
        "superseded_job_ids": result.get("superseded_job_ids") or [],
    }


@router.get(
    "/deploy/status",
    summary="自动化部署：查询开关与白名单",
    description=(
        "只读配置探测，不触发 CI/SSH、不改仓。"
        "默认 DEPLOY_ENABLED=0；与写码/提交批/审码车道独立。"
        "ci_provider 为 github_actions（默认）或 local_ssh（本机 SSH 旁路）。"
    ),
)
async def local_dev_deploy_status(auth: tuple = Depends(require_auth)):
    _auth_user(auth)
    from local_dev.deploy_config import get_deploy_config

    cfg = get_deploy_config()
    if cfg.enabled:
        summary = (
            "部署能力已开启；确认后走本机 SSH 同步"
            if cfg.ci_provider == "local_ssh"
            else "部署能力已开启；确认卡确认后才触发 Actions"
        )
    else:
        summary = "部署能力默认关闭；识别到「部署到预发」时仅提示配置，不会发版"
    return {
        "ok": True,
        "runtime": "deploy",
        "enabled": bool(cfg.enabled),
        "env_whitelist": list(cfg.env_whitelist),
        "allow_production": bool(cfg.allow_production),
        "ci_provider": cfg.ci_provider,
        "github_workflow": cfg.github_workflow,
        "github_repo": cfg.github_repo,
        "require_pushed_ref": bool(cfg.require_pushed_ref),
        "can_trigger_ci": False,
        "summary": summary,
    }


@router.post(
    "/deploy/prepare",
    summary="自动化部署：门禁探测（不触发发布）",
    description=(
        "识别部署意图后的准备接口：检查总开关、环境白名单，以及当前提供方配置。"
        "github_actions：须 workflow / 仓库；can_trigger_ci 还须 Token。"
        "local_ssh：须本机项目路径与 SSH 主机/用户/私钥路径/远端目录。"
        "本接口本身不触发任何发布。不经 Deep Agents；与 commit_batch / code_review 分离。"
    ),
)
async def prepare_local_dev_deploy(
    body: DeployPrepareBody,
    auth: tuple = Depends(require_auth),
):
    _auth_user(auth)
    from local_dev.deploy_prepare import prepare_deploy

    return prepare_deploy(
        message=(body.message or "").strip(),
        env=(body.env or "").strip() or None,
        ref=(body.ref or "").strip() or None,
    )


class DeployConfirmBody(BaseModel):
    decision: str = Field(
        ...,
        description="confirm=触发 CI；cancel/skip=取消，不触发",
    )
    message: str = Field("", description="用户原话（可选）")
    env: str = Field("", description="目标环境，默认 staging")
    ref: str = Field("", description="已推送的 branch/tag/commit；空则用默认工作分支")


@router.post(
    "/deploy/confirm",
    summary="自动化部署：确认后触发发布（或取消）",
    description=(
        "人点确认卡后由 API 直执发布，不经模型。"
        "github_actions → workflow_dispatch；local_ssh → 本机构建 + SSH/rsync（后台任务）。"
        "默认须 DEPLOY_ENABLED=1；仅白名单环境；短窗防双击。cancel 不触发任何发布。"
    ),
)
async def confirm_local_dev_deploy(
    body: DeployConfirmBody,
    auth: tuple = Depends(require_auth),
):
    user = _auth_user(auth)
    from local_dev.deploy_confirm import confirm_deploy

    result = confirm_deploy(
        decision=(body.decision or "").strip(),
        message=(body.message or "").strip(),
        env=(body.env or "").strip() or None,
        ref=(body.ref or "").strip() or None,
        user_id=getattr(user, "user_id", None),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "部署确认失败")
    return result


class DeployPollBody(BaseModel):
    repo: str = Field("", description="owner/repo；空则用系统配置 DEPLOY_GITHUB_REPO（local_ssh 可空）")
    run_id: str = Field("", description="Actions run id 或本机任务 id（local-…）；有则精确查询")
    workflow: str = Field("", description="无 run_id 时用 workflow 查最近一次（仅 github_actions）")
    ref: str = Field("", description="可选：按分支过滤最近 run")


@router.post(
    "/deploy/poll",
    summary="自动化部署：查询运行状态",
    description=(
        "P1-3c：轮询发布状态。"
        "github_actions：查 GitHub run；暂不可达时返回 unreachable（HTTP 200）。"
        "local_ssh：按 run_id（local-…）查本机后台任务。"
        "不经模型；github 路径不改本地代码；local_ssh 仅用临时 worktree。"
    ),
)
async def poll_local_dev_deploy(
    body: DeployPollBody,
    auth: tuple = Depends(require_auth),
):
    _auth_user(auth)
    from local_dev.deploy_config import get_deploy_config
    from local_dev.deploy_github import find_latest_workflow_run, get_workflow_run_status
    from local_dev.deploy_local_ssh import get_local_ssh_run_status

    cfg = get_deploy_config()
    # 禁止客户端指定任意 repo 蹭服务端 Token 查别人仓库
    repo = (cfg.github_repo or "").strip()
    client_repo = (body.repo or "").strip()
    if client_repo and repo and client_repo != repo:
        raise HTTPException(status_code=400, detail="仓库须与系统配置 DEPLOY_GITHUB_REPO 一致")
    if client_repo and not repo:
        raise HTTPException(
            status_code=400,
            detail="未配置 DEPLOY_GITHUB_REPO，拒绝客户端指定仓库（防 Token 越权查询）",
        )
    run_id = (body.run_id or "").strip()
    workflow = (body.workflow or "").strip() or cfg.github_workflow
    ref = (body.ref or "").strip()

    # 本机 SSH：仅接受格式正确的 local-* run_id，避免误入 GitHub 查询或探测
    if run_id.startswith("local-") or cfg.ci_provider == "local_ssh":
        if not run_id:
            raise HTTPException(status_code=400, detail="本机 SSH 部署请提供 run_id")
        out = get_local_ssh_run_status(run_id)
        return {"runtime": "deploy", "poll_timeout_sec": cfg.poll_timeout_sec, **out}

    if not repo:
        raise HTTPException(status_code=400, detail="未配置仓库（DEPLOY_GITHUB_REPO）")
    if run_id:
        out = get_workflow_run_status(repo=repo, run_id=run_id)
    elif workflow:
        out = find_latest_workflow_run(repo=repo, workflow=workflow, ref=ref)
    else:
        raise HTTPException(status_code=400, detail="请提供 run_id 或 workflow")
    # 可达性问题用 200 + ok=false，避免前端当硬错误打断轮询
    return {"runtime": "deploy", "poll_timeout_sec": cfg.poll_timeout_sec, **out}


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
    if str(job.get("runtime") or "") == "commit_batch":
        raise HTTPException(
            status_code=409,
            detail="提交批次任务请用确认提交接口，不能走写码 SSE",
        )
    if status == "awaiting_commit":
        raise HTTPException(
            status_code=409,
            detail="任务正在等待提交确认，请先确认或跳过",
        )
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
