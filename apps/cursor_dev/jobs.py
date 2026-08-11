"""写码任务 / 会话落盘（与 LangGraph checkpoint 隔离）。"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_lock = threading.Lock()

STATUSES = frozenset(
    {
        "draft",
        "confirmed",
        "queued",
        "running",
        "idle_for_followup",
        "awaiting_pr_confirm",
        "creating_pr",
        "succeeded",
        "failed",
        "cancelled",
    }
)


def jobs_dir(data_dir: Path) -> Path:
    d = data_dir / "cursor_dev" / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _job_path(data_dir: Path, job_id: str) -> Path:
    safe = "".join(c for c in job_id if c.isalnum() or c in "-_")
    if not safe or safe != job_id:
        raise ValueError("invalid job_id")
    return jobs_dir(data_dir) / f"{safe}.json"


def new_job_id() -> str:
    return f"cdj-{uuid.uuid4().hex[:16]}"


def create_job(
    data_dir: Path,
    *,
    user_id: str | int | None,
    username: str | None,
    thread_id: str,
    repo: str,
    ref: str,
    message: str,
    create_pr: bool,
    system_prompt: str,
    file_paths: list[str] | None = None,
) -> dict[str, Any]:
    now = int(time.time())
    paths = [str(p).strip() for p in (file_paths or []) if str(p).strip()]
    job: dict[str, Any] = {
        "id": new_job_id(),
        "user_id": "" if user_id is None else str(user_id),
        "username": username or "",
        "thread_id": thread_id or "",
        "repo": repo,
        "ref": ref or "",
        "status": "queued",
        "create_pr": bool(create_pr),
        "messages": [
            {
                "role": "user",
                "content": message,
                "at": now,
            }
        ],
        "system_prompt": system_prompt,
        # 上传截图本地路径：run_job 时转成 Cloud prompt.images
        "file_paths": paths,
        "agent_id": None,
        "run_id": None,
        "pr_url": None,
        "review_job_id": None,
        "runtime": "cloud",
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    with _lock:
        path = _job_path(data_dir, job["id"])
        path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    return job


def get_job(data_dir: Path, job_id: str) -> dict[str, Any] | None:
    try:
        path = _job_path(data_dir, job_id)
    except ValueError:
        return None
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def update_job(data_dir: Path, job_id: str, **fields: Any) -> dict[str, Any] | None:
    with _lock:
        job = get_job(data_dir, job_id)
        if not job:
            return None
        cur_status = str(job.get("status") or "")
        new_status = fields.get("status")
        # cancelled 禁止复活为 active（须新建 job）；failed/idle/succeeded 允许 queued 重试或续聊
        if cur_status == "cancelled" and new_status is not None:
            if str(new_status) in {"queued", "running", "creating_pr"}:
                return job
        # 已请求取消且仍在 active：禁止清 flag / 改回 running（防取消后幽灵复活）
        # 若已是 failed 且显式 cancel_requested=False + queued，视为合法「重试写码」
        if job.get("cancel_requested") and cur_status in {"queued", "running", "creating_pr"}:
            if fields.get("cancel_requested") is False:
                fields = {**fields}
                fields.pop("cancel_requested", None)
            if fields.get("status") in {"queued", "running", "creating_pr"}:
                fields = {**fields, "status": "cancelled"}
        elif job.get("cancel_requested") and cur_status == "failed":
            # 重试路径会带 cancel_requested=False；未带则保持 failed 不可偷偷改回 running
            if fields.get("cancel_requested") is not False and new_status in {
                "queued",
                "running",
                "creating_pr",
            }:
                return job
        for k, v in fields.items():
            if k == "id":
                continue
            if k == "status" and v is not None and str(v) not in STATUSES:
                raise ValueError(f"invalid status: {v}")
            job[k] = v
        job["updated_at"] = int(time.time())
        path = _job_path(data_dir, job_id)
        path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        return job


def append_message(data_dir: Path, job_id: str, *, role: str, content: str) -> dict[str, Any] | None:
    with _lock:
        job = get_job(data_dir, job_id)
        if not job:
            return None
        msgs = list(job.get("messages") or [])
        msgs.append({"role": role, "content": content, "at": int(time.time())})
        job["messages"] = msgs
        job["updated_at"] = int(time.time())
        path = _job_path(data_dir, job_id)
        path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        return job


def count_jobs_by_status(data_dir: Path, statuses: set[str], *, user_id: str | None = None) -> int:
    n = 0
    for path in jobs_dir(data_dir).glob("cdj-*.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if job.get("status") not in statuses:
            continue
        # 已请求取消但状态尚未落 cancelled 的，不占并发（兼容旧数据）
        if job.get("cancel_requested") and job.get("status") in {
            "queued",
            "running",
            "creating_pr",
        }:
            continue
        if user_id is not None and str(job.get("user_id") or "") != str(user_id):
            continue
        n += 1
    return n


def list_jobs(
    data_dir: Path,
    *,
    statuses: set[str] | None = None,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in jobs_dir(data_dir).glob("cdj-*.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if statuses is not None and job.get("status") not in statuses:
            continue
        if user_id is not None and str(job.get("user_id") or "") != str(user_id):
            continue
        out.append(job)
    return out


def cancel_abandoned_queued(
    data_dir: Path,
    *,
    user_id: str | None = None,
    reason: str = "被新写码任务取代（未执行的 queued）",
) -> list[str]:
    """取消仍停在 queued、从未真正跑起来的任务，避免占满每人并发。"""
    cancelled: list[str] = []
    for job in list_jobs(data_dir, statuses={"queued"}, user_id=user_id):
        jid = job.get("id")
        if not jid:
            continue
        # 已有 agent_id 说明曾启动过，留给 running 路径处理
        if job.get("agent_id") or job.get("run_id"):
            continue
        update_job(data_dir, jid, status="cancelled", error=reason)
        cancelled.append(jid)
    return cancelled


def finalize_cancel_requested(data_dir: Path, *, user_id: str | None = None) -> list[str]:
    """把已标 cancel_requested 但仍占 queued/running 的任务落成 cancelled，释放并发。"""
    done: list[str] = []
    for job in list_jobs(data_dir, statuses={"queued", "running", "creating_pr"}, user_id=user_id):
        if not job.get("cancel_requested"):
            continue
        jid = str(job.get("id") or "")
        if not jid:
            continue
        update_job(
            data_dir,
            jid,
            status="cancelled",
            error=job.get("error") or "用户取消",
            cancel_requested=True,
        )
        done.append(jid)
    return done


def request_cancel(data_dir: Path, job_id: str, *, reason: str = "用户取消") -> dict[str, Any] | None:
    """标记取消并立刻释放并发名额。

    queued / running / creating_pr → 直接 status=cancelled（执行线程靠
    cancel_requested / status=cancelled 轮询退出）。若仅设 cancel_requested
    而保持 running，停止后重试会卡在「不可续聊：running」+「并发已满」。
    """
    job = get_job(data_dir, job_id)
    if not job:
        return None
    status = job.get("status")
    if status in {"succeeded", "cancelled", "failed"}:
        return job
    return update_job(
        data_dir,
        job_id,
        status="cancelled",
        error=reason or "用户取消",
        cancel_requested=True,
    )


def is_cancel_requested(data_dir: Path, job_id: str) -> bool:
    job = get_job(data_dir, job_id)
    if not job:
        return True
    if job.get("cancel_requested"):
        return True
    return job.get("status") == "cancelled"


def find_reusable_followup_job(
    data_dir: Path,
    *,
    thread_id: str,
    repo: str,
    user_id: str | int | None = None,
) -> dict[str, Any] | None:
    """同会话 + 同仓可续聊的 job（优先带 agent_id，便于 Cloud resume 免重拉仓）。

    新会话 thread_id 不同 → 返回 None，走新建 Agent。
    """
    tid = (thread_id or "").strip()
    repo_n = (repo or "").strip()
    if not tid or not repo_n:
        return None
    uid = "" if user_id is None else str(user_id)
    best: dict[str, Any] | None = None
    best_score = -1
    for job in list_jobs(
        data_dir,
        statuses={"idle_for_followup", "succeeded"},
    ):
        if str(job.get("thread_id") or "").strip() != tid:
            continue
        if str(job.get("repo") or "").strip() != repo_n:
            continue
        if uid and str(job.get("user_id") or "") not in ("", uid, "0"):
            # 有明确 user_id 时校验归属；空/0 本地免登录放行
            if str(job.get("user_id") or "") != uid:
                continue
        if job.get("cancel_requested"):
            continue
        aid = str(job.get("agent_id") or "").strip()
        updated = int(job.get("updated_at") or job.get("created_at") or 0)
        # 有 agent_id 大幅加分；同档比更新时间
        score = updated + (1_000_000_000 if aid else 0)
        if score > best_score:
            best_score = score
            best = job
    return best


def active_jobs_on_repo(
    data_dir: Path,
    repo: str,
    *,
    exclude_job_id: str | None = None,
) -> list[dict[str, Any]]:
    """同仓仍在跑/排队的任务（多人冲突提示用）。"""
    repo = (repo or "").strip()
    out: list[dict[str, Any]] = []
    for job in list_jobs(data_dir, statuses={"queued", "running", "creating_pr"}):
        if job.get("cancel_requested"):
            continue
        if str(job.get("repo") or "") != repo:
            continue
        if exclude_job_id and job.get("id") == exclude_job_id:
            continue
        out.append(job)
    return out
