"""
解析 docs/中软MES数据库表结构.md（中软数据字典导出）。

只读本地 Markdown，不连数据库、不改 ERP、不碰 entities.json。
大文档按域/表分页返回，避免一次塞进模型上下文。
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from config import Config

# 默认文档路径（仓库 docs/）
DEFAULT_SCHEMA_DOC = Config.REPO_ROOT / "docs" / "中软MES数据库表结构.md"
# 可选缓存索引（首次解析后写入，加速后续）
INDEX_CACHE = Config.REPO_ROOT / "data" / "schema" / "mes_schema_index.json"

_DOMAIN_RE = re.compile(r"^###\s+(\d+\.\d+)\s+(.+?)\s*$", re.M)
_TABLE_HEAD_RE = re.compile(
    r"^####\s+(\d+)\s+(.+?)\s*\(\s*([A-Z][A-Z0-9_]+)\s*\)\s*$",
    re.M,
)
_MEANING_RE = re.compile(r"-\s*\*\*业务含义\*\*[：:]\s*(.+)")
_DB_RE = re.compile(r"-\s*\*\*所属数据库\*\*[：:]\s*(.+)")
_FIELD_ROW_RE = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$"
)
_REL_RE = re.compile(r"^\s*-\s*([A-Z][A-Z0-9_]+)\.([A-Za-z0-9_]+)\s*=\s*([A-Z][A-Z0-9_]+)\.([A-Za-z0-9_]+)")


def schema_doc_path() -> Path:
    override = os.getenv("MES_SCHEMA_DOC", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_SCHEMA_DOC


def _load_raw_text() -> str:
    path = schema_doc_path()
    if not path.exists():
        raise FileNotFoundError(f"表结构文档不存在: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(
            f"表结构文档为空（可能未保存）: {path}。"
            "请在编辑器中保存 docs/中软MES数据库表结构.md 后重试。"
        )
    return text


def _split_table_blocks(text: str) -> list[tuple[str, str, str, str]]:
    """返回 [(domain_id, domain_name, table_head_line, block_body), ...]。"""
    domain_spans: list[tuple[int, str, str]] = []
    for m in _DOMAIN_RE.finditer(text):
        domain_spans.append((m.start(), m.group(1), m.group(2).strip()))

    def domain_at(pos: int) -> tuple[str, str]:
        cur = ("", "")
        for start, did, dname in domain_spans:
            if start <= pos:
                cur = (did, dname)
            else:
                break
        return cur

    heads = list(_TABLE_HEAD_RE.finditer(text))
    blocks: list[tuple[str, str, str, str]] = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[m.end() : end]
        did, dname = domain_at(m.start())
        blocks.append((did, dname, m.group(0), body))
    return blocks


def _parse_table_block(
    domain_id: str,
    domain_name: str,
    head_line: str,
    body: str,
) -> dict[str, Any]:
    hm = _TABLE_HEAD_RE.match(head_line.strip())
    seq = int(hm.group(1)) if hm else 0
    label = hm.group(2).strip() if hm else ""
    table = hm.group(3).strip() if hm else ""

    meaning_m = _MEANING_RE.search(body)
    db_m = _DB_RE.search(body)
    meaning = meaning_m.group(1).strip() if meaning_m else ""
    database = db_m.group(1).strip() if db_m else ""

    fields: list[dict[str, str]] = []
    in_fields = False
    for line in body.splitlines():
        if line.startswith("| 字段名"):
            in_fields = True
            continue
        if in_fields and line.startswith("|--"):
            continue
        if in_fields:
            if not line.startswith("|"):
                in_fields = False
            else:
                fm = _FIELD_ROW_RE.match(line)
                if fm:
                    name = fm.group(1).strip()
                    if name and name != "字段名":
                        fields.append(
                            {
                                "name": name,
                                "type": fm.group(2).strip(),
                                "nullable": fm.group(3).strip(),
                                "default": fm.group(4).strip(),
                                "comment": fm.group(5).strip(),
                            }
                        )

    relations: list[dict[str, str]] = []
    in_rel = False
    for line in body.splitlines():
        if "关联关系" in line:
            in_rel = True
            continue
        if in_rel:
            if line.startswith("---") or line.startswith("####"):
                break
            rm = _REL_RE.match(line)
            if rm:
                relations.append(
                    {
                        "from_table": rm.group(1),
                        "from_field": rm.group(2),
                        "to_table": rm.group(3),
                        "to_field": rm.group(4),
                    }
                )
            elif line.strip().startswith("-") and "无" in line:
                break

    prefix = ""
    parts = table.split("_")
    if len(parts) >= 2:
        prefix = parts[1]  # SYS / BD / QM / SFC ...

    return {
        "seq": seq,
        "table": table,
        "label": label,
        "domain_id": domain_id,
        "domain": domain_name,
        "meaning": meaning,
        "database": database,
        "field_count": len(fields),
        "fields": fields,
        "relations": relations,
        "table_prefix": prefix,
    }


def build_index(force: bool = False) -> dict[str, Any]:
    """构建/读取轻量索引（不含全量字段，字段在 describe 时再取）。"""
    if not force and INDEX_CACHE.exists():
        try:
            cached = json.loads(INDEX_CACHE.read_text(encoding="utf-8"))
            src = schema_doc_path()
            if cached.get("source_mtime") == src.stat().st_mtime and cached.get("tables"):
                return cached
        except Exception:
            pass

    text = _load_raw_text()
    blocks = _split_table_blocks(text)
    tables: list[dict[str, Any]] = []
    domains: dict[str, dict[str, Any]] = {}

    for did, dname, head, body in blocks:
        # 索引只保留摘要，字段在 describe 时解析（避免巨大 JSON）
        full = _parse_table_block(did, dname, head, body)
        summary = {
            "seq": full["seq"],
            "table": full["table"],
            "label": full["label"],
            "domain_id": full["domain_id"],
            "domain": full["domain"],
            "meaning": full["meaning"],
            "database": full["database"],
            "field_count": full["field_count"],
            "relation_count": len(full["relations"]),
            "table_prefix": full["table_prefix"],
        }
        tables.append(summary)
        key = did or "unknown"
        if key not in domains:
            domains[key] = {"domain_id": did, "domain": dname, "table_count": 0, "tables": []}
        domains[key]["table_count"] += 1
        domains[key]["tables"].append(full["table"])

    index = {
        "source": str(schema_doc_path()),
        "source_mtime": schema_doc_path().stat().st_mtime,
        "built_at": time.time(),
        "table_count": len(tables),
        "domain_count": len(domains),
        "domains": list(domains.values()),
        "tables": tables,
    }
    try:
        INDEX_CACHE.parent.mkdir(parents=True, exist_ok=True)
        INDEX_CACHE.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return index


_full_tables_cache: list[dict[str, Any]] | None = None
_full_tables_mtime: float | None = None


def _all_tables_full() -> list[dict[str, Any]]:
    global _full_tables_cache, _full_tables_mtime
    path = schema_doc_path()
    mtime = path.stat().st_mtime
    if _full_tables_cache is not None and _full_tables_mtime == mtime:
        return _full_tables_cache
    text = _load_raw_text()
    blocks = _split_table_blocks(text)
    _full_tables_cache = [_parse_table_block(d, n, h, b) for d, n, h, b in blocks]
    _full_tables_mtime = mtime
    return _full_tables_cache


def find_table_full(table_or_label: str) -> dict[str, Any] | None:
    key = (table_or_label or "").strip()
    if not key:
        return None
    key_u = key.upper()
    tables = _all_tables_full()
    for t in tables:
        if t["table"].upper() == key_u or t["label"] == key or key in t["label"]:
            return t
    for t in tables:
        if key_u in t["table"].upper():
            return t
    return None
