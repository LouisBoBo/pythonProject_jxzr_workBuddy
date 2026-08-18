"""
摸底报告导出（Markdown / Excel）。

只读本地表结构索引与预置场景，写入 Config.EXPORT_DIR。
不调用 ERP，不改写平台数据。
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated, Any, Literal

import pandas as pd

from config import Config
from tools.schema_tool.business_scenarios import _SCENARIOS, get_scenario_table_pack
from tools.schema_tool.mes_schema_parser import build_index, find_table_full, schema_doc_path
from tools.schema_tool.schema_query import _PREFIX_CAPABILITY


def _ensure_export_dir() -> str:
    out = Config.EXPORT_DIR
    os.makedirs(out, exist_ok=True)
    return out


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _live_entities() -> list[dict[str, Any]]:
    try:
        from tools.query_tool.entity_catalog import catalog_summary

        return catalog_summary()
    except Exception:
        return []


def _prefix_capabilities(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_prefix: dict[str, int] = {}
    for t in tables:
        p = t.get("table_prefix") or "?"
        by_prefix[p] = by_prefix.get(p, 0) + 1
    out = []
    for prefix, cnt in sorted(by_prefix.items(), key=lambda x: -x[1]):
        cap = _PREFIX_CAPABILITY.get(prefix, f"其它（前缀 {prefix}）")
        out.append({"prefix": prefix, "table_count": cnt, "capability": cap})
    return out


def _domain_briefs(tables: list[dict[str, Any]], top_n: int = 5) -> list[dict[str, Any]]:
    by_domain: dict[str, list[dict[str, Any]]] = {}
    for t in tables:
        dname = t.get("domain") or "未分类"
        by_domain.setdefault(dname, []).append(t)
    briefs = []
    for dname, items in by_domain.items():
        scored = sorted(
            items,
            key=lambda x: (
                -int(x.get("field_count") or 0),
                -int(x.get("relation_count") or 0),
            ),
        )
        top = scored[:top_n]
        briefs.append(
            {
                "domain": dname,
                "table_count": len(items),
                "representative_tables": [
                    {
                        "table": x.get("table"),
                        "label": x.get("label"),
                        "meaning": (x.get("meaning") or "")[:80],
                    }
                    for x in top
                ],
            }
        )
    return briefs


def _build_report_payload(
    focus: str | None,
    include_fields: bool,
    fields_per_table: int,
) -> dict[str, Any]:
    index = build_index()
    all_tables = list(index.get("tables") or [])
    tables = all_tables
    if focus:
        f = focus.strip()
        tables = [
            t
            for t in all_tables
            if f in (t.get("domain") or "")
            or f in (t.get("label") or "")
            or f in (t.get("meaning") or "")
            or f.upper() in (t.get("table") or "").upper()
        ]

    domains = _domain_briefs(tables, top_n=5)
    caps = _prefix_capabilities(all_tables if not focus else tables)

    field_rows: list[dict[str, Any]] = []
    if include_fields:
        limit_fields = max(5, min(int(fields_per_table or 15), 40))
        seen: set[str] = set()
        for d in domains:
            for rep in (d.get("representative_tables") or [])[:3]:
                tname = rep.get("table")
                if not tname or tname in seen:
                    continue
                seen.add(tname)
                full = find_table_full(tname)
                if not full:
                    continue
                for fld in (full.get("fields") or [])[:limit_fields]:
                    field_rows.append(
                        {
                            "domain": full.get("domain"),
                            "table": tname,
                            "label": full.get("label"),
                            "field": fld.get("name"),
                            "type": fld.get("type"),
                            "nullable": fld.get("nullable"),
                            "comment": (fld.get("comment") or "")[:80],
                        }
                    )

    scenarios_brief = []
    for s in _SCENARIOS:
        pack = get_scenario_table_pack(s["id"], expand_relations=False)
        if pack.get("error"):
            continue
        scenarios_brief.append(
            {
                "id": pack.get("scenario_id"),
                "title": pack.get("title"),
                "path_summary": pack.get("path_summary"),
                "seed_table_count": pack.get("seed_table_count"),
            }
        )

    return {
        "source": index.get("source") or str(schema_doc_path()),
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "focus": focus,
        "table_count": index.get("table_count"),
        "domain_count": index.get("domain_count"),
        "matched_table_count": len(tables) if focus else index.get("table_count"),
        "capabilities_by_prefix": caps,
        "domains": domains,
        "field_summary_rows": field_rows,
        "scenarios": scenarios_brief,
        "live_queryable_entities": _live_entities(),
        "disclaimer": (
            "本报告由当前已配置的 MES 表结构文档推断，用于实施摸底对齐；"
            "不是实时数据库快照，也不代表 WorkBuddy 已对接全部 REST。"
        ),
    }


def _write_markdown(payload: dict[str, Any], path: str) -> None:
    lines: list[str] = [
        "# 中软 MES 表结构摸底报告",
        "",
        f"- 生成时间：{payload.get('built_at')}",
        f"- 来源：`{payload.get('source')}`",
        f"- 字典表数：{payload.get('table_count')}；业务域：{payload.get('domain_count')}",
    ]
    if payload.get("focus"):
        lines.append(f"- 聚焦：{payload['focus']}（匹配表约 {payload.get('matched_table_count')}）")
    lines.extend(["", f"> {payload.get('disclaimer')}", "", "## 1. 能力前缀地图", ""])
    lines.append("| 前缀 | 表数 | 能力说明 |")
    lines.append("|------|------|----------|")
    for c in payload.get("capabilities_by_prefix") or []:
        lines.append(
            f"| {c.get('prefix')} | {c.get('table_count')} | {c.get('capability')} |"
        )

    lines.extend(["", "## 2. 业务域与代表表", ""])
    for d in payload.get("domains") or []:
        lines.append(f"### {d.get('domain')}（{d.get('table_count')} 张表）")
        lines.append("")
        for r in d.get("representative_tables") or []:
            meaning = (r.get("meaning") or "").replace("|", "/")
            lines.append(f"- **{r.get('label')}** (`{r.get('table')}`) — {meaning}")
        lines.append("")

    lines.extend(["", "## 3. 预置业务场景表包（摘要）", ""])
    for s in payload.get("scenarios") or []:
        lines.append(f"### {s.get('title')}（`{s.get('id')}`）")
        lines.append(f"- 种子表数：{s.get('seed_table_count')}")
        lines.append(f"- 路径：{s.get('path_summary')}")
        lines.append("")

    live = payload.get("live_queryable_entities") or []
    if live:
        lines.extend(
            [
                "## 4. 助手模拟演示实体（非平台能力背书）",
                "",
                "> 以下来自 entities.json，仅表示助手可演示的查/导能力，**不是**中软 MES 表结构平台能力清单。",
                "",
            ]
        )
        for e in live:
            lines.append(f"- `{e.get('entity')}` — {e.get('label')}")
        lines.append("")

    fields = payload.get("field_summary_rows") or []
    if fields:
        lines.extend(["## 5. 代表表字段摘要", ""])
        cur = None
        for row in fields:
            key = row.get("table")
            if key != cur:
                cur = key
                lines.append(f"### {row.get('label')} (`{key}`)")
                lines.append("")
                lines.append("| 字段 | 类型 | 可空 | 说明 |")
                lines.append("|------|------|------|------|")
            lines.append(
                f"| {row.get('field')} | {row.get('type')} | {row.get('nullable')} | "
                f"{(row.get('comment') or '').replace('|', '/')} |"
            )
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_excel(payload: dict[str, Any], path: str) -> None:
    caps = pd.DataFrame(payload.get("capabilities_by_prefix") or [])
    domain_rows = []
    for d in payload.get("domains") or []:
        reps = d.get("representative_tables") or []
        if not reps:
            domain_rows.append(
                {
                    "domain": d.get("domain"),
                    "table_count": d.get("table_count"),
                    "table": "",
                    "label": "",
                    "meaning": "",
                }
            )
        for r in reps:
            domain_rows.append(
                {
                    "domain": d.get("domain"),
                    "table_count": d.get("table_count"),
                    "table": r.get("table"),
                    "label": r.get("label"),
                    "meaning": r.get("meaning"),
                }
            )
    domains_df = pd.DataFrame(domain_rows)
    scenarios_df = pd.DataFrame(payload.get("scenarios") or [])
    fields_df = pd.DataFrame(payload.get("field_summary_rows") or [])
    live_df = pd.DataFrame(payload.get("live_queryable_entities") or [])
    overview = pd.DataFrame(
        [
            {"item": "生成时间", "value": payload.get("built_at")},
            {"item": "来源", "value": payload.get("source")},
            {"item": "字典表数", "value": payload.get("table_count")},
            {"item": "业务域数", "value": payload.get("domain_count")},
            {"item": "聚焦", "value": payload.get("focus") or "（全部）"},
            {"item": "说明", "value": payload.get("disclaimer")},
        ]
    )

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        overview.to_excel(writer, sheet_name="概述", index=False)
        if not caps.empty:
            caps.to_excel(writer, sheet_name="能力前缀", index=False)
        if not domains_df.empty:
            domains_df.to_excel(writer, sheet_name="业务域代表表", index=False)
        if not scenarios_df.empty:
            scenarios_df.to_excel(writer, sheet_name="业务场景摘要", index=False)
        if not fields_df.empty:
            fields_df.to_excel(writer, sheet_name="字段摘要", index=False)
        if not live_df.empty:
            live_df.to_excel(writer, sheet_name="模拟演示实体", index=False)


def export_schema_survey_report(
    format: Annotated[
        Literal["markdown", "excel", "both", "md", "xlsx"],
        "导出格式：markdown / excel / both（可用别名 md / xlsx）",
    ] = "both",
    focus: Annotated[
        str | None, "可选聚焦关键字，如 品质、仓储；不传则全量域地图"
    ] = None,
    include_fields: Annotated[bool, "是否附带代表表字段摘要（默认 True）"] = True,
    fields_per_table: Annotated[
        int, "每张代表表最多导出字段数，默认 15，最大 40"
    ] = 15,
) -> dict[str, Any]:
    """导出表结构摸底报告（Markdown 和/或 Excel），便于发给客户/中软对齐。"""
    fmt = (format or "both").lower().strip()
    if fmt not in ("markdown", "excel", "both", "md", "xlsx"):
        return {"error": f"不支持的 format: {format}", "hint": "用 markdown / excel / both"}
    if fmt == "md":
        fmt = "markdown"
    if fmt == "xlsx":
        fmt = "excel"

    try:
        payload = _build_report_payload(focus, include_fields, fields_per_table)
    except Exception as e:
        return {"error": str(e), "hint": "请在「系统配置 → MES 接入」上传表结构文档"}

    out_dir = _ensure_export_dir()
    stamp = _stamp()
    focus_tag = f"_{focus}" if focus else ""
    safe_tag = "".join(c if c.isalnum() or c in "-_" else "_" for c in (focus_tag or ""))
    files: dict[str, str] = {}

    try:
        if fmt in ("markdown", "both"):
            md_path = os.path.join(out_dir, f"MES表结构摸底报告{safe_tag}_{stamp}.md")
            _write_markdown(payload, md_path)
            files["markdown"] = md_path
        if fmt in ("excel", "both"):
            xlsx_path = os.path.join(out_dir, f"MES表结构摸底报告{safe_tag}_{stamp}.xlsx")
            _write_excel(payload, xlsx_path)
            files["excel"] = xlsx_path
    except Exception as e:
        return {"error": f"写入报告失败: {e}", "partial_files": files}

    return {
        "status": "ok",
        "format": fmt,
        "focus": focus,
        "table_count": payload.get("table_count"),
        "domain_count": payload.get("domain_count"),
        "files": files,
        "export_dir": out_dir,
        "note": payload.get("disclaimer"),
    }
