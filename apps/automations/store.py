"""自动化任务本地落盘（定义 + 运行记录）。"""
from __future__ import annotations

import json
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from automations.schedule import enrich_automation_schedule

_lock = threading.Lock()

STATUSES = frozenset({"active", "paused"})
MAX_RUN_RECORDS = 100


def _safe_automation_id(automation_id: str) -> str | None:
    safe = "".join(c for c in automation_id if c.isalnum() or c in "-_")
    if not safe or safe != automation_id:
        return None
    return safe


def _repo_root_for_cwds() -> Path | None:
    apps = Path(__file__).resolve().parents[1]
    agent = apps / "agent"
    agent_str = str(agent)
    if agent_str not in sys.path:
        sys.path.insert(0, agent_str)
    try:
        from bundle_root import resolve_repo_root

        root = resolve_repo_root()
        return root.resolve() if root.is_dir() else None
    except Exception:
        return None


def _sanitize_cwds(cwds_raw: list) -> list[str]:
    """工作目录须落在 ZR WorkBuddy 仓库内，防止周报 git 扫任意路径。"""
    repo = _repo_root_for_cwds()
    if repo is None:
        return []
    out: list[str] = []
    for raw in cwds_raw:
        text = str(raw or "").strip()
        if not text or "\x00" in text:
            continue
        try:
            resolved = Path(text).expanduser().resolve()
        except OSError:
            continue
        if not resolved.is_dir():
            continue
        try:
            resolved.relative_to(repo)
        except ValueError:
            continue
        out.append(str(resolved))
        if len(out) >= 8:
            break
    return out


def automations_dir(data_dir: Path) -> Path:
    d = Path(data_dir) / "automations"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _definitions_path(data_dir: Path) -> Path:
    return automations_dir(data_dir) / "automations.json"


def _runs_path(data_dir: Path) -> Path:
    return automations_dir(data_dir) / "runs.json"


def _new_id() -> str:
    return f"auto-{uuid.uuid4().hex[:16]}"


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file() or path.stat().st_size <= 0:
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, type(default)) else default
    except (OSError, json.JSONDecodeError):
        return default


def _write_json_atomic(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def list_automations(data_dir: Path) -> list[dict[str, Any]]:
    items = _read_json(_definitions_path(data_dir), [])
    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict) and item.get("id"):
            out.append(item)
    out.sort(key=lambda x: int(x.get("updated_at") or x.get("created_at") or 0), reverse=True)
    return out


def get_automation(data_dir: Path, automation_id: str) -> dict[str, Any] | None:
    safe = _safe_automation_id(automation_id)
    if not safe:
        return None
    for item in list_automations(data_dir):
        if item.get("id") == automation_id:
            return item
    return None


def create_automation(data_dir: Path, fields: dict[str, Any]) -> dict[str, Any]:
    now = int(time.time())
    status = str(fields.get("status") or "active").strip().lower()
    if status not in STATUSES:
        status = "active"
    schedule_type = str(fields.get("schedule_type") or "recurring").strip().lower()
    if schedule_type not in {"recurring", "once"}:
        schedule_type = "recurring"
    cwds_raw = fields.get("cwds") or []
    cwds = _sanitize_cwds(cwds_raw if isinstance(cwds_raw, list) else [])
    item: dict[str, Any] = {
        "id": _new_id(),
        "name": str(fields.get("name") or "未命名任务").strip()[:120] or "未命名任务",
        "prompt": str(fields.get("prompt") or "").strip()[:8000],
        "status": status,
        "schedule_type": schedule_type,
        "rrule": str(fields.get("rrule") or "").strip()[:500],
        "scheduled_at": fields.get("scheduled_at"),
        "valid_from": fields.get("valid_from"),
        "valid_until": fields.get("valid_until"),
        "cwds": cwds,
        "push_to_wecom": bool(fields.get("push_to_wecom")),
        "next_run_at": fields.get("next_run_at"),
        "last_run_at": fields.get("last_run_at"),
        "created_at": now,
        "updated_at": now,
    }
    item = enrich_automation_schedule(item)
    with _lock:
        items = list_automations(data_dir)
        items.append(item)
        _write_json_atomic(_definitions_path(data_dir), items)
    return item


def update_automation(data_dir: Path, automation_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    safe_id = _safe_automation_id(automation_id)
    if not safe_id:
        return None
    with _lock:
        items = list_automations(data_dir)
        idx = next((i for i, x in enumerate(items) if x.get("id") == safe_id), None)
        if idx is None:
            return None
        item = dict(items[idx])
        if "name" in fields:
            item["name"] = str(fields["name"] or "").strip()[:120] or item.get("name") or "未命名任务"
        if "prompt" in fields:
            item["prompt"] = str(fields["prompt"] or "").strip()[:8000]
        if "status" in fields:
            st = str(fields["status"] or "").strip().lower()
            if st in STATUSES:
                item["status"] = st
        if "schedule_type" in fields:
            st = str(fields["schedule_type"] or "").strip().lower()
            if st in {"recurring", "once"}:
                item["schedule_type"] = st
        for key in ("rrule", "scheduled_at", "valid_from", "valid_until", "next_run_at", "last_run_at"):
            if key in fields:
                item[key] = fields[key]
        if "cwds" in fields:
            cwds_raw = fields.get("cwds") or []
            item["cwds"] = _sanitize_cwds(cwds_raw if isinstance(cwds_raw, list) else [])
        if "push_to_wecom" in fields:
            item["push_to_wecom"] = bool(fields["push_to_wecom"])
        item["updated_at"] = int(time.time())
        schedule_keys = {
            "status",
            "schedule_type",
            "rrule",
            "scheduled_at",
            "valid_from",
            "valid_until",
        }
        if schedule_keys.intersection(fields.keys()) and "next_run_at" not in fields:
            item = enrich_automation_schedule(item)
        items[idx] = item
        _write_json_atomic(_definitions_path(data_dir), items)
        return item


def delete_automation(data_dir: Path, automation_id: str) -> bool:
    safe_id = _safe_automation_id(automation_id)
    if not safe_id:
        return False
    with _lock:
        items = list_automations(data_dir)
        new_items = [x for x in items if x.get("id") != safe_id]
        if len(new_items) == len(items):
            return False
        _write_json_atomic(_definitions_path(data_dir), new_items)
        return True


def _trim_run_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """运行记录只保留最新 MAX_RUN_RECORDS 条（按 started_at 降序）。"""
    valid = [x for x in items if isinstance(x, dict) and x.get("id")]
    valid.sort(key=lambda x: int(x.get("started_at") or 0), reverse=True)
    return valid[:MAX_RUN_RECORDS]


def list_runs(
    data_dir: Path,
    *,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[dict[str, Any]], int]:
    items = _read_json(_runs_path(data_dir), [])
    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict) and item.get("id"):
            out.append(item)
    out.sort(key=lambda x: int(x.get("started_at") or 0), reverse=True)
    total = len(out)
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    start = (page - 1) * page_size
    return out[start : start + page_size], total


def append_run(data_dir: Path, record: dict[str, Any]) -> dict[str, Any]:
    now = int(time.time())
    item = {
        "id": f"run-{uuid.uuid4().hex[:16]}",
        "automation_id": str(record.get("automation_id") or ""),
        "automation_name": str(record.get("automation_name") or ""),
        "status": str(record.get("status") or "pending"),
        "started_at": int(record.get("started_at") or now),
        "finished_at": record.get("finished_at"),
        "summary": str(record.get("summary") or "")[:4000],
        "error": str(record.get("error") or "")[:2000] or None,
        "thread_id": record.get("thread_id"),
        "cwd": record.get("cwd"),
        "delivery_status": record.get("delivery_status"),
        "delivered_at": record.get("delivered_at"),
        "delivery_error": record.get("delivery_error"),
    }
    with _lock:
        items = _read_json(_runs_path(data_dir), [])
        items.append(item)
        items = _trim_run_records(items)
        _write_json_atomic(_runs_path(data_dir), items)
    return item


def update_run(data_dir: Path, run_id: str, **fields: Any) -> dict[str, Any] | None:
    with _lock:
        items = _read_json(_runs_path(data_dir), [])
        idx = next((i for i, x in enumerate(items) if x.get("id") == run_id), None)
        if idx is None:
            return None
        row = dict(items[idx])
        for key, val in fields.items():
            if val is not None or key in {
                "error",
                "finished_at",
                "summary",
                "delivery_error",
                "delivered_at",
                "delivery_status",
            }:
                row[key] = val
        items[idx] = row
        items = _trim_run_records(items)
        _write_json_atomic(_runs_path(data_dir), items)
        return row
