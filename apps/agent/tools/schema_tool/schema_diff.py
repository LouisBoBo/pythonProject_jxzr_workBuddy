"""文档（表结构）vs 接口目录对照。默认不打 MES，换平台仍可用。"""
from __future__ import annotations

import json
import re
from typing import Annotated, Any

from tools.query_tool.entity_catalog import load_catalog
from tools.schema_tool.mes_schema_parser import build_index

_PREFIXES = ("tbl_", "tbl", "t_")
_STOP = frozenset(
    {
        "list",
        "api",
        "data",
        "info",
        "item",
        "items",
        "main",
        "detail",
        "log",
        "the",
        "and",
        "表",
        "主表",
        "明细",
    }
)


def _fold(text: str) -> str:
    s = (text or "").strip().lower()
    for p in _PREFIXES:
        if s.startswith(p):
            s = s[len(p) :]
            break
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", s)


def _terms(*parts: Any) -> list[str]:
    out: list[str] = []
    for part in parts:
        if isinstance(part, (list, tuple)):
            for x in part:
                t = str(x or "").strip()
                if t and t not in out:
                    out.append(t)
            continue
        t = str(part or "").strip()
        if t and t not in out:
            out.append(t)
    return out


def _tokens(text: str) -> set[str]:
    folded = _fold(text)
    toks: set[str] = set()
    if len(folded) >= 2:
        toks.add(folded)
    for piece in re.split(r"[\s_\-/]+", (text or "").strip().lower()):
        f = _fold(piece)
        if len(f) >= 2 and f not in _STOP:
            toks.add(f)
    return toks


def _score_pair(table_terms: list[str], entity_terms: list[str]) -> int:
    best = 0
    t_folds = [_fold(x) for x in table_terms if x]
    e_folds = [_fold(x) for x in entity_terms if x]
    for tf in t_folds:
        if len(tf) < 2:
            continue
        for ef in e_folds:
            if len(ef) < 2:
                continue
            if tf == ef:
                best = max(best, 100 + min(len(tf), 20))
            elif len(tf) >= 3 and len(ef) >= 3 and (tf in ef or ef in tf):
                best = max(best, 70 + min(len(tf), len(ef), 20))
    for t in table_terms:
        tt = str(t or "").strip()
        if len(tt) < 2 or tt in _STOP:
            continue
        for e in entity_terms:
            ee = str(e or "").strip()
            if len(ee) < 2 or ee in _STOP:
                continue
            if tt == ee:
                best = max(best, 95)
            elif tt in ee or ee in tt:
                best = max(best, 72 if min(len(tt), len(ee)) >= 2 else 0)
    t_toks: set[str] = set()
    e_toks: set[str] = set()
    for x in table_terms:
        t_toks |= _tokens(x)
    for x in entity_terms:
        e_toks |= _tokens(x)
    overlap = {x for x in (t_toks & e_toks) if len(x) >= 2 and x not in _STOP}
    if overlap:
        best = max(best, 40 + min(20, 5 * len(overlap)))
    return best


def _load_overlay_pairs() -> list[dict[str, str]]:
    try:
        from mes_profile import profile_dir

        pdir = profile_dir()
        if pdir is None:
            return []
        path = pdir / "schema_catalog_map.json"
        if not path.is_file() or path.stat().st_size <= 0:
            return []
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return []
    pairs = data.get("pairs") if isinstance(data, dict) else None
    out: list[dict[str, str]] = []
    for row in pairs or []:
        if not isinstance(row, dict):
            continue
        table = str(row.get("table") or "").strip()
        entity = str(row.get("entity") or "").strip()
        if table and entity:
            out.append({"table": table, "entity": entity})
    return out


def compare_schema_vs_catalog(
    sample_live: Annotated[
        bool,
        "是否对已匹配实体做只读抽检（limit=1）。默认 false，不打 MES，避免和查数混用",
    ] = False,
    min_score: Annotated[int, "启发式匹配最低分，默认 70"] = 70,
) -> dict[str, Any]:
    """对照当前资料包：表结构文档（L0）与 OpenAPI 可查对象（L1）。

    默认只做名称/别名启发式 + 资料包可选 schema_catalog_map.json。
    不写 MES；sample_live 才抽检，且最多 5 条。换一套 MES 仍走同一工具。
    """
    try:
        index = build_index()
    except Exception as e:
        return {
            "error": f"{type(e).__name__}：表结构未能解析",
            "hint": "请在「系统配置 → MES 接入」上传表结构文档",
        }
    tables = [t for t in (index.get("tables") or []) if isinstance(t, dict) and t.get("table")]
    catalog = [e for e in load_catalog() if isinstance(e, dict) and e.get("id")]
    if not tables and not catalog:
        return {
            "error": "表结构与可查对象目录都为空",
            "hint": "先在系统配置上传表结构 .md，并导入接口文档生成可查对象。",
        }

    overlay = _load_overlay_pairs()
    overlay_hits: dict[str, str] = {p["table"].lower(): p["entity"] for p in overlay}
    used_entities: set[str] = set()
    matched: list[dict[str, Any]] = []

    for table in tables:
        tname = str(table.get("table") or "")
        t_terms = _terms(tname, table.get("label"), table.get("meaning"))
        forced = overlay_hits.get(tname.lower())
        if forced:
            ent = next((e for e in catalog if str(e.get("id")) == forced), None)
            if ent:
                used_entities.add(str(ent["id"]))
                matched.append(
                    {
                        "table": tname,
                        "table_label": table.get("label"),
                        "entity": ent["id"],
                        "entity_label": ent.get("label") or ent["id"],
                        "score": 1000,
                        "how": "资料包 schema_catalog_map.json",
                    }
                )
                continue
        best: tuple[int, dict[str, Any]] | None = None
        for ent in catalog:
            e_terms = _terms(
                ent.get("id"),
                ent.get("label"),
                ent.get("aliases") or [],
                str(ent.get("path") or "").rsplit("/", 1)[-1],
            )
            score = _score_pair(t_terms, e_terms)
            if best is None or score > best[0]:
                best = (score, ent)
        threshold = max(50, min(int(min_score or 70), 100))
        if best and best[0] >= threshold:
            ent = best[1]
            eid = str(ent["id"])
            if eid in used_entities:
                continue
            used_entities.add(eid)
            matched.append(
                {
                    "table": tname,
                    "table_label": table.get("label"),
                    "entity": eid,
                    "entity_label": ent.get("label") or eid,
                    "score": best[0],
                    "how": "名称/别名启发式",
                }
            )

    matched_tables = {m["table"] for m in matched}
    schema_only = [
        {"table": t.get("table"), "label": t.get("label"), "domain": t.get("domain")}
        for t in tables
        if t.get("table") not in matched_tables
    ]
    catalog_only = [
        {"entity": e.get("id"), "label": e.get("label") or e.get("id")}
        for e in catalog
        if str(e.get("id")) not in used_entities
    ]

    live: list[dict[str, Any]] = []
    if sample_live:
        live = _sample_live(matched[:5])

    return {
        "schema_table_count": len(tables),
        "catalog_entity_count": len(catalog),
        "matched_count": len(matched),
        "matched": matched[:40],
        "schema_only_count": len(schema_only),
        "schema_only": schema_only[:30],
        "catalog_only_count": len(catalog_only),
        "catalog_only": catalog_only[:30],
        "overlay_pairs": overlay,
        "live_samples": live,
        "markdown_summary": _diff_markdown(
            matched_count=len(matched),
            schema_only_count=len(schema_only),
            catalog_only_count=len(catalog_only),
            matched=matched,
            schema_only=schema_only,
            catalog_only=catalog_only,
            sample_live=bool(sample_live),
            live=live,
        ),
        "note": (
            "L0=表结构文档，L1=接口可查对象。匹配是启发式，不是同一对象的证明。"
            "默认未抽检现场数据；sample_live 才只读抽 1 条。"
            "资料包可放 schema_catalog_map.json 按 table→entity 校准。"
        ),
        "reply_hint": (
            "优先展示 markdown_summary；先报对照结论：匹配数 / 仅文档有 / 仅接口有；点名几条例子。"
            "不要把「对得上名字」说成已经查了实时库。"
            "用户要现场抽检时才 sample_live=true。"
        ),
    }


def _diff_markdown(
    *,
    matched_count: int,
    schema_only_count: int,
    catalog_only_count: int,
    matched: list[dict[str, Any]],
    schema_only: list[dict[str, Any]],
    catalog_only: list[dict[str, Any]],
    sample_live: bool,
    live: list[dict[str, Any]],
) -> str:
    lines = [
        "## 表结构 ↔ 接口目录对照",
        "",
        f"- 匹配：**{matched_count}**",
        f"- 仅文档有：**{schema_only_count}**",
        f"- 仅接口有：**{catalog_only_count}**",
        "",
        "（启发式名称匹配，不等于同一业务对象；默认未抽检现场数据。）",
    ]
    if matched:
        lines += ["", "### 匹配示例", "", "| 表 | 可查对象 | 方式 |", "| --- | --- | --- |"]
        for m in matched[:8]:
            lines.append(
                f"| {m.get('table_label') or m.get('table')} | "
                f"{m.get('entity_label') or m.get('entity')} (`{m.get('entity')}`) | "
                f"{m.get('how')} |"
            )
    if schema_only:
        lines += ["", "### 仅文档有（节选）"]
        for t in schema_only[:6]:
            lines.append(f"- {t.get('label') or t.get('table')}（`{t.get('table')}`）")
    if catalog_only:
        lines += ["", "### 仅接口有（节选）"]
        for e in catalog_only[:6]:
            lines.append(f"- {e.get('label')}（`{e.get('entity')}`）")
    if sample_live and live:
        lines += ["", "### 现场抽检"]
        for row in live[:5]:
            if row.get("error"):
                lines.append(f"- 抽检失败：{row.get('error')}")
            elif row.get("ok"):
                lines.append(
                    f"- `{row.get('entity')}`：ok，total={row.get('total')}，本次 {row.get('returned')}"
                )
            else:
                lines.append(f"- `{row.get('entity')}`：{row.get('error') or '失败'}")
    return "\n".join(lines)


def _sample_live(matched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        from tools.platform_api import get_client

        client = get_client()
    except Exception as e:
        return [{"error": f"无法抽检（{type(e).__name__}）"}]
    out: list[dict[str, Any]] = []
    for row in matched:
        eid = str(row.get("entity") or "")
        if not eid:
            continue
        try:
            raw = client.query(eid, None, 1)
        except Exception as e:
            out.append({"entity": eid, "ok": False, "error": str(e)[:200]})
            continue
        if not isinstance(raw, dict):
            out.append({"entity": eid, "ok": False, "error": "返回格式异常"})
            continue
        if raw.get("error"):
            out.append({"entity": eid, "ok": False, "error": str(raw.get("error"))[:200]})
            continue
        recs = raw.get("records") if isinstance(raw.get("records"), list) else []
        out.append(
            {
                "entity": eid,
                "ok": True,
                "total": raw.get("total"),
                "returned": len(recs),
            }
        )
    return out
