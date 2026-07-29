"""
外部访问日志导入：解析网关/Nginx/JSONL/CSV → 统一写入 calls.jsonl（source=import）。
"""
from __future__ import annotations

import csv
import json
import re
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from tools.api_log_tool.call_store import append_api_call, path_pattern_key

# Nginx combined 风格（末尾可选 request_time 秒）
_NGINX_RE = re.compile(
    r"(?P<remote>\S+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+"
    r'"(?P<method>[A-Z]+)\s+(?P<path>[^"\s]+)(?:\s+HTTP/[\d.]+)?"\s+'
    r"(?P<status>\d{3})\s+(?P<size>\S+)"
    r"(?:\s+(?P<referer>\"[^\"]*\"|-))?"
    r"(?:\s+(?P<ua>\"[^\"]*\"|-))?"
    r"(?:\s+(?P<rt>[\d.]+))?"
)

_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
_MAX_IMPORT_LINES = 20000


def _parse_ts(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        if v > 1e12:
            return v / 1000.0
        return v
    s = str(value).strip()
    if not s:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return _parse_ts(float(s))
    for fmt in (
        "%d/%b/%Y:%H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y/%m/%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(s.replace("Z", "+0000"), fmt).timestamp()
        except ValueError:
            continue
    try:
        return parsedate_to_datetime(s).timestamp()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _status_ok(status: int | None) -> bool:
    if status is None:
        return False
    return 200 <= int(status) < 400


def _extract_path(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    if "://" in s:
        parts = urlsplit(s)
        path = parts.path or "/"
        if parts.query:
            return f"{path}?{parts.query}"
        return path
    return s


def normalize_external_row(row: dict[str, Any], *, source: str = "import") -> dict[str, Any] | None:
    """把任意字典归一成 calls.jsonl 行。"""
    if not isinstance(row, dict):
        return None

    method = str(
        row.get("method")
        or row.get("http_method")
        or row.get("verb")
        or row.get("req_method")
        or ""
    ).strip().upper()
    path = _extract_path(
        str(
            row.get("path")
            or row.get("uri")
            or row.get("url")
            or row.get("request_uri")
            or row.get("request_path")
            or row.get("endpoint")
            or ""
        )
    )
    if not path and row.get("request"):
        req = str(row.get("request") or "").strip().strip('"')
        parts = req.split()
        if len(parts) >= 2 and parts[0].upper() in _METHODS:
            method = parts[0].upper()
            path = _extract_path(parts[1])

    if not path:
        return None
    if method and method not in _METHODS:
        method = "GET"
    if not method:
        method = "GET"

    status_raw = (
        row.get("status")
        if row.get("status") is not None
        else row.get("status_code")
        if row.get("status_code") is not None
        else row.get("http_status")
        if row.get("http_status") is not None
        else row.get("code")
    )
    try:
        status = int(status_raw) if status_raw is not None and str(status_raw).strip() != "" else None
    except Exception:
        status = None

    lat_raw = (
        row.get("latency_ms")
        if row.get("latency_ms") is not None
        else row.get("duration_ms")
        if row.get("duration_ms") is not None
        else row.get("response_time_ms")
        if row.get("response_time_ms") is not None
        else row.get("rt_ms")
        if row.get("rt_ms") is not None
        else row.get("request_time")
        if row.get("request_time") is not None
        else row.get("elapsed")
    )
    latency_ms = 0.0
    if lat_raw is not None and str(lat_raw).strip() != "":
        try:
            latency_ms = float(lat_raw)
            # 仅当 latency 尚未换算、且带秒单位标记时才 ×1000
            if str(row.get("_latency_unit") or "") == "s" and row.get("latency_ms") is None:
                latency_ms = float(lat_raw) * 1000.0
            elif (
                row.get("request_time") is not None
                and row.get("latency_ms") is None
                and float(row["request_time"]) == float(lat_raw)
            ):
                latency_ms = float(lat_raw) * 1000.0
        except Exception:
            latency_ms = 0.0

    ts = _parse_ts(row.get("ts") or row.get("timestamp") or row.get("time") or row.get("@timestamp"))
    if ts is None:
        ts = time.time()

    error = row.get("error") or row.get("message") or row.get("err")
    if error is not None:
        error = str(error)[:200]
    ok = row.get("ok")
    if ok is None:
        ok = _status_ok(status)
    else:
        ok = bool(ok)

    return {
        "ts": ts,
        "method": method,
        "path": path,
        "path_key": path_pattern_key(path),
        "status": status,
        "ok": ok,
        "latency_ms": round(latency_ms, 1),
        "source": source,
        "error": error if (not ok and error) else (None if ok else (error or f"HTTP {status}")),
        "import_format": row.get("_format"),
    }


def parse_nginx_line(line: str) -> dict[str, Any] | None:
    m = _NGINX_RE.search(line.strip())
    if not m:
        return None
    gd = m.groupdict()
    status = int(gd["status"])
    rt = gd.get("rt")
    latency_ms = 0.0
    meta: dict[str, Any] = {"_format": "nginx"}
    if rt and re.fullmatch(r"[\d.]+", rt):
        # nginx $request_time 为秒 → 直接转毫秒写入 latency_ms
        latency_ms = float(rt) * 1000.0
        meta["request_time_sec"] = float(rt)
    return normalize_external_row(
        {
            "method": gd["method"],
            "path": gd["path"],
            "status": status,
            "latency_ms": latency_ms,
            "ts": _parse_ts(gd["time"]),
            **meta,
        }
    )


def parse_json_line(line: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(line)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    obj = dict(obj)
    obj["_format"] = "jsonl"
    return normalize_external_row(obj)


def detect_format(sample_lines: list[str]) -> str:
    non_empty = [x.strip() for x in sample_lines if x.strip()][:20]
    if not non_empty:
        return "unknown"
    json_hits = sum(1 for line in non_empty if line.startswith("{") and parse_json_line(line))
    nginx_hits = sum(1 for line in non_empty if _NGINX_RE.search(line))
    if json_hits >= max(1, len(non_empty) // 3):
        return "jsonl"
    if nginx_hits >= max(1, len(non_empty) // 3):
        return "nginx"
    first = non_empty[0].lower()
    if ("," in non_empty[0] or "\t" in non_empty[0]) and any(
        k in first for k in ("method", "path", "uri", "status", "url")
    ):
        return "csv"
    return "unknown"


def parse_csv_text(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sample = next((ln for ln in text.splitlines() if ln.strip()), "")
    dialect = csv.excel_tab if sample.count("\t") > sample.count(",") else csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    for raw in reader:
        if not raw:
            continue
        mapped = {str(k or "").strip().lower(): v for k, v in raw.items()}
        alias: dict[str, Any] = {
            "method": mapped.get("method") or mapped.get("http_method") or mapped.get("verb"),
            "path": mapped.get("path")
            or mapped.get("uri")
            or mapped.get("url")
            or mapped.get("request_uri"),
            "status": mapped.get("status")
            or mapped.get("status_code")
            or mapped.get("http_status")
            or mapped.get("code"),
            "latency_ms": mapped.get("latency_ms")
            or mapped.get("duration_ms")
            or mapped.get("response_time_ms"),
            "ts": mapped.get("ts") or mapped.get("timestamp") or mapped.get("time"),
            "error": mapped.get("error") or mapped.get("message"),
            "ok": mapped.get("ok"),
            "_format": "csv",
        }
        if mapped.get("request_time") and not alias["latency_ms"]:
            alias["request_time"] = mapped.get("request_time")
            alias["_latency_unit"] = "s"
            try:
                alias["latency_ms"] = float(mapped["request_time"]) * 1000.0
            except Exception:
                pass
        rec = normalize_external_row(alias)
        if rec:
            rows.append(rec)
    return rows


def parse_log_file(
    file_path: str,
    *,
    format: str = "auto",
    max_lines: int = 5000,
) -> dict[str, Any]:
    """解析外部日志文件，返回归一化记录（尚未写入）。"""
    p = Path(file_path).expanduser()
    if not p.is_file():
        return {"error": f"文件不存在: {file_path}"}

    max_lines = max(1, min(int(max_lines or 5000), _MAX_IMPORT_LINES))
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"error": f"读取失败: {e}"}

    lines = text.splitlines()
    fmt = (format or "auto").strip().lower()
    if fmt in ("", "auto", "detect"):
        fmt = detect_format(lines[:50])
        if fmt == "unknown":
            if lines and ("," in lines[0] or "\t" in lines[0]):
                fmt = "csv"
            else:
                return {
                    "error": "无法识别日志格式",
                    "hint": "支持 format=jsonl|nginx|csv；或使用含 method/path/status 的 JSON 行",
                    "sample_line": next((x for x in lines if x.strip()), "")[:200],
                }

    records: list[dict[str, Any]] = []
    skipped = 0
    if fmt == "csv":
        all_csv = parse_csv_text(text)
        records = all_csv[:max_lines]
        skipped = max(0, len(all_csv) - len(records))
    else:
        for line in lines:
            if not line.strip():
                continue
            if len(records) >= max_lines:
                skipped += 1
                continue
            if fmt == "jsonl":
                rec = parse_json_line(line)
            elif fmt == "nginx":
                rec = parse_nginx_line(line)
            else:
                rec = parse_json_line(line) or parse_nginx_line(line)
            if rec:
                records.append(rec)
            else:
                skipped += 1

    fail_n = sum(1 for r in records if not r.get("ok", True))
    return {
        "status": "ok",
        "format": fmt,
        "file_path": str(p.resolve()),
        "parsed": len(records),
        "skipped": skipped,
        "failures_in_file": fail_n,
        "records": records,
    }


def import_log_file(
    file_path: str,
    *,
    format: str = "auto",
    max_lines: int = 5000,
    source: str = "import",
    replace_previous: bool = True,
) -> dict[str, Any]:
    """解析并写入 calls.jsonl。

    replace_previous=True（默认）时先清除同 source 的旧导入，
    避免上次 nginx/jsonl 残留污染本次分析。
    """
    from tools.api_log_tool.call_store import (
        bind_run_id,
        clear_call_logs,
        new_run_id,
        set_last_run_id,
    )

    resolved = resolve_upload_path(file_path)
    if resolved.get("error"):
        return resolved
    path = str(resolved["path"])

    parsed = parse_log_file(path, format=format, max_lines=max_lines)
    if parsed.get("error"):
        return parsed
    records = list(parsed.get("records") or [])
    written = 0
    src = (source or "import").strip() or "import"
    run_id = new_run_id("import")
    cleared: dict[str, Any] | None = None
    if replace_previous:
        cleared = clear_call_logs(remove_sources={src})
    unique_keys: set[tuple[str, str]] = set()
    with bind_run_id(run_id):
        for rec in records:
            rec["source"] = src
            rec["run_id"] = run_id
            append_api_call(rec)
            written += 1
            unique_keys.add((str(rec.get("method") or "GET").upper(), str(rec.get("path_key") or "")))
    set_last_run_id(src, run_id)
    fail_n = sum(1 for r in records if not r.get("ok", True))
    return {
        "status": "ok",
        "format": parsed.get("format"),
        "file_path": parsed.get("file_path"),
        "resolved_from": resolved.get("resolved_from"),
        "imported": written,
        "endpoint_count": len(unique_keys),
        "endpoints": sorted(f"{m} {k}" for m, k in unique_keys),
        "skipped": parsed.get("skipped"),
        "failures_imported": fail_n,
        "source": src,
        "run_id": run_id,
        "replaced_previous": bool(replace_previous),
        "cleared_previous": (cleared or {}).get("removed", 0) if cleared else 0,
        "sample_failures": [
            {
                "method": r.get("method"),
                "path": r.get("path"),
                "path_key": r.get("path_key"),
                "status": r.get("status"),
                "error": r.get("error"),
                "latency_ms": r.get("latency_ms"),
            }
            for r in records
            if not r.get("ok", True)
        ][:15],
        "note": (
            f"已导入 {written} 条（{len(unique_keys)} 个接口形态）到 calls.jsonl"
            f"（source={src}, run_id={run_id}）"
            + ("；已清除同来源旧导入" if replace_previous else "")
            + "。请用 analyze_api_errors_from_logs(source_filter='import', run_id='latest') 分析；"
            "结论只基于本轮导入，勿编造未出现的接口。"
        ),
        "next": "analyze_api_errors_from_logs(source_filter='import', run_id='latest')",
    }


def resolve_upload_path(file_path: str) -> dict[str, Any]:
    """解析用户附件路径：绝对路径 / uploads 下文件名 / 模糊匹配。"""
    from config import Config

    raw = (file_path or "").strip().strip('"').strip("'")
    if not raw:
        return {"error": "请提供 file_path", "hint": "使用消息中的 [附件路径] 绝对路径"}

    candidates: list[Path] = []
    p = Path(raw).expanduser()
    candidates.append(p)
    if not p.is_absolute():
        candidates.append(Path(Config.DATA_DIR) / "uploads" / p.name)
        candidates.append(Path(Config.DATA_DIR) / "uploads" / raw)
        candidates.append(Path(Config.DATA_DIR) / "samples" / p.name)

    upload_dir = Path(Config.DATA_DIR) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    name = p.name
    # 精确文件名
    candidates.append(upload_dir / name)
    # 上传保存名常为 stem_timestamp.ext；按原始名模糊匹配最新
    stem = Path(name).stem
    ext = Path(name).suffix
    try:
        matches = sorted(
            upload_dir.glob(f"{stem}_*{ext}" if ext else f"{stem}_*"),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )
        candidates.extend(matches[:5])
        # 也匹配「原始名」出现在 saved_name 前缀的情况
        if stem:
            matches2 = sorted(
                [x for x in upload_dir.iterdir() if x.is_file() and stem in x.name],
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            )
            candidates.extend(matches2[:5])
    except Exception:
        pass

    seen: set[str] = set()
    for c in candidates:
        try:
            key = str(c.resolve()) if c.exists() else str(c)
        except Exception:
            key = str(c)
        if key in seen:
            continue
        seen.add(key)
        if c.is_file():
            return {
                "path": c.resolve(),
                "resolved_from": raw if str(c.resolve()) != str(Path(raw).expanduser()) else "as_is",
            }

    listing = []
    try:
        listing = sorted(
            [x.name for x in upload_dir.iterdir() if x.is_file()],
            key=lambda n: (upload_dir / n).stat().st_mtime,
            reverse=True,
        )[:8]
    except Exception:
        pass
    return {
        "error": f"文件路径在文件系统中未找到: {raw}",
        "hint": (
            "请使用上传接口返回的绝对路径（消息里的 [附件路径]）。"
            "也可只传文件名，将在 data/uploads/ 下查找。"
        ),
        "uploads_recent": listing,
        "upload_dir": str(upload_dir),
    }
