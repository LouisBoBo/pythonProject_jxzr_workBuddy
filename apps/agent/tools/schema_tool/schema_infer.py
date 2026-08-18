"""从表结构索引推断能力地图 / 术语 / 场景表，不写死某一套 MES 表名。"""
from __future__ import annotations

import re
from typing import Any

# 跨平台通用术语（不是某一客户的表名）
GENERIC_GLOSSARY: list[dict[str, Any]] = [
    {
        "term": "工单",
        "also_called": ["MO", "制造订单", "派工单", "生产任务", "work order"],
        "plain": "一张要生产的任务单据，不是排产计划本身。",
    },
    {
        "term": "排产",
        "also_called": ["生产计划", "排程", "APS"],
        "plain": "何时在哪条线做；与工单列表通常不是同一张单。",
    },
    {
        "term": "在制",
        "also_called": ["WIP", "进行中"],
        "plain": "已开工、尚未完工。",
    },
    {
        "term": "点检",
        "also_called": ["巡检", "设备点检"],
        "plain": "按计划检查设备状态，通常不是生产工单。",
    },
    {
        "term": "IPQC",
        "also_called": ["制程检验", "过程检验"],
        "plain": "生产过程中的品质检验。",
    },
    {
        "term": "OQC",
        "also_called": ["出货检验"],
        "plain": "发货前品质检验。",
    },
]


def infer_capabilities_from_index(index: dict[str, Any] | None) -> list[dict[str, Any]]:
    """每个业务域一块能力；代表表取该域字段较多的若干张。"""
    index = index or {}
    tables = [t for t in (index.get("tables") or []) if isinstance(t, dict) and t.get("table")]
    if not tables:
        return []
    domains = [d for d in (index.get("domains") or []) if isinstance(d, dict)]
    by_domain: dict[str, list[dict[str, Any]]] = {}
    for t in tables:
        dname = str(t.get("domain") or "未分类").strip() or "未分类"
        by_domain.setdefault(dname, []).append(t)
    ordered_names: list[str] = []
    for d in domains:
        name = str(d.get("domain") or "").strip()
        if name and name not in ordered_names:
            ordered_names.append(name)
    for name in by_domain:
        if name not in ordered_names:
            ordered_names.append(name)
    caps: list[dict[str, Any]] = []
    for i, dname in enumerate(ordered_names):
        items = by_domain.get(dname) or []
        if not items:
            continue
        scored = sorted(
            items,
            key=lambda x: (-int(x.get("field_count") or 0), str(x.get("table") or "")),
        )
        top = scored[:8]
        did = str((domains[i].get("domain_id") if i < len(domains) else "") or "").strip()
        cap_id = _slug(did or dname, f"domain-{i + 1}")
        caps.append(
            {
                "id": cap_id,
                "name": dname,
                "one_liner": f"{dname}：当前表结构文档中有 {len(items)} 张相关表。",
                "business_questions": [f"{dname}管哪些业务？", f"{dname}有哪些主表？"],
                "user_phrases": [dname],
                "schema_domains": [dname],
                "representative_tables": [str(x.get("table")) for x in top if x.get("table")],
                "related_scenarios": [],
                "ask_examples": [f"{dname}能管哪些事", f"{dname}有哪些表"],
                "inferred": True,
            }
        )
    return caps


def infer_glossary_from_index(index: dict[str, Any] | None) -> list[dict[str, Any]]:
    """通用术语 + 当前文档表中文名。"""
    items: list[dict[str, Any]] = [dict(g) for g in GENERIC_GLOSSARY]
    seen = {str(g["term"]) for g in items}
    for t in (index or {}).get("tables") or []:
        if not isinstance(t, dict):
            continue
        label = str(t.get("label") or "").strip()
        table = str(t.get("table") or "").strip()
        if not label or label in seen or len(label) > 20:
            continue
        seen.add(label)
        items.append(
            {
                "term": label,
                "also_called": [table] if table else [],
                "plain": str(t.get("meaning") or f"表 `{table}`").strip()[:120],
                "inferred": True,
            }
        )
        if len(items) >= 48:
            break
    return items


def match_tables_for_stage(
    known: dict[str, dict[str, Any]],
    *,
    exact_names: list[str] | None = None,
    keywords: list[str] | None = None,
    limit: int = 8,
) -> tuple[list[str], list[str]]:
    """先精确表名，再按表名/中文名关键字匹配当前文档。"""
    hits: list[str] = []
    unused_seeds: list[str] = []
    seen: set[str] = set()
    for name in exact_names or []:
        if name in known and name not in seen:
            hits.append(name)
            seen.add(name)
        elif name not in known:
            unused_seeds.append(name)
        if len(hits) >= limit:
            return hits, unused_seeds
    scored: list[tuple[int, str]] = []
    for tname, meta in known.items():
        if tname in seen:
            continue
        score = _keyword_score(meta, keywords or [])
        if score >= 4:
            scored.append((score, tname))
    scored.sort(key=lambda x: (-x[0], x[1]))
    for _score, tname in scored:
        if len(hits) >= limit:
            break
        hits.append(tname)
        seen.add(tname)
    return hits, unused_seeds


def _keyword_score(meta: dict[str, Any], keywords: list[str]) -> int:
    table = str(meta.get("table") or "").lower()
    label = str(meta.get("label") or "").lower()
    domain = str(meta.get("domain") or "").lower()
    meaning = str(meta.get("meaning") or "")[:80].lower()
    score = 0
    for raw in keywords:
        k = str(raw or "").strip().lower()
        if len(k) < 2:
            continue
        if k in table:
            score += 5
        elif k in label:
            score += 4
        elif k in domain:
            score += 2
        elif k in meaning:
            score += 1
    return score


def _slug(text: str, fallback: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", (text or "").strip())
    s = s.strip("-").lower()[:40]
    return s or fallback
