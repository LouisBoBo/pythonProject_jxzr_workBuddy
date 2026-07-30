"""IDE Bridge 安全审计（JSONL，对齐 write_store 风格）。

存储：data/ide_bridge/audit.jsonl
不记录文件正文 / token / 密钥内容。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from config import Config
from ha.fs_lock import InterProcessLock, instance_id

_LOCK = InterProcessLock("ide-bridge-audit")
AUDIT_MAX_LINES = int(os.getenv("IDE_BRIDGE_AUDIT_MAX_LINES", "50000"))


def _audit_path() -> Path:
    d = Path(Config.DATA_DIR) / "ide_bridge"
    d.mkdir(parents=True, exist_ok=True)
    return d / "audit.jsonl"


def append_ide_audit(record: dict[str, Any]) -> None:
    """追加一行审计；失败不影响主流程。"""
    try:
        body = {
            "ts": time.time(),
            "instance_id": instance_id(),
            **record,
        }
        # 禁止把正文/密钥写进审计
        for k in ("file_contents", "content", "token", "authorization", "password"):
            body.pop(k, None)
        line = json.dumps(body, ensure_ascii=False, default=str) + "\n"
        path = _audit_path()
        with _LOCK:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
            _maybe_rotate(path)
    except Exception:
        pass


def _maybe_rotate(path: Path) -> None:
    if AUDIT_MAX_LINES <= 0 or not path.exists():
        return
    try:
        if path.stat().st_size < 2_000_000:
            return
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) <= AUDIT_MAX_LINES:
            return
        keep = lines[-AUDIT_MAX_LINES:]
        bak = path.with_suffix(path.suffix + ".1")
        if bak.exists():
            bak.unlink()
        path.rename(bak)
        path.write_text("\n".join(keep) + "\n", encoding="utf-8")
    except Exception:
        pass


def query_ide_audit(
    *,
    user_id: Any = None,
    event: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    path = _audit_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if user_id is not None and str(row.get("user_id")) != str(user_id):
            continue
        if event and row.get("event") != event:
            continue
        out.append(row)
        if len(out) >= max(1, min(limit, 200)):
            break
    return out
