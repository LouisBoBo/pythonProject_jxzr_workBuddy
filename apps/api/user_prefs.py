"""按登录用户落盘的轻量偏好（与整站 settings.json 分离）。"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()

_SAFE_USER = re.compile(r"[^a-zA-Z0-9._@+-]+")


def prefs_dir(data_dir: Path) -> Path:
    d = Path(data_dir) / "user_prefs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_username(username: str | None) -> str:
    raw = (username or "anonymous").strip() or "anonymous"
    cleaned = _SAFE_USER.sub("_", raw)[:120]
    return cleaned or "anonymous"


def prefs_path(data_dir: Path, username: str | None) -> Path:
    return prefs_dir(data_dir) / f"{_safe_username(username)}.json"


def load_prefs(data_dir: Path, username: str | None) -> dict[str, Any]:
    path = prefs_path(data_dir, username)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_prefs(data_dir: Path, username: str | None, patch: dict[str, Any]) -> dict[str, Any]:
    """合并写入偏好；只保留已知键。"""
    allowed = {"last_local_workspace"}
    with _lock:
        cur = load_prefs(data_dir, username)
        for k, v in (patch or {}).items():
            if k not in allowed:
                continue
            if v is None:
                cur.pop(k, None)
            else:
                cur[k] = str(v).strip() if k == "last_local_workspace" else v
        path = prefs_path(data_dir, username)
        path.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
        return dict(cur)


def get_last_local_workspace(data_dir: Path, username: str | None) -> str:
    return str(load_prefs(data_dir, username).get("last_local_workspace") or "").strip()


def set_last_local_workspace(data_dir: Path, username: str | None, path: str) -> str:
    cleaned = str(path or "").strip()
    save_prefs(data_dir, username, {"last_local_workspace": cleaned or None})
    return cleaned
