"""写码车道审计（追加 JSONL）。"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def _audit_path(data_dir: Path) -> Path:
    root = data_dir / "cursor_dev"
    root.mkdir(parents=True, exist_ok=True)
    return root / "audit.jsonl"


def append_audit(data_dir: Path, event: dict[str, Any]) -> None:
    row = {"ts": int(time.time()), **event}
    path = _audit_path(data_dir)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def list_audit(
    data_dir: Path,
    *,
    limit: int = 50,
    event: str | None = None,
    user_id: str | None = None,
    repo: str | None = None,
) -> list[dict[str, Any]]:
    """倒序读取最近审计（新在前）。"""
    path = _audit_path(data_dir)
    if not path.is_file():
        return []
    limit = max(1, min(int(limit or 50), 500))
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if event and str(row.get("event") or "") != event:
            continue
        if user_id is not None and str(row.get("user_id") or "") != str(user_id):
            continue
        if repo and str(row.get("repo") or "") != str(repo):
            continue
        rows.append(row)
        if len(rows) >= limit:
            break
    return rows
