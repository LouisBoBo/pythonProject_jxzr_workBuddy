"""
ERP 出站调用日志落盘（JSONL）。

仅记录助手 → 平台 HTTP 调用，不含 Authorization。
失败写盘不影响主请求返回。

支持 run_id：探活 / 外部导入按轮次隔离，汇总可默认只看本轮。
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

from config import Config
from ha.fs_lock import InterProcessLock, instance_id

_LOCK = InterProcessLock("api_calls")
CALL_LOG_MAX_LINES = int(os.getenv("API_CALL_LOG_MAX_LINES", "50000"))
_run_id_ctx: ContextVar[str | None] = ContextVar("api_call_run_id", default=None)


def _root() -> Path:
    root = Path(Config.DATA_DIR) / "api_calls"
    root.mkdir(parents=True, exist_ok=True)
    return root


def call_log_path() -> Path:
    return _root() / "calls.jsonl"


def last_run_path() -> Path:
    return _root() / "last_run.json"


def new_run_id(prefix: str = "run") -> str:
    """生成一轮探活/导入的 run_id，例 probe_20260729_093015_a1b2c3。"""
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "", (prefix or "run").strip()) or "run"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{safe}_{stamp}_{uuid.uuid4().hex[:6]}"


@contextmanager
def bind_run_id(run_id: str | None) -> Iterator[str | None]:
    """在上下文内 append_api_call 自动带上 run_id（显式传入优先）。"""
    token = _run_id_ctx.set(run_id)
    try:
        yield run_id
    finally:
        _run_id_ctx.reset(token)


def set_last_run_id(source: str, run_id: str) -> None:
    """记录某 source 最近一轮 run_id，供 summarize/analyze 默认 latest。"""
    src = (source or "").strip().lower()
    rid = (run_id or "").strip()
    if not src or not rid:
        return
    path = last_run_path()
    with _LOCK:
        data: dict[str, Any] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8") or "{}")
            except Exception:
                data = {}
        if not isinstance(data, dict):
            data = {}
        runs = data.get("runs") if isinstance(data.get("runs"), dict) else {}
        runs[src] = rid
        data["runs"] = runs
        data["updated_at"] = datetime.now().isoformat(timespec="seconds")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_last_run_id(source: str | None = None) -> str | None:
    src = (source or "").strip().lower() or None
    path = last_run_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return None
    runs = data.get("runs") if isinstance(data, dict) else None
    if not isinstance(runs, dict):
        return None
    if src:
        rid = runs.get(src)
        return str(rid) if rid else None
    # 无 source：优先 sandbox，再 import，再任意
    for key in ("sandbox", "probe", "import"):
        if runs.get(key):
            return str(runs[key])
    for v in runs.values():
        if v:
            return str(v)
    return None


def resolve_run_id_filter(
    run_id: str | None,
    *,
    source: str | None = None,
    default: str = "all",
) -> str | None:
    """把工具参数解析成具体 run_id；返回 None 表示不过滤。

    - ``all`` / 空：不过滤
    - ``latest``：取该 source 最近一轮（无则不过滤，避免误空结果）
    - 其它：按字面匹配
    """
    raw = default if run_id is None else str(run_id).strip()
    if not raw or raw.lower() in ("all", "*", "any"):
        return None
    if raw.lower() == "latest":
        return get_last_run_id(source)
    return raw

def clear_call_logs(
    *,
    keep_sources: set[str] | None = None,
    remove_sources: set[str] | None = None,
) -> dict[str, Any]:
    """清理调用日志。

    - 默认（二者皆空）：清空全部
    - keep_sources：仅保留这些 source（如 {"erp"}）
    - remove_sources：只删除这些 source（如 {"import"}），其余保留
      （与 keep_sources 同时传入时以 remove_sources 为准）
    """
    path = call_log_path()
    keep_sources = keep_sources or set()
    remove_sources = remove_sources or set()
    removed = 0
    kept = 0
    with _LOCK:
        if not path.exists():
            return {"status": "ok", "removed": 0, "kept": 0, "log_path": str(path)}
        if not keep_sources and not remove_sources:
            try:
                removed = sum(1 for _ in path.open("r", encoding="utf-8") if _.strip())
            except Exception:
                removed = 0
            path.write_text("", encoding="utf-8")
            return {"status": "ok", "removed": removed, "kept": 0, "log_path": str(path)}
        lines_out: list[str] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    removed += 1
                    continue
                src = str((row or {}).get("source") or "")
                if remove_sources:
                    drop = src in remove_sources
                else:
                    drop = src not in keep_sources
                if drop:
                    removed += 1
                else:
                    lines_out.append(line)
                    kept += 1
        except Exception:
            path.write_text("", encoding="utf-8")
            return {"status": "ok", "removed": removed, "kept": 0, "log_path": str(path)}
        path.write_text(("\n".join(lines_out) + ("\n" if lines_out else "")), encoding="utf-8")
    return {"status": "ok", "removed": removed, "kept": kept, "log_path": str(path)}


def normalize_path(path: str) -> str:
    """去掉 fragment；保留 path；query 排序后归一（便于聚合）。"""
    raw = (path or "").strip()
    if not raw:
        return ""
    if "://" in raw:
        parts = urlsplit(raw)
        path_only = parts.path or "/"
        query = parts.query
    else:
        if "?" in raw:
            path_only, query = raw.split("?", 1)
        else:
            path_only, query = raw, ""
        path_only = path_only or "/"
    # 去掉尾部多余 /（根路径除外）
    if len(path_only) > 1 and path_only.endswith("/"):
        path_only = path_only.rstrip("/")
    if query:
        # 简单排序 query 键，不解码复杂值
        items = []
        for pair in query.split("&"):
            if not pair:
                continue
            if "=" in pair:
                k, v = pair.split("=", 1)
            else:
                k, v = pair, ""
            items.append((k, v))
        items.sort(key=lambda x: (x[0], x[1]))
        query = "&".join(f"{k}={v}" if v != "" else k for k, v in items)
        return f"{path_only}?{query}"
    return path_only


# OpenAPI / 路由模板段：{order_id}、{id}、{userId} 等一律归一为 {id}
_PATH_TEMPLATE_SEG = re.compile(r"^\{[^{}]+\}$")
_UUID_SEG = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def path_pattern_key(path: str) -> str:
    """路径模板键：便于目录 × 日志聚合。

    通用规则（与具体业务参数名无关）：
    - 数字段、UUID 段 → ``{id}``
    - OpenAPI/路由模板段 ``{任意名}`` → ``{id}``（``{order_id}`` 与 ``{id}`` 视为同一形态）
    - 其余字面量段保持不变
    """
    p = normalize_path(path).split("?", 1)[0]
    parts = []
    for seg in p.split("/"):
        if not seg:
            parts.append(seg)
            continue
        if re.fullmatch(r"\d+", seg) or _UUID_SEG.fullmatch(seg) or _PATH_TEMPLATE_SEG.fullmatch(seg):
            parts.append("{id}")
        else:
            parts.append(seg)
    return "/".join(parts) or "/"


def append_api_call(record: dict[str, Any]) -> None:
    """追加一行；任何异常吞掉，绝不影响业务请求。"""
    try:
        row = dict(record)
        row.setdefault("ts", time.time())
        path = str(row.get("path") or "")
        row["path"] = normalize_path(path) if path else ""
        if not row.get("path_key"):
            row["path_key"] = path_pattern_key(row["path"])
        else:
            row["path_key"] = path_pattern_key(str(row["path_key"]))
        # 脱敏：禁止落 token
        row.pop("authorization", None)
        row.pop("token", None)
        # run_id：显式优先，否则取上下文（探活/导入绑定）
        if not row.get("run_id"):
            ctx_rid = _run_id_ctx.get()
            if ctx_rid:
                row["run_id"] = ctx_rid
        row.setdefault("instance_id", instance_id())
        line = json.dumps(row, ensure_ascii=False, default=str) + "\n"
        path_file = call_log_path()
        with _LOCK:
            with open(path_file, "a", encoding="utf-8") as f:
                f.write(line)
            _maybe_rotate(path_file)
    except Exception:
        pass


def _maybe_rotate(path: Path) -> None:
    if CALL_LOG_MAX_LINES <= 0 or not path.exists():
        return
    try:
        if path.stat().st_size < 2_000_000:
            return
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) <= CALL_LOG_MAX_LINES:
            return
        keep = lines[-CALL_LOG_MAX_LINES :]
        bak = path.with_suffix(path.suffix + ".1")
        if bak.exists():
            bak.unlink()
        path.rename(bak)
        path.write_text("\n".join(keep) + "\n", encoding="utf-8")
    except Exception:
        pass


def query_api_calls(
    *,
    method: str | None = None,
    path_keyword: str | None = None,
    ok: bool | None = None,
    source: str | None = None,
    run_id: str | None = None,
    since_ts: float | None = None,
    until_ts: float | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    path = call_log_path()
    empty = {
        "items": [],
        "returned": 0,
        "has_more": False,
        "offset": offset,
        "limit": limit,
        "log_path": str(path),
        "run_id_filter": run_id,
    }
    if not path.exists():
        return empty

    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    method_u = (method or "").strip().upper() or None
    kw = (path_keyword or "").strip().lower() or None
    src = (source or "").strip().lower() or None
    rid = (run_id or "").strip() or None
    need = offset + limit + 1
    matched: list[dict[str, Any]] = []

    with _LOCK:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return empty

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        try:
            ts = float(row.get("ts") or 0)
        except Exception:
            ts = 0.0
        if since_ts is not None and ts < float(since_ts):
            break
        if until_ts is not None and ts >= float(until_ts):
            continue
        if method_u and str(row.get("method") or "").upper() != method_u:
            continue
        if src and str(row.get("source") or "").lower() != src:
            continue
        if rid and str(row.get("run_id") or "") != rid:
            continue
        if kw:
            blob = f"{row.get('path') or ''} {row.get('path_key') or ''}".lower()
            if kw not in blob:
                continue
        if ok is not None and bool(row.get("ok")) is not bool(ok):
            continue
        matched.append(row)
        if len(matched) >= need:
            break

    page = matched[offset : offset + limit]
    return {
        "items": page,
        "returned": len(page),
        "has_more": len(matched) > offset + limit,
        "offset": offset,
        "limit": limit,
        "log_path": str(path),
        "since_ts": since_ts,
        "until_ts": until_ts,
        "source_filter": src,
        "run_id_filter": rid,
    }


def default_since_ts(lookback_days: int = 7) -> float:
    days = max(1, int(lookback_days or 7))
    return (datetime.now() - timedelta(days=days)).timestamp()
