"""可选只读 SQL（默认关）：表白名单 + SELECT-only + 强制 LIMIT + 超时。

开启：环境变量或系统配置 READONLY_SQL_ENABLED=true，并配置 READONLY_SQL_DSN
与 READONLY_SQL_TABLE_WHITELIST（逗号分隔表名）。

用途：API 覆盖不到的聚合/对账；禁止 DDL/DML；不替代受控写操作。
"""
from __future__ import annotations

import os
import re
import sqlite3
from typing import Annotated, Any

_MAX_ROWS = 200
_DEFAULT_LIMIT = 50
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|MERGE|"
    r"GRANT|REVOKE|EXEC|EXECUTE|CALL|INTO\s+OUTFILE|LOAD\s+DATA)\b",
    re.IGNORECASE,
)
_SELECT_HEAD = re.compile(r"^\s*(WITH\b[\s\S]+?\)\s*)?SELECT\b", re.IGNORECASE)
_FROM_TABLE = re.compile(
    r"\b(?:FROM|JOIN)\s+([`\"\[]?)([A-Za-z_][\w$]*)\1?",
    re.IGNORECASE,
)


def readonly_sql_enabled() -> bool:
    try:
        from config import Config

        return bool(getattr(Config, "READONLY_SQL_ENABLED", False))
    except Exception:
        return os.getenv("READONLY_SQL_ENABLED", "").lower() in ("1", "true", "yes")


def _whitelist() -> set[str]:
    raw = ""
    try:
        from config import Config

        raw = str(getattr(Config, "READONLY_SQL_TABLE_WHITELIST", "") or "")
    except Exception:
        raw = os.getenv("READONLY_SQL_TABLE_WHITELIST", "") or ""
    return {t.strip().lower() for t in raw.split(",") if t.strip()}


def _dsn() -> str:
    try:
        from config import Config

        return str(getattr(Config, "READONLY_SQL_DSN", "") or "").strip()
    except Exception:
        return (os.getenv("READONLY_SQL_DSN") or "").strip()


def validate_readonly_sql(
    sql: str,
    *,
    whitelist: set[str] | None = None,
    max_limit: int = _MAX_ROWS,
) -> dict[str, Any]:
    """校验 SQL；通过则返回 {ok, sql, limit, tables}，否则 {error, ...}。"""
    text = (sql or "").strip().rstrip(";")
    if not text:
        return {"error": "SQL 为空"}
    if ";" in text:
        return {"error": "禁止多语句；只允许单条 SELECT"}
    if _FORBIDDEN.search(text):
        return {"error": "禁止非只读语句（DDL/DML/存储过程等）"}
    if not _SELECT_HEAD.search(text):
        return {"error": "只允许 SELECT（可含 WITH … SELECT）"}

    tables = {m.group(2).lower() for m in _FROM_TABLE.finditer(text)}
    wl = whitelist if whitelist is not None else _whitelist()
    if not wl:
        return {
            "error": "未配置表白名单 READONLY_SQL_TABLE_WHITELIST，拒绝执行",
            "hint": "在系统配置填写逗号分隔表名后再试",
        }
    bad = sorted(t for t in tables if t not in wl)
    if bad:
        return {
            "error": f"表不在白名单：{', '.join(bad)}",
            "whitelist": sorted(wl),
            "tables_in_sql": sorted(tables),
        }
    if not tables:
        return {"error": "未能从 SQL 解析出 FROM/JOIN 表名，拒绝执行"}

    lim = _DEFAULT_LIMIT
    m = re.search(r"\bLIMIT\s+(\d+)\b", text, re.IGNORECASE)
    if m:
        lim = min(int(m.group(1)), max_limit)
        # 规范化过大 LIMIT
        text = re.sub(
            r"\bLIMIT\s+\d+\b",
            f"LIMIT {lim}",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        lim = min(_DEFAULT_LIMIT, max_limit)
        text = f"{text} LIMIT {lim}"

    return {"ok": True, "sql": text, "limit": lim, "tables": sorted(tables)}


def _run_sqlite(dsn: str, sql: str, timeout_sec: float) -> dict[str, Any]:
    # sqlite: path 或 :memory:；禁止任意 URI 附件
    path = dsn
    if dsn.lower().startswith("sqlite:///"):
        path = dsn[10:]
    elif dsn.lower().startswith("sqlite://"):
        path = dsn[9:]
    if path not in (":memory:",) and (".." in path or path.startswith("~")):
        # 允许绝对/相对路径，但拒绝明显穿越写法的简化：仍 resolve
        from pathlib import Path

        try:
            resolved = Path(path).expanduser().resolve()
            path = str(resolved)
        except Exception:
            return {"error": "无效的 SQLite 路径"}

    conn = sqlite3.connect(path, timeout=timeout_sec)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        records = [dict(zip(cols, row, strict=False)) for row in rows]
        return {
            "ok": True,
            "columns": cols,
            "records": records,
            "returned": len(records),
            "driver": "sqlite",
        }
    finally:
        conn.close()


def execute_validated_sql(sql: str) -> dict[str, Any]:
    """执行已通过 validate_readonly_sql 的语句。"""
    dsn = _dsn()
    if not dsn:
        return {
            "error": "未配置 READONLY_SQL_DSN",
            "hint": "仅支持 sqlite 路径或 sqlite:///…（本期）；生产库请走只读从库账号",
        }
    timeout = float(os.getenv("READONLY_SQL_TIMEOUT_SEC", "8") or "8")
    low = dsn.lower()
    if low.startswith("sqlite") or low.endswith(".db") or low.endswith(".sqlite") or low == ":memory:" or "/" in dsn:
        return _run_sqlite(dsn, sql, timeout)
    return {
        "error": "本期只读 SQL 仅支持 SQLite DSN；其它引擎请后续扩展",
        "dsn_scheme": dsn.split(":", 1)[0] if ":" in dsn else "path",
    }


def readonly_sql(
    sql: Annotated[
        str,
        "只读 SELECT（可 WITH）；须引用白名单表；无 LIMIT 时自动补 LIMIT",
    ],
    note: Annotated[
        str,
        "用途说明（审计），如「工序在制对账」",
    ] = "",
) -> dict:
    """受控只读 SQL 查询（默认未挂载；须 READONLY_SQL_ENABLED）。

    不替代 HTTP 实体查询；用于 API 无聚合/跨表时的统计与对账。
    """
    if not readonly_sql_enabled():
        return {
            "error": "只读 SQL 未开启",
            "hint": "在系统配置打开「只读 SQL」并配置 DSN 与表白名单；默认应走 HTTP 查数。",
        }
    checked = validate_readonly_sql(sql)
    if checked.get("error"):
        return checked
    out = execute_validated_sql(str(checked["sql"]))
    if out.get("error"):
        return out
    # 审计（失败不挡）
    try:
        from tools.api_log_tool.call_store import append_api_call
        from middleware.request_context import get_thread_id, get_username

        append_api_call(
            {
                "source": "readonly_sql",
                "method": "SELECT",
                "path": ",".join(checked.get("tables") or []),
                "status": 200,
                "note": (note or "")[:120],
                "thread_id": get_thread_id(),
                "username": get_username(),
            }
        )
    except Exception:
        pass

    records = out.get("records") if isinstance(out.get("records"), list) else []
    preview_rows = records[:8]
    return {
        "ok": True,
        "sql": checked["sql"],
        "tables": checked.get("tables"),
        "limit": checked.get("limit"),
        "columns": out.get("columns") or [],
        "records": records,
        "returned": out.get("returned"),
        "preview_rows": preview_rows,
        "note": (note or "").strip()[:200],
        "caveats": [
            "只读 SQL 结果；非 MES HTTP 实体查询。",
            "聚合口径请与业务确认后再出图。",
        ],
        "reply_hint": (
            "展示 preview_rows / 条数；需要出图时把分组结果交给 render_analysis_chart。"
            "禁止声称这是 HTTP API 结果。"
        ),
    }
