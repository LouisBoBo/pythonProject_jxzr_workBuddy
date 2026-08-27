"""自动化运行时状态（防并发双跑）。"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

_lock = threading.Lock()


def _runtime_path(data_dir: Path) -> Path:
    d = Path(data_dir) / "automations"
    d.mkdir(parents=True, exist_ok=True)
    return d / "runtime.json"


def _read(data_dir: Path) -> dict[str, Any]:
    path = _runtime_path(data_dir)
    if not path.is_file() or path.stat().st_size <= 0:
        return {"running": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("running", {})
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"running": {}}


def _write(data_dir: Path, payload: dict[str, Any]) -> None:
    path = _runtime_path(data_dir)
    tmp = path.with_suffix(".tmp")
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def is_running(data_dir: Path, automation_id: str) -> bool:
    with _lock:
        data = _read(data_dir)
        return automation_id in (data.get("running") or {})


def mark_running(data_dir: Path, automation_id: str, run_id: str) -> bool:
    with _lock:
        data = _read(data_dir)
        running = dict(data.get("running") or {})
        if automation_id in running:
            return False
        running[automation_id] = {"run_id": run_id, "started_at": int(time.time())}
        data["running"] = running
        _write(data_dir, data)
        return True


def clear_running(data_dir: Path, automation_id: str, run_id: str | None = None) -> None:
    with _lock:
        data = _read(data_dir)
        running = dict(data.get("running") or {})
        cur = running.get(automation_id)
        if not cur:
            return
        if run_id and cur.get("run_id") != run_id:
            return
        running.pop(automation_id, None)
        data["running"] = running
        _write(data_dir, data)
