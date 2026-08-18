"""加字段后的确定性闸门：SQLite 补列 + 按业务状态回填空值。

不依赖模型自觉。提示词仍可能漏回填；本闸门在同步后直接改库。
只动白名单时间列、只填 NULL，不覆盖已有值。
演示库约定：开始用计划日 08:00，结束用计划日 18:00（无真实车间时钟）。
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from .config import COPY_SKIP_DIR_NAMES
from .stack_chain import looks_like_data_ui_change

# 只回填这些列，避免误写 created_at / start_date
_START_COLS = frozenset(
    {
        "actual_start_time",
        "actual_start",
        "actual_started_at",
        "started_at",
    }
)
_END_COLS = frozenset(
    {
        "actual_end_time",
        "actual_end",
        "actual_finished_at",
        "actual_finish_time",
        "finished_at",
        "completed_at",
    }
)
_ALL_ACTUAL_COLS = _START_COLS | _END_COLS

_START_DATE_CANDIDATES = (
    "start_date",
    "plan_start_date",
    "planned_start",
    "planned_start_date",
    "scheduled_start",
)
_END_DATE_CANDIDATES = (
    "end_date",
    "plan_end_date",
    "planned_end",
    "planned_end_date",
    "scheduled_end",
    "due_date",
)

_STARTED_STATUSES = ("in_progress", "processing", "running", "completed", "closed", "done", "finished")
_ENDED_STATUSES = ("completed", "closed", "done", "finished")

_START_CLOCK = "08:00:00"
_END_CLOCK = "18:00:00"
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_PY_BYTES = 400_000
_MAX_DB_BYTES = 200 * 1024 * 1024


def _safe_sql_ident(name: str) -> str | None:
    """只允许普通标识符，防止表/列名拼进 SQL。"""
    s = str(name or "").strip()
    if _IDENT_RE.match(s) and len(s) <= 64:
        return s
    return None


def _quoted_ident(name: str) -> str | None:
    ident = _safe_sql_ident(name)
    if not ident:
        return None
    return f'"{ident}"'


def _is_under_root(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False

_TABLENAME_RE = re.compile(r'__tablename__\s*=\s*["\'](\w+)["\']')
_CLASS_RE = re.compile(r"^class\s+\w+", re.M)
_MAPPED_DT_RE = re.compile(
    r"^(\s+)(\w+)\s*:\s*Mapped\[[^\]]*datetime[^\]]*\]",
    re.M,
)
_COLUMN_DT_RE = re.compile(
    r"^(\s+)(\w+)\s*=\s*Column\(\s*DateTime",
    re.M,
)


def find_sqlite_dbs(root: Path, *, max_files: int = 20) -> list[Path]:
    """在工程内找 SQLite 文件，跳过依赖、构建目录与指向仓外的符号链接。"""
    base = Path(root).resolve()
    if not base.is_dir():
        return []
    found: list[Path] = []
    for path in base.rglob("*"):
        if len(found) >= max_files:
            break
        try:
            if not path.is_file():
                continue
            resolved = path.resolve()
        except OSError:
            continue
        if not _is_under_root(base, resolved):
            continue
        if any(part in COPY_SKIP_DIR_NAMES for part in resolved.parts):
            continue
        if resolved.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
            continue
        try:
            if resolved.stat().st_size > _MAX_DB_BYTES:
                continue
        except OSError:
            continue
        found.append(resolved)
    return found


def parse_model_datetime_fields(source: str) -> dict[str, list[str]]:
    """从表模型里抽出 __tablename__ → 白名单 DateTime 字段。"""
    text = source or ""
    classes = list(_CLASS_RE.finditer(text))
    out: dict[str, list[str]] = {}
    for i, m in enumerate(classes):
        body = text[m.start() : classes[i + 1].start() if i + 1 < len(classes) else len(text)]
        tm = _TABLENAME_RE.search(body)
        if not tm:
            continue
        table = tm.group(1)
        names: list[str] = []
        for rx in (_MAPPED_DT_RE, _COLUMN_DT_RE):
            for fm in rx.finditer(body):
                col = fm.group(2)
                if col in _ALL_ACTUAL_COLS and col not in names:
                    names.append(col)
        if names:
            out.setdefault(table, [])
            for col in names:
                if col not in out[table]:
                    out[table].append(col)
    return out


def collect_model_datetime_fields(root: Path) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    base = Path(root).resolve()
    if not base.is_dir():
        return merged
    for path in base.rglob("*.py"):
        if any(part in COPY_SKIP_DIR_NAMES for part in path.parts):
            continue
        try:
            if not _is_under_root(base, path):
                continue
            if path.stat().st_size > _MAX_PY_BYTES:
                continue
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for table, cols in parse_model_datetime_fields(text).items():
            merged.setdefault(table, [])
            for col in cols:
                if col not in merged[table]:
                    merged[table].append(col)
    return merged


def _table_columns(conn: sqlite3.Connection, table: str) -> dict[str, str]:
    q = _quoted_ident(table)
    if not q:
        return {}
    rows = conn.execute(f"PRAGMA table_info({q})").fetchall()
    return {str(r[1]): str(r[2] or "") for r in rows}


def _list_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    out: list[str] = []
    for r in rows:
        ident = _safe_sql_ident(str(r[0]))
        if ident:
            out.append(ident)
    return out


def _pick_date_col(columns: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    lower = {k.lower(): k for k in columns}
    for name in candidates:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _ensure_column(conn: sqlite3.Connection, table: str, col: str) -> bool:
    table_q = _quoted_ident(table)
    col_q = _quoted_ident(col)
    col_id = _safe_sql_ident(col)
    if not table_q or not col_q or not col_id:
        return False
    cols = _table_columns(conn, table)
    if col_id in cols:
        return False
    conn.execute(f"ALTER TABLE {table_q} ADD COLUMN {col_q} DATETIME")
    return True


def _backfill(
    conn: sqlite3.Connection,
    *,
    table: str,
    target_col: str,
    date_col: str,
    clock: str,
    statuses: tuple[str, ...],
) -> int:
    table_q = _quoted_ident(table)
    target_q = _quoted_ident(target_col)
    date_q = _quoted_ident(date_col)
    target_id = _safe_sql_ident(target_col)
    date_id = _safe_sql_ident(date_col)
    if not table_q or not target_q or not date_q or not target_id or not date_id:
        return 0
    if clock not in (_START_CLOCK, _END_CLOCK):
        return 0
    cols = _table_columns(conn, table)
    if "status" not in cols or target_id not in cols or date_id not in cols:
        return 0
    placeholders = ",".join("?" for _ in statuses)
    cur = conn.execute(
        f"""
        UPDATE {table_q}
        SET {target_q} = CASE
          WHEN length(trim({date_q})) <= 10 THEN datetime({date_q} || ' ' || ?)
          ELSE datetime({date_q})
        END
        WHERE {target_q} IS NULL
          AND {date_q} IS NOT NULL
          AND TRIM({date_q}) != ''
          AND status IN ({placeholders})
        """,
        (clock, *statuses),
    )
    return int(cur.rowcount or 0)


def repair_sqlite_datetime_chain(
    db_path: Path,
    *,
    model_fields: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """对单个 SQLite：按模型补白名单列，并按状态回填空的实际开始/结束时间。"""
    actions: list[str] = []
    path = Path(db_path)
    try:
        path = path.resolve()
    except OSError:
        return {"ok": True, "actions": [], "db": str(db_path)}
    if not path.is_file():
        return {"ok": True, "actions": [], "db": str(path)}
    model_fields = model_fields or {}
    conn = sqlite3.connect(str(path), timeout=8)
    try:
        conn.execute("PRAGMA busy_timeout=8000")
        tables = set(_list_tables(conn))
        for table, cols in model_fields.items():
            table_id = _safe_sql_ident(table)
            if not table_id or table_id not in tables:
                continue
            for col in cols:
                if _ensure_column(conn, table_id, col):
                    actions.append(f"{path.name}:{table_id} 补列 {col}")
        for table in tables:
            columns = _table_columns(conn, table)
            start_date = _pick_date_col(columns, _START_DATE_CANDIDATES)
            end_date = _pick_date_col(columns, _END_DATE_CANDIDATES)
            for col in columns:
                col_id = _safe_sql_ident(col)
                if not col_id:
                    continue
                if col_id in _START_COLS and start_date:
                    n = _backfill(
                        conn,
                        table=table,
                        target_col=col_id,
                        date_col=start_date,
                        clock=_START_CLOCK,
                        statuses=_STARTED_STATUSES,
                    )
                    if n:
                        actions.append(f"{path.name}:{table} 回填 {col_id} {n} 行")
                if col_id in _END_COLS and end_date:
                    n = _backfill(
                        conn,
                        table=table,
                        target_col=col_id,
                        date_col=end_date,
                        clock=_END_CLOCK,
                        statuses=_ENDED_STATUSES,
                    )
                    if n:
                        actions.append(f"{path.name}:{table} 回填 {col_id} {n} 行")
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "actions": actions, "db": str(path)}


def run_stack_chain_gate(
    project_root: Path,
    *,
    requirement: str = "",
) -> dict[str, Any]:
    """数据字段任务：扫描工程 SQLite，补列并回填。纯样式任务跳过。"""
    if requirement and not looks_like_data_ui_change(requirement):
        return {"skipped": True, "actions": [], "dbs": []}
    root = Path(project_root)
    model_fields = collect_model_datetime_fields(root)
    dbs = find_sqlite_dbs(root)
    actions: list[str] = []
    for db in dbs:
        result = repair_sqlite_datetime_chain(db, model_fields=model_fields)
        actions.extend(result.get("actions") or [])
    return {
        "skipped": False,
        "actions": actions,
        "dbs": [p.name for p in dbs],
        "model_fields": model_fields,
    }


def format_gate_summary(result: dict[str, Any]) -> str:
    if result.get("skipped"):
        return ""
    if result.get("error"):
        return f"数据链路闸门未完全执行：{result['error']}"
    actions = result.get("actions") or []
    if not actions:
        if result.get("dbs"):
            return "数据链路闸门已检查库表：无需补列或回填。"
        return "数据链路闸门未找到 SQLite，跳过自动回填（若用其它库需启动后由迁移脚本处理）。"
    lines = "\n".join(f"- {a}" for a in actions[:20])
    return f"数据链路闸门已自动处理（演示库按计划日 08:00/18:00 回填空值）：\n{lines}"
