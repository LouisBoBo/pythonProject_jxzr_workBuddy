"""
人话能力地图：只用表结构文档说明「MES 系统业务能力」。

范围（务必遵守）：
- 本模块描述的是**当前资料包**表结构文档所反映的业务能力
- 查数 / 导入导出依据可查对象目录，不并入、不改写 MES 能力结论
- 用户问「平台/系统能干什么」指 ZR WorkBuddy，不要用本模块的结论去回答

只读资料包内 capability_map.json（若有）+ 表结构索引。不连数据库。
未配置时返回空能力列表。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from mes_profile import resolve_capability_map_path
from tools.schema_tool.mes_schema_parser import build_index
from tools.schema_tool.schema_infer import (
    infer_capabilities_from_index,
    infer_glossary_from_index,
)

_BOUNDARY = (
    "本结果只反映「当前已配置表结构文档中的 MES 系统业务能力」。"
    "查数/导入导出依据可查对象目录，不代表 MES 全量能力，也不应写进 MES 能力结论。"
    "若用户问的是「平台/系统」（WorkBuddy），请介绍助手产品能力，不要用本结果冒充。"
)

_map_cache: dict[str, Any] | None = None
_map_key: tuple[str, float] | None = None


def _load_map_raw() -> dict[str, Any]:
    global _map_cache, _map_key
    path, _src = resolve_capability_map_path()
    if path is None:
        return {"version": 0, "glossary": [], "capabilities": []}
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {"version": 0, "glossary": [], "capabilities": []}
    key = (str(path), mtime)
    if _map_cache is not None and _map_key == key:
        return _map_cache
    if not path.exists():
        raw = {"version": 0, "glossary": [], "capabilities": []}
    else:
        raw = json.loads(path.read_text(encoding="utf-8"))
    _map_cache = raw
    _map_key = key
    return raw


def reload_capability_map() -> None:
    """文档/配置更新后清缓存（供内部或重建索引时调用）。"""
    global _map_cache, _map_key
    _map_cache = None
    _map_key = None


def _schema_index() -> dict[str, Any]:
    try:
        return build_index()
    except Exception:
        return {"tables": [], "domains": []}


def _resolved_map() -> dict[str, Any]:
    """资料包有能力地图则用之；否则按当前表结构域推断，换平台不必手写 JSON。"""
    raw = dict(_load_map_raw() or {})
    caps = list(raw.get("capabilities") or [])
    gloss = list(raw.get("glossary") or [])
    index = _schema_index()
    map_source = "profile"
    if not caps:
        caps = infer_capabilities_from_index(index)
        map_source = "inferred_from_schema"
    if not gloss:
        gloss = infer_glossary_from_index(index)
    raw["capabilities"] = caps
    raw["glossary"] = gloss
    raw["map_source"] = map_source
    return raw


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
    不要用本工具回答「帮我查业务数据」——那是可查对象目录上的查询工具。
    """
    reload_capability_map()
    raw = _resolved_map()
    caps = raw.get("capabilities") or []
    _path, src = resolve_capability_map_path()
    if not caps:
        return {
            "capabilities": [],
            "capability_count": 0,
            "summary": {"schema_backed": [], "other": []},
            "scope": "schema_only",
            "scope_note": _BOUNDARY,
            "map_source": raw.get("map_source") or "empty",
            "note": (
                "当前没有可推断的表结构模块。"
                "请先在「系统配置 → MES 接入」上传表结构（.md）；"
                "也可在资料包放 capability_map.json 覆盖自动推断。"
            ),
            "source": src,
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
        "map_source": raw.get("map_source") or "profile",
        "demo_note": (
            "另：助手里「查数/导入导出」依据可查对象目录，"
            "与本 MES 能力地图无关，请勿在「MES系统能干什么」的结论里当成真实 MES 全量能力。"
            "用户问「平台/系统」时请介绍 ZR WorkBuddy，不要用本结果回答。"
        ),
        "note": (
            _BOUNDARY
            + " 详情用 describe_platform_capability；场景路径用 get_scenario_table_pack。"
            + (
                " 本轮能力地图由当前表结构域自动生成（资料包未提供 capability_map.json）。"
                if raw.get("map_source") == "inferred_from_schema"
                else ""
            )
        ),
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

    # 常见业务说法若不在能力地图：引导查 glossary / list，勿硬编码演示实体
    if any(k in q for k in ("排产", "排程", "生产计划")) and "工单" not in q:
        gloss = list_platform_glossary(keyword="生产计划")
        return {
            "id": None,
            "name": "生产计划（需对照当前表结构）",
            "one_liner": "请以当前资料包表结构与能力地图为准，勿套用仓库旧演示实体",
            "status": "not_in_schema_map",
            "status_label": "不在当前能力地图或需术语核对",
            "glossary": gloss.get("glossary") or [],
            "note": (
                "若问「MES 表结构里有哪些能力」：请看 list_platform_capabilities。"
                "若要「查业务列表数据」：请走可查对象查询工具，不是 MES 能力结论。"
                "若问「平台/系统能干什么」：介绍 ZR WorkBuddy，不要用本结果回答。"
            ),
            "scope_note": _BOUNDARY,
        }

    raw = _resolved_map()
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
            "不要把「查数/导入导出」写进本模块的平台能力结论；"
            "那些依据可查对象目录。本模块只讲表结构业务含义与代表表。"
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
    raw = _resolved_map()
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
        "note": "术语小抄（表结构语境）。查业务数据请走查询工具，勿与平台能力地图混谈。",
        "scope_note": raw.get("scope_note") or _BOUNDARY,
    }
