"""本机写码成功后，将 API / 表结构变更增量同步到当前 MES 资料包。"""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_AGENT_DIR = Path(__file__).resolve().parents[1] / "agent"
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

_API_PATH_HINTS = (
    "/routes/",
    "/routers/",
    "/router/",
    "/api/",
    "/schemas/",
    "/endpoints/",
    "main.py",
    "openapi",
)
_SCHEMA_PATH_HINTS = (
    "/models/",
    "/model/",
    "/migrations/",
    "/alembic/",
    "models.py",
    "schema.py",
)
_MAX_MODEL_BYTES = 400_000


def _is_under_root(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False

_TABLENAME_RE = re.compile(r'__tablename__\s*=\s*["\'](\w+)["\']')
_CLASS_RE = re.compile(r"^class\s+(\w+)", re.M)
_MAPPED_FIELD_RE = re.compile(
    r"^\s+(\w+)\s*:\s*Mapped\[(?:Optional\[)?([^\]]+)\]?\]",
    re.M,
)
_COLUMN_FIELD_RE = re.compile(
    r"^\s+(\w+)\s*=\s*Column\(\s*([^,)]+)",
    re.M,
)
_TABLE_HEAD_ERP_RE = re.compile(
    r"^####\s+`([A-Za-z_][A-Za-z0-9_]*)`\s*[—\-–]\s*(.+?)\s*$",
    re.M,
)
_AUTO_SYNC_DOMAIN = "### WorkBuddy 自动同步"


def _norm_rel(path: str) -> str:
    return str(path or "").replace("\\", "/").strip().lstrip("./")


def synced_touches_api(synced_files: list[str]) -> bool:
    for raw in synced_files or []:
        p = _norm_rel(raw).lower()
        if not p.endswith(".py"):
            continue
        if any(h in p for h in _SCHEMA_PATH_HINTS):
            continue
        if p.startswith("backend/") or "/backend/" in p:
            if any(h in p for h in _API_PATH_HINTS):
                return True
            if p.endswith("main.py"):
                return True
        elif any(h in p for h in _API_PATH_HINTS):
            return True
    return False


def synced_touches_schema(synced_files: list[str]) -> bool:
    for raw in synced_files or []:
        p = _norm_rel(raw).lower()
        if p.endswith(".py") and any(h in p for h in _SCHEMA_PATH_HINTS):
            return True
        if "/migrations/" in p or "/alembic/" in p:
            return True
        if p.endswith((".sql", ".md")) and "migration" in p:
            return True
    return False


def _is_localhost_url(url: str) -> bool:
    """仅允许 loopback（127.0.0.1 / ::1 / localhost）。"""
    import ipaddress
    import socket

    from safe_http import assert_http_url_allowed

    try:
        text = assert_http_url_allowed(url, what="MES 后端")
        host = (urlparse(text).hostname or "").strip().lower()
    except ValueError:
        return False
    if not host:
        return False
    if host in {"localhost", "localhost.localdomain"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
        return bool(ip.is_loopback)
    except ValueError:
        pass
    try:
        for info in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM):
            addr = info[4][0]
            try:
                if not ipaddress.ip_address(addr).is_loopback:
                    return False
            except ValueError:
                return False
        return True
    except OSError:
        return False


def _agent_importable() -> bool:
    try:
        import mes_profile  # noqa: F401

        return True
    except Exception:
        return False


def _map_py_type(raw: str) -> str:
    s = (raw or "").strip().lower()
    if "datetime" in s or "date" in s:
        return "DATETIME"
    if "int" in s:
        return "INTEGER"
    if "bool" in s:
        return "BOOLEAN"
    if "float" in s or "decimal" in s or "numeric" in s:
        return "DECIMAL"
    if "text" in s:
        return "TEXT"
    return "VARCHAR"


def _humanize(name: str) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name or "")
    return s.replace("_", " ").strip() or name


def parse_sqlalchemy_tables(source: str) -> list[dict[str, Any]]:
    text = source or ""
    classes = list(_CLASS_RE.finditer(text))
    out: list[dict[str, Any]] = []
    for i, m in enumerate(classes):
        class_name = m.group(1)
        body = text[m.start() : classes[i + 1].start() if i + 1 < len(classes) else len(text)]
        tm = _TABLENAME_RE.search(body)
        if not tm:
            continue
        table = tm.group(1)
        fields: list[dict[str, str]] = []
        seen: set[str] = set()
        for rx in (_MAPPED_FIELD_RE, _COLUMN_FIELD_RE):
            for fm in rx.finditer(body):
                fname = fm.group(1)
                if fname.startswith("_") or fname in seen:
                    continue
                seen.add(fname)
                ftype = _map_py_type(fm.group(2))
                fields.append({"name": fname, "type": ftype, "note": ""})
        if not fields:
            continue
        out.append(
            {
                "table": table,
                "label": _humanize(class_name),
                "fields": fields,
            }
        )
    return out


def collect_tables_from_files(project_root: Path, synced_files: list[str]) -> list[dict[str, Any]]:
    root = Path(project_root).resolve()
    merged: dict[str, dict[str, Any]] = {}
    for rel in synced_files or []:
        p = _norm_rel(rel)
        if not p.endswith(".py"):
            continue
        low = p.lower()
        if not any(h in low for h in _SCHEMA_PATH_HINTS):
            continue
        path = (root / p).resolve()
        try:
            if not _is_under_root(root, path):
                continue
            if not path.is_file() or path.stat().st_size > _MAX_MODEL_BYTES:
                continue
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for item in parse_sqlalchemy_tables(text):
            merged[item["table"]] = item
    return list(merged.values())


def _render_table_block(item: dict[str, Any]) -> str:
    table = str(item.get("table") or "").strip()
    label = str(item.get("label") or table).strip()
    lines = [
        f"#### `{table}` — {label}",
        "",
        "| 字段名 | 类型 | 约束 | 默认值 | 说明 |",
        "|--------|------|------|--------|------|",
    ]
    for f in item.get("fields") or []:
        name = str(f.get("name") or "").strip()
        if not name:
            continue
        ftype = str(f.get("type") or "VARCHAR").strip()
        note = str(f.get("note") or "—").strip() or "—"
        lines.append(f"| {name} | {ftype} | — | — | {note} |")
    lines.append("")
    return "\n".join(lines)


def merge_schema_markdown(existing: str, tables: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    text = existing or ""
    added: list[str] = []
    updated: list[str] = []
    new_blocks: list[str] = []

    for item in tables:
        table = str(item.get("table") or "").strip()
        if not table:
            continue
        block = _render_table_block(item)
        pattern = re.compile(
            rf"^####\s+`{re.escape(table)}`\s*[—\-–].*?(?=^####\s|^###\s|\Z)",
            re.M | re.S,
        )
        if pattern.search(text):
            text = pattern.sub(block.rstrip() + "\n\n", text, count=1)
            updated.append(table)
        else:
            new_blocks.append(block)
            added.append(table)

    if new_blocks:
        if _AUTO_SYNC_DOMAIN not in text:
            text = text.rstrip() + f"\n\n{_AUTO_SYNC_DOMAIN}\n\n"
        text = text.rstrip() + "\n\n" + "\n".join(new_blocks)

    stats = {"added": added, "updated": updated, "total_tables": len(tables)}
    return text.strip() + "\n", stats


def _fetch_openapi_from_backend(backend_url: str) -> tuple[str, str]:
    from safe_http import assert_http_url_allowed
    from tools.query_tool.openapi_fetch import fetch_openapi_text

    base = str(backend_url or "").strip().rstrip("/")
    if not base:
        raise ValueError("后端地址为空")
    assert_http_url_allowed(base, what="MES 后端")
    if not _is_localhost_url(base):
        raise ValueError("自动同步仅允许本机 MES（127.0.0.1 / localhost）")
    docs_url = f"{base}/docs"
    return fetch_openapi_text(docs_url)


def _runtime_backend_candidates(preview: dict[str, Any] | None = None) -> list[str]:
    out: list[str] = []
    preview_url = str((preview or {}).get("backend_url") or "").strip().rstrip("/")
    if preview_url:
        out.append(preview_url)
    try:
        from mes_profile import resolve_mes_api_base

        api_base = str(resolve_mes_api_base() or "").strip().rstrip("/")
        if api_base and api_base not in out:
            out.append(api_base)
    except Exception:
        pass
    return out


def refresh_openapi_to_profile(
    profile_id: str | None = None,
    *,
    backend_urls: list[str] | None = None,
    sync_note: str = "从运行中 MES 刷新接口目录",
) -> dict[str, Any]:
    """从本机运行中的 MES 拉 OpenAPI，合并写入资料包 entities.json。"""
    from mes_profile import active_profile_id
    from mes_profile_persist import persist_openapi_text

    pid = (profile_id or active_profile_id() or "").strip()
    if not pid:
        raise ValueError("未配置 MES 资料包（MES_PROFILE_ID）")

    urls = [u.strip().rstrip("/") for u in (backend_urls or []) if str(u or "").strip()]
    if not urls:
        urls = _runtime_backend_candidates()

    errors: list[str] = []
    for base in urls:
        try:
            text, used = _fetch_openapi_from_backend(base)
            out = persist_openapi_text(
                pid,
                text,
                source_url=used,
                merge_existing=True,
                reload_agent=True,
                sync_note=sync_note,
                preserve_runtime=True,
            )
            merge = out.get("merge") or {}
            return {
                "ok": True,
                "profile_id": pid,
                "fetched_from": used,
                "entity_count": out.get("entity_count"),
                "added": merge.get("added") or [],
                "updated": merge.get("updated") or [],
                "preserved": merge.get("preserved") or [],
            }
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{base}: {exc}")

    detail = "；".join(errors[:3]) if errors else "无可用本机后端地址"
    raise ValueError(f"未能从运行中 MES 刷新接口目录：{detail}")


def sync_mes_profile_after_dev(
    *,
    project_root: Path | str,
    synced_files: list[str],
    preview: dict[str, Any] | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    """写码同步成功后调用：按需刷新资料包 openapi/entities 与 schema.md。"""
    result: dict[str, Any] = {
        "skipped": True,
        "ok": True,
        "api": {"skipped": True},
        "schema": {"skipped": True},
    }
    if not enabled:
        result["reason"] = "MES_PROFILE_AUTO_SYNC 已关闭"
        return result
    if not _agent_importable():
        result["reason"] = "agent 模块不可用"
        return result

    from mes_profile import (
        SCHEMA_FILENAME,
        active_profile_id,
        profile_dir,
        resolve_schema_doc,
    )

    pid = active_profile_id()
    if not pid:
        result["reason"] = "未配置当前 MES 资料包（MES_PROFILE_ID）"
        return result
    pdir = profile_dir(pid)
    if pdir is None:
        result["reason"] = "资料包目录不存在"
        return result

    want_api = synced_touches_api(synced_files)
    want_schema = synced_touches_schema(synced_files)
    if not want_api and not want_schema:
        result["reason"] = "本次变更未涉及 API 或表结构文件"
        return result

    result["skipped"] = False
    result["profile_id"] = pid
    reload_agent = False
    notes: list[str] = []

    # --- API / entities ---
    if want_api:
        backend_urls = _runtime_backend_candidates(preview)
        if not backend_urls:
            result["api"] = {
                "skipped": True,
                "ok": False,
                "error": "预览后端与资料包 api_base 均不可用",
            }
            notes.append("接口目录：无可用本机 MES 地址，已跳过")
        else:
            try:
                api_out = refresh_openapi_to_profile(
                    pid,
                    backend_urls=backend_urls,
                    sync_note="本机写码后自动同步",
                )
                result["api"] = {
                    "skipped": False,
                    "ok": True,
                    "fetched_from": api_out.get("fetched_from"),
                    "entity_count": api_out.get("entity_count"),
                    "added": api_out.get("added") or [],
                    "updated": api_out.get("updated") or [],
                    "preserved": api_out.get("preserved") or [],
                }
                reload_agent = False  # refresh_openapi_to_profile 已 reload
                added = api_out.get("added") or []
                if added:
                    notes.append(f"接口目录：新增可查对象 {', '.join(added[:8])}")
                else:
                    notes.append("接口目录：已与运行中 OpenAPI 对齐（保留既有实体）")
            except Exception as exc:  # noqa: BLE001
                logger.warning("mes profile api auto-sync failed: %s", exc)
                result["api"] = {
                    "skipped": False,
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                notes.append(f"接口目录：同步失败（{exc}），未改动资料包")

    # --- schema.md ---
    if want_schema:
        tables = collect_tables_from_files(Path(project_root), synced_files)
        if not tables:
            result["schema"] = {
                "skipped": True,
                "ok": False,
                "error": "未能从变更的模型文件解析出表",
            }
            notes.append("表结构：未解析到新表，已跳过")
        else:
            try:
                schema_path, schema_src = resolve_schema_doc()
                existing = ""
                if schema_src == "profile" and schema_path and schema_path.is_file():
                    existing = schema_path.read_text(encoding="utf-8")
                elif (pdir / SCHEMA_FILENAME).is_file():
                    existing = (pdir / SCHEMA_FILENAME).read_text(encoding="utf-8")

                merged_text, stats = merge_schema_markdown(existing, tables)
                from mes_profile_persist import persist_schema_text

                persist_schema_text(pid, merged_text, reload_agent=False)
                result["schema"] = {
                    "skipped": False,
                    "ok": True,
                    "added_tables": stats.get("added") or [],
                    "updated_tables": stats.get("updated") or [],
                }
                reload_agent = True
                added_t = stats.get("added") or []
                updated_t = stats.get("updated") or []
                if added_t:
                    notes.append(f"表结构：新增表 {', '.join(added_t[:8])}")
                if updated_t:
                    notes.append(f"表结构：更新表 {', '.join(updated_t[:8])}")
                if not added_t and not updated_t:
                    notes.append("表结构：无变化")
            except Exception as exc:  # noqa: BLE001
                logger.warning("mes profile schema auto-sync failed: %s", exc)
                result["schema"] = {
                    "skipped": False,
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                notes.append(f"表结构：同步失败（{exc}），未改动资料包")

    if reload_agent:
        from mes_profile_persist import _reload_after_profile_change

        _reload_after_profile_change()

    result["ok"] = bool(
        (result.get("api") or {}).get("ok")
        or (result.get("schema") or {}).get("ok")
        or (
            (result.get("api") or {}).get("skipped")
            and (result.get("schema") or {}).get("skipped")
        )
    )
    result["notes"] = notes
    return result


def format_profile_sync_summary(result: dict[str, Any]) -> str:
    if result.get("skipped"):
        reason = str(result.get("reason") or "").strip()
        if not reason:
            return ""
        return f"### 资料包自动同步\n\n- 已跳过：{reason}\n\n"

    lines = ["### 资料包自动同步", ""]
    for note in result.get("notes") or []:
        lines.append(f"- {note}")
    api = result.get("api") or {}
    schema = result.get("schema") or {}
    if api.get("ok") is False and api.get("error"):
        lines.append(f"- 接口同步错误：{api['error']}")
    if schema.get("ok") is False and schema.get("error"):
        lines.append(f"- 表结构同步错误：{schema['error']}")
    if len(lines) <= 2:
        return ""
    lines.append("")
    return "\n".join(lines)
