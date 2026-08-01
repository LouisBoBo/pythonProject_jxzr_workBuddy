"""全仓分批计划缓存（按 thread_id），避免把上百路径塞进模型上下文。"""
from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_PLANS: dict[str, dict[str, Any]] = {}
_TTL_SEC = 3600.0


def _key(thread_id: str) -> str:
    return str(thread_id or "").strip() or "_default"


def save_repo_plan(
    thread_id: str,
    *,
    workspace_root: str,
    files: list[str],
    batch_size: int = 5,
) -> dict[str, Any]:
    bs = max(1, int(batch_size or 5))
    paths = [str(p) for p in (files or []) if str(p).strip()]
    batches = [paths[i : i + bs] for i in range(0, len(paths), bs)] if paths else []
    plan = {
        "workspace_root": str(workspace_root or "").strip(),
        "files": paths,
        "batch_size": bs,
        "batch_count": len(batches),
        "total": len(paths),
        "batches": batches,
        "saved_at": time.time(),
    }
    with _lock:
        _PLANS[_key(thread_id)] = plan
    return {
        "total": plan["total"],
        "batch_size": bs,
        "batch_count": plan["batch_count"],
        "workspace_root": plan["workspace_root"],
    }


def get_repo_plan(thread_id: str) -> dict[str, Any] | None:
    with _lock:
        plan = _PLANS.get(_key(thread_id))
        if not plan:
            return None
        if time.time() - float(plan.get("saved_at") or 0) > _TTL_SEC:
            _PLANS.pop(_key(thread_id), None)
            return None
        return dict(plan)


def get_batch_paths(thread_id: str, batch_index: int) -> dict[str, Any]:
    plan = get_repo_plan(thread_id)
    if not plan:
        return {
            "status": "error",
            "message": "没有分批计划，请先调用 request_ide_list_source_files",
            "paths": [],
        }
    batches = plan.get("batches") or []
    n = len(batches)
    idx = int(batch_index)
    if idx < 0 or idx >= n:
        return {
            "status": "error",
            "message": f"batch_index 越界：{idx}（有效 0..{max(0, n - 1)}）",
            "paths": [],
            "batch_count": n,
            "total": plan.get("total"),
        }
    return {
        "status": "ok",
        "paths": list(batches[idx]),
        "batch_index": idx,
        "batch_count": n,
        "batch_size": plan.get("batch_size"),
        "total": plan.get("total"),
        "workspace_root": plan.get("workspace_root"),
        "done_after": idx + 1 >= n,
        "next_batch_index": None if idx + 1 >= n else idx + 1,
    }
