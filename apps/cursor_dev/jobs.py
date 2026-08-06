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
) -> dict[str, Any]:
    now = int(time.time())
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


def request_cancel(data_dir: Path, job_id: str, *, reason: str = "用户取消") -> dict[str, Any] | None:
    """标记取消：queued 立即 cancelled；running 设 cancel_requested 供执行线程轮询。"""
    job = get_job(data_dir, job_id)
    if not job:
        return None
    status = job.get("status")
    if status in {"succeeded", "cancelled", "failed"}:
        return job
    if status == "queued" and not job.get("agent_id") and not job.get("run_id"):
        return update_job(data_dir, job_id, status="cancelled", error=reason, cancel_requested=True)
    return update_job(data_dir, job_id, cancel_requested=True, error=reason)


def is_cancel_requested(data_dir: Path, job_id: str) -> bool:
    job = get_job(data_dir, job_id)
    if not job:
        return True
    if job.get("cancel_requested"):
        return True
    return job.get("status") == "cancelled"


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
        if str(job.get("repo") or "") != repo:
            continue
        if exclude_job_id and job.get("id") == exclude_job_id:
            continue
        out.append(job)
    return out
