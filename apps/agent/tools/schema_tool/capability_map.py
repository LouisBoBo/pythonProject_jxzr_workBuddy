"""
人话能力地图：只用表结构文档说明「MES 系统业务能力」。

范围（务必遵守）：
- 本模块描述的是中软 MES 数据字典所反映的业务能力
- 查工单 / 查排产 / 导入导出 属于助手侧「模拟演示」，不并入、不改写 MES 能力
- 用户问「平台/系统能干什么」指 ZR WorkBuddy，不要用本模块的结论去回答

只读本地 capability_map.json + 表结构索引。不连数据库。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from tools.schema_tool.mes_schema_parser import build_index

_MAP_PATH = Path(__file__).resolve().parent / "capability_map.json"

_BOUNDARY = (
    "本结果只反映「表结构文档中的 MES 系统业务能力」。"
    "查工单/排产、导入导出是助手模拟演示，不代表 MES 真实已开放能力，也不应写进 MES 能力结论。"
    "若用户问的是「平台/系统」（WorkBuddy），请介绍助手产品能力，不要用本结果冒充。"
)


@lru_cache(maxsize=1)
def _load_map_raw() -> dict[str, Any]:
    if not _MAP_PATH.exists():
        return {"version": 0, "glossary": [], "capabilities": []}
    return json.loads(_MAP_PATH.read_text(encoding="utf-8"))


def reload_capability_map() -> None:
    """文档/配置更新后清缓存（供内部或重建索引时调用）。"""
    _load_map_raw.cache_clear()


def _table_meta() -> dict[str, dict[str, Any]]:
    try:
        index = build_index()
    except Exception:
        return {}
    return {t["table"]: t for t in (index.get("tables") or []) if t.get("table")}


def _enrich_capability(cap: dict[str, Any], table_meta: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """补全代表表元数据；状态只表示是否在字典中有表支撑。"""
    reps = []
    missing_tables = []
    for tname in cap.get("representative_tables") or []:
        meta = table_meta.get(tname)
        if not meta:
            missing_tables.append(tname)
            continue
        reps.append(
            {
                "table": tname,
                "label": meta.get("label"),
                "domain": meta.get("domain"),
                "meaning": (meta.get("meaning") or "")[:100],
                "field_count": meta.get("field_count"),
            }
        )

    # 兼容旧配置里的 assistant.ask_examples
    ask = list(cap.get("ask_examples") or [])
    if not ask:
        ask = list((cap.get("assistant") or {}).get("ask_examples") or [])

    if reps:
        status = "schema_backed"
        status_label = "表结构可佐证（MES 业务能力）"
    elif missing_tables and (cap.get("representative_tables") or []):
        status = "schema_partial"
        status_label = "配置了代表表但字典中部分未找到"
    else:
        status = "schema_unverified"
        status_label = "暂无代表表（未纳入本字典结论）"

    return {
        "id": cap.get("id"),
        "name": cap.get("name"),
        "one_liner": cap.get("one_liner"),
        "business_questions": list(cap.get("business_questions") or []),
        "user_phrases": list(cap.get("user_phrases") or []),
        "schema_domains": list(cap.get("schema_domains") or []),
        "schema_note": cap.get("schema_note"),
        "representative_tables": reps,
        "missing_tables_in_doc": missing_tables,
        "related_scenarios": list(cap.get("related_scenarios") or []),
        "ask_examples": ask,
        "status": status,
        "status_label": status_label,
    }


def list_platform_capabilities() -> dict[str, Any]:
    """用人话列出 MES 系统业务能力地图（仅表结构视角）。

    适用：「MES系统能干什么」「MES 有哪些业务模块」「根据表结构给功能总览」。
    不要用本工具回答「平台/系统能干什么」（那是 WorkBuddy 产品介绍）。
    不要用本工具回答「帮我查工单/排产」——那是模拟演示查询。
    """
    reload_capability_map()
    raw = _load_map_raw()
    caps = raw.get("capabilities") or []
    if not caps:
        return {
            "error": "能力地图配置为空或缺失",
            "hint": f"请检查 {_MAP_PATH}",
        }

    table_meta = _table_meta()
    enriched = [_enrich_capability(c, table_meta) for c in caps]
    backed = [c for c in enriched if c["status"] == "schema_backed"]
    other = [c for c in enriched if c["status"] != "schema_backed"]

    return {
        "scope": raw.get("scope") or "schema_only",
        "scope_note": raw.get("scope_note") or _BOUNDARY,
        "capability_count": len(enriched),
        "summary": {
            "schema_backed": [
                {"id": c["id"], "name": c["name"], "one_liner": c["one_liner"]} for c in backed
            ],
            "other": [
                {"id": c["id"], "name": c["name"], "one_liner": c["one_liner"], "status": c["status"]}
                for c in other
            ],
        },
        "capabilities": [
            {
                "id": c["id"],
                "name": c["name"],
                "one_liner": c["one_liner"],
                "status": c["status"],
                "status_label": c["status_label"],
                "schema_domains": c["schema_domains"],
                "user_phrases": c["user_phrases"][:6],
                "ask_examples": c["ask_examples"][:2],
            }
            for c in enriched
        ],
        "glossary_count": len(raw.get("glossary") or []),
        "demo_note": (
            "另：助手里「查工单/查排产/导入导出」是模拟演示功能，"
            "与本 MES 能力地图无关，请勿在「MES系统能干什么」的结论里当成真实 MES 全量能力。"
            "用户问「平台/系统」时请介绍 ZR WorkBuddy，不要用本结果回答。"
        ),
        "note": _BOUNDARY + " 详情用 describe_platform_capability；场景路径用 get_scenario_table_pack。",
    }


def describe_platform_capability(
    focus: Annotated[
        str, "能力 id（如 warehouse）或说法（如 仓储、工单、品质、OQC）"
    ],
) -> dict[str, Any]:
    """按模块或用户说法，返回表结构视角的人话能力详情。"""
    reload_capability_map()
    q = (focus or "").strip()
    if not q:
        return {
            "error": "请提供 focus，例如：仓储、工单、品质、production-execution",
            "hint": "可先 list_platform_capabilities 看总览",
        }

    # 排产/生产计划：表结构地图不单列该模块，引导术语说明 + 边界
    if any(k in q for k in ("排产", "排程", "生产计划")) and "工单" not in q:
        gloss = list_platform_glossary(keyword="生产计划")
        return {
            "id": None,
            "name": "生产计划（非表结构能力条目）",
            "one_liner": "中软 MES 表结构摸底不以「排产/排程」为独立 MES 能力模块",
            "status": "not_in_schema_map",
            "status_label": "不在本表结构能力地图中",
            "glossary": gloss.get("glossary") or [],
            "note": (
                "若问「MES 表结构里有哪些能力」：请看 list_platform_capabilities。"
                "若要「查排产数据」：那是助手模拟演示（production-plans），不是 MES 能力结论。"
                "若问「平台/系统能干什么」：介绍 ZR WorkBuddy，不要用本结果回答。"
            ),
            "scope_note": _BOUNDARY,
        }

    raw = _load_map_raw()
    caps = raw.get("capabilities") or []
    table_meta = _table_meta()
    q_l = q.lower()

    matched: dict[str, Any] | None = None
    for c in caps:
        if c.get("id") == q or (c.get("id") or "").lower() == q_l:
            matched = c
            break
        if q in (c.get("name") or "") or (c.get("name") or "") in q:
            matched = c
            break
        phrases = c.get("user_phrases") or []
        if any(q in p or p in q for p in phrases):
            matched = c
            break

    if not matched:
        best: tuple[int, dict[str, Any] | None] = (0, None)
        for c in caps:
            blob = " ".join(
                [
                    c.get("id") or "",
                    c.get("name") or "",
                    c.get("one_liner") or "",
                    *(c.get("user_phrases") or []),
                    *(c.get("business_questions") or []),
                ]
            ).lower()
            score = 0
            for tok in [q_l, *q.replace("/", " ").split()]:
                tok = tok.strip().lower()
                if len(tok) >= 2 and tok in blob:
                    score += 2
            if score > best[0]:
                best = (score, c)
        matched = best[1]

    if not matched:
        return {
            "error": f"未匹配到能力模块: {focus}",
            "hint": "先 list_platform_capabilities，或换说法：生产、仓储、品质、设备、采购、出货、SPC",
            "available": [{"id": c.get("id"), "name": c.get("name")} for c in caps],
            "scope_note": _BOUNDARY,
        }

    enriched = _enrich_capability(matched, table_meta)
    gloss = []
    phrase_blob = " ".join(enriched.get("user_phrases") or []) + " " + (enriched.get("name") or "")
    for g in raw.get("glossary") or []:
        term = g.get("term") or ""
        als = g.get("also_called") or []
        if term and (term in phrase_blob or any(a in phrase_blob for a in als)):
            gloss.append(g)
        elif any(term in p or p in term for p in (enriched.get("user_phrases") or [])):
            gloss.append(g)

    return {
        **enriched,
        "glossary": gloss,
        "scope_note": raw.get("scope_note") or _BOUNDARY,
        "demo_note": (
            "不要把「查工单/导入导出」写进本模块的平台能力结论；"
            "那些是模拟演示。本模块只讲表结构业务含义与代表表。"
        ),
        "note": (
            "依据本地表结构字典。若 related_scenarios 非空，可用 get_scenario_table_pack 看阶段路径。"
        ),
    }


def list_platform_glossary(
    keyword: Annotated[str | None, "可选，按术语或别名筛选，如 工单、排产、IPQC"] = None,
) -> dict[str, Any]:
    """列出平台常见术语的人话解释（工单/排产/IPQC 等）。"""
    reload_capability_map()
    raw = _load_map_raw()
    items = list(raw.get("glossary") or [])
    if keyword:
        k = keyword.strip()
        items = [
            g
            for g in items
            if k in (g.get("term") or "")
            or k in (g.get("plain") or "")
            or any(k in a for a in (g.get("also_called") or []))
        ]
    return {
        "count": len(items),
        "glossary": items,
        "note": "术语小抄（表结构语境）。查工单/排产演示数据请走查询工具，勿与平台能力地图混谈。",
        "scope_note": raw.get("scope_note") or _BOUNDARY,
    }
