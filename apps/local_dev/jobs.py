"""本机写码任务落盘。"""
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
        "queued",
        "running",
        "succeeded",
        "failed",
        "cancelled",
    }
)


def jobs_dir(data_dir: Path) -> Path:
    d = Path(data_dir) / "local_dev" / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _job_path(data_dir: Path, job_id: str) -> Path:
    safe = "".join(c for c in job_id if c.isalnum() or c in "-_")
    if not safe or safe != job_id:
        raise ValueError("invalid job_id")
    return jobs_dir(data_dir) / f"{safe}.json"


def new_job_id() -> str:
    return f"ldj-{uuid.uuid4().hex[:16]}"


def create_job(
    data_dir: Path,
    *,
    user_id: str | int | None,
    username: str | None,
    thread_id: str,
    workspace: str,
    message: str,
    empty_target: bool = False,
) -> dict[str, Any]:
    now = int(time.time())
    job: dict[str, Any] = {
        "id": new_job_id(),
        "user_id": "" if user_id is None else str(user_id),
        "username": username or "",
        "thread_id": thread_id or "",
        "workspace": workspace,
        "empty_target": bool(empty_target),
        "status": "queued",
        "messages": [{"role": "user", "content": message, "at": now}],
        "sandbox_path": None,
        "changed_files": [],
        "synced_files": [],
        "preview_url": None,
        "preview": None,
        "error": None,
        "cancel_requested": False,
        "runtime": "local_sandbox",
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
        # 已取消：禁止再写成 queued/running/succeeded/failed（后台线程收尾不得覆盖）
        if cur_status == "cancelled" and new_status is not None and str(new_status) != "cancelled":
            fields = {k: v for k, v in fields.items() if k != "status"}
            if not fields:
                return job
        # 用户已点取消但状态尚未落到 cancelled 时，同样禁止成功收尾
        if job.get("cancel_requested") and new_status is not None:
            if str(new_status) in {"queued", "running", "succeeded"}:
                fields = {k: v for k, v in fields.items() if k != "status"}
                if not fields:
                    return job
        for k, v in fields.items():
            job[k] = v
        job["updated_at"] = int(time.time())
        path = _job_path(data_dir, job_id)
        path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        return job


def try_claim_job(data_dir: Path, job_id: str) -> dict[str, Any] | None:
    """原子抢占：queued|failed → running。并发 SSE 时仅一个成功，其余返回 None。"""
    with _lock:
        job = get_job(data_dir, job_id)
        if not job:
            return None
        if job.get("cancel_requested") or str(job.get("status") or "") == "cancelled":
            return None
        st = str(job.get("status") or "")
        if st not in {"queued", "failed"}:
            return None
        job["status"] = "running"
        job["error"] = None
        job["cancel_requested"] = False
        job["updated_at"] = int(time.time())
        path = _job_path(data_dir, job_id)
        path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        return job


def request_cancel(data_dir: Path, job_id: str, reason: str = "用户取消") -> dict[str, Any] | None:
    return update_job(
        data_dir,
        job_id,
        cancel_requested=True,
        error=reason,
        status="cancelled",
    )


def is_cancel_requested(data_dir: Path, job_id: str) -> bool:
    job = get_job(data_dir, job_id)
    return bool(job and job.get("cancel_requested"))


def count_jobs_by_status(
    data_dir: Path,
    statuses: set[str] | frozenset[str],
    *,
    user_id: str | None = None,
) -> int:
    n = 0
    for p in jobs_dir(data_dir).glob("*.json"):
        try:
            job = json.loads(p.read_text(encoding="utf-8"))
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
    statuses: set[str] | frozenset[str] | None = None,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in jobs_dir(data_dir).glob("*.json"):
        try:
            job = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if statuses is not None and job.get("status") not in statuses:
            continue
        if user_id is not None and str(job.get("user_id") or "") != str(user_id):
            continue
        out.append(job)
    out.sort(key=lambda j: int(j.get("updated_at") or 0), reverse=True)
    return out


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
