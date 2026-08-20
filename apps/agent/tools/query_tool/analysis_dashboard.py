"""资料包驱动的分析看板：多卡取数出图，缺卡诚实缺口；不写死实体 id。

设计约定（谨慎）：
- Happy path：模板卡 → 绑定当前目录 → 出图；多卡相互独立。
- 边界：某卡绑不上/抽不出 series → 仅该卡 gap，其它卡继续。
- 失败：不编造数值；不影响 query_metric / summarize 原链路。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from tools.query_tool.analysis_chart import render_analysis_chart
from tools.query_tool.entity_catalog import load_catalog
from tools.query_tool.metrics_pack import _resolve_entity
from tools.query_tool.ops_presentation import (
    build_drill_payload,
    build_kpis_from_charts,
    try_metric_kpi,
)
from tools.query_tool.query_present import resolve_group_by, summarize_records

_BUILTIN_DIR = Path(__file__).resolve().parent / "dashboard_templates"
_MAX_CARDS = 8
_MAX_POINTS = 40


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def _safe_template_id(raw: str) -> str:
    s = "".join(c for c in (raw or "").strip() if c.isalnum() or c in "-_")
    return s or "pcb_ops"


def load_dashboard_template(template_id: str = "pcb_ops") -> dict[str, Any]:
    """资料包 dashboards/{id}.json 优先，否则内置 dashboard_templates/。"""
    tid = _safe_template_id(template_id)
    try:
        from mes_profile import profile_dir

        pdir = profile_dir()
    except Exception:
        pdir = None
    if pdir is not None:
        custom = pdir / "dashboards" / f"{tid}.json"
        if custom.is_file():
            data = _read_json(custom)
            if data and isinstance(data.get("cards"), list):
                data = dict(data)
                data["_source"] = f"profile:{custom.name}"
                return data
    builtin = _BUILTIN_DIR / f"{tid}.json"
    data = _read_json(builtin)
    if data and isinstance(data.get("cards"), list):
        data = dict(data)
        data["_source"] = f"builtin:{builtin.name}"
        return data
    return {
        "id": tid,
        "label": tid,
        "cards": [],
        "_source": "missing",
        "error": f"未找到看板模板 {tid!r}",
    }


def series_from_records(
    records: list[Any],
    *,
    category_fields: list[str],
    value_fields: list[str],
    prefer_nonzero: bool = True,
) -> tuple[list[str], list[float], str | None]:
    """从记录抽 categories/values；抽不出返回空 + 原因。

    优先用模板字段；失败时回退到常见类目/产量字段名（跨厂友好，不写死实体 id）。
    prefer_nonzero=True 时：若首选数值字段全为 0，改用后续非零字段（如 today→week）。
    """
    if not records:
        return [], [], "无记录"
    cat_keys = [str(x) for x in category_fields if str(x).strip()]
    val_keys = [str(x) for x in value_fields if str(x).strip()]
    cat_fallback = [
        "name",
        "label",
        "code",
        "time",
        "title",
        "key",
        "product_model",
        "production_line",
        "line",
        "device_name",
        "process",
    ]
    val_fallback = [
        "today_output",
        "week_output",
        "month_output",
        "lot_output",
        "model_output",
        "today_completed",
        "today_area_output",
        "total_completed",
        "actual_qty",
        "area_output",
        "quantity",
        "qty",
        "output",
        "value",
        "count",
    ]

    def _cat_keys() -> list[str]:
        out = list(cat_keys)
        for k in cat_fallback:
            if k not in out:
                out.append(k)
        return out

    def _val_keys() -> list[str]:
        out = list(val_keys)
        for k in val_fallback:
            if k not in out:
                out.append(k)
        return out

    def _pick_cat(rec: dict[str, Any], keys: list[str]) -> tuple[str | None, str]:
        for k in keys:
            if k not in rec or rec[k] is None:
                continue
            s = str(rec[k]).strip()
            if s:
                return s[:80], k
        return None, ""

    def _sum_for_key(key: str) -> float | None:
        total = 0.0
        hit = False
        for rec in records:
            if not isinstance(rec, dict) or key not in rec or rec[key] is None:
                continue
            try:
                total += float(rec[key])
                hit = True
            except (TypeError, ValueError):
                continue
        return total if hit else None

    ck = _cat_keys()
    vk = _val_keys()
    # 选定数值字段：顺序优先；全 0 时换下一个有正数的字段
    chosen_v = ""
    first_available = ""
    for k in vk:
        s = _sum_for_key(k)
        if s is None:
            continue
        if not first_available:
            first_available = k
        if prefer_nonzero:
            if s != 0.0:
                chosen_v = k
                break
        else:
            chosen_v = k
            break
    if not chosen_v:
        chosen_v = first_available
        # 扫字段名启发式
        for rec in records:
            if not isinstance(rec, dict):
                continue
            for k, v in rec.items():
                kl = str(k).lower()
                if not any(
                    t in kl for t in ("output", "completed", "qty", "quantity", "count", "value")
                ):
                    continue
                if "rate" in kl or "pct" in kl or "percent" in kl:
                    continue
                try:
                    float(v)
                except (TypeError, ValueError):
                    continue
                chosen_v = str(k)
                break
            if chosen_v:
                break

    if not chosen_v:
        keys = sorted({str(k) for r in records if isinstance(r, dict) for k in r.keys()})[:12]
        return [], [], f"无法从记录抽取类目/数值（所见字段：{', '.join(keys) or '无'}）"

    cats: list[str] = []
    vals: list[float] = []
    used_c = ""
    for rec in records:
        if not isinstance(rec, dict):
            continue
        c_val, c_key = _pick_cat(rec, ck)
        if c_val is None:
            continue
        if chosen_v not in rec or rec[chosen_v] is None:
            continue
        try:
            v_val = float(rec[chosen_v])
        except (TypeError, ValueError):
            continue
        cats.append(str(c_val))
        vals.append(v_val)
        used_c = c_key

    if not cats:
        keys = sorted({str(k) for r in records if isinstance(r, dict) for k in r.keys()})[:12]
        return [], [], f"无法从记录抽取类目/数值（所见字段：{', '.join(keys) or '无'}）"

    merged: dict[str, float] = {}
    for c, v in zip(cats, vals, strict=False):
        merged[c] = merged.get(c, 0.0) + float(v)
    items = sorted(merged.items(), key=lambda x: x[1], reverse=True)[:_MAX_POINTS]
    note = f"系列字段 {used_c}/{chosen_v}" if used_c else f"系列字段 ?/{chosen_v}"
    if prefer_nonzero and chosen_v and _sum_for_key(chosen_v) == 0.0:
        note += "（数值全为 0）"
    elif prefer_nonzero and "today" in chosen_v.lower():
        pass
    elif prefer_nonzero and any(
        t in chosen_v.lower() for t in ("week", "month", "total")
    ):
        # 说明发生了 today→week 类切换
        today_sum = _sum_for_key("today_output")
        if today_sum == 0.0:
            note += "（今日产量为 0，已改用非零产量字段）"
    return [c for c, _ in items], [v for _, v in items], note


def _entity_candidates(hints: list[Any], catalog: list[dict[str, Any]]) -> list[str]:
    """按 hint 顺序解析候选实体（保留顺序、去重），便于首个抽不出 series 时换下一个。"""
    out: list[str] = []
    for hint in hints:
        eid = _resolve_entity([hint], catalog)
        if eid and eid not in out:
            out.append(eid)
    # 全局最优兜底（可能与顺序不同）
    best = _resolve_entity(hints, catalog)
    if best and best not in out:
        out.append(best)
    return out


def _card_gap(card: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "id": card.get("id"),
        "title": card.get("title") or card.get("id"),
        "status": "gap",
        "reason": reason[:300],
    }


def _run_entity_series(
    card: dict[str, Any],
    *,
    catalog: list[dict[str, Any]],
    user_intent: str,
) -> dict[str, Any]:
    hints = list(card.get("entity_hints") or [])
    candidates = _entity_candidates(hints, catalog)
    if not candidates:
        return _card_gap(card, "当前资料包没有与该卡匹配的可查对象。")
    try:
        from tools.platform_api import get_client
    except Exception as e:  # noqa: BLE001
        return _card_gap(card, f"查询客户端不可用：{type(e).__name__}")

    limit = max(1, min(int(card.get("limit") or 50), 100))
    client = get_client()
    last_reason = ""
    for eid in candidates:
        raw = client.query(eid, None, limit)
        if not isinstance(raw, dict) or raw.get("error"):
            err = (raw or {}).get("error") if isinstance(raw, dict) else "查询失败"
            last_reason = f"查询 `{eid}` 失败：{err}"
            continue
        records = raw.get("records") if isinstance(raw.get("records"), list) else []
        cats, vals, note = series_from_records(
            records,
            category_fields=list(card.get("category_fields") or []),
            value_fields=list(card.get("value_fields") or []),
        )
        if not cats:
            last_reason = f"`{eid}`：{note or '无法解析 series'}"
            continue

        title = str(card.get("title") or eid)
        series_name = str(card.get("series_name") or "数量")
        extra_caveats: list[str] = []
        if note and "改用非零产量字段" in note:
            if "week_output" in note:
                title = f"{title}（本周·今日为0）"
                series_name = "本周产量"
                extra_caveats.append(
                    "今日 today_output 均为 0，已改用 week_output（本周产量）展示，非编造"
                )
            else:
                extra_caveats.append(str(note))
        intent = f"{user_intent} {card.get('chart_intent') or ''} {title}".strip()
        card_ct = str(card.get("chart_type") or "auto").strip() or "auto"
        chart = render_analysis_chart(
            chart_type=card_ct,
            title=title,
            categories=cats,
            values=vals,
            series_name=series_name,
            definition=str(card.get("definition") or ""),
            source_note=f"实体 `{eid}`，本次 {len(records)} 条" + (f"；{note}" if note else ""),
            user_intent=intent,
        )
        if chart.get("error"):
            last_reason = str(chart.get("error"))
            continue
        caveats = list(chart.get("caveats") or []) + extra_caveats
        group_field = None
        for f in card.get("category_fields") or []:
            fs = str(f)
            if any(isinstance(r, dict) and fs in r for r in records):
                group_field = fs
                break
        drill = build_drill_payload(
            card_id=str(card.get("id") or eid),
            title=title,
            group_field=group_field,
            categories=cats,
            values=vals,
            records=records,
            entity=eid,
        )
        return {
            "id": card.get("id"),
            "title": title,
            "status": "ok",
            "entity": eid,
            "point_count": chart.get("point_count"),
            "chart_type": chart.get("chart_type"),
            "chart_option": chart.get("chart_option"),
            "caveats": caveats,
            "definition": chart.get("definition") or "",
            "layout": chart.get("layout") or {},
            "drill": drill,
        }

    reason = last_reason or "无法解析为图表 series"
    soft = str(card.get("soft_gap") or "").strip()
    if soft:
        reason = f"{reason}；{soft}"
    return _card_gap(card, reason)


def _run_metric_groups(
    card: dict[str, Any],
    *,
    user_intent: str,
) -> dict[str, Any]:
    from tools.query_tool.platform_query import query_metric

    metric_name = str(card.get("metric") or "").strip()
    if not metric_name:
        return _card_gap(card, "模板未配置 metric")
    out = query_metric(metric_name, limit=max(1, min(int(card.get("limit") or 50), 100)))
    if not isinstance(out, dict) or out.get("error"):
        return _card_gap(
            card,
            str((out or {}).get("error") or "口径查询失败")
            + (f"；{out.get('hint')}" if isinstance(out, dict) and out.get("hint") else ""),
        )
    records = out.get("records") if isinstance(out.get("records"), list) else []
    if not records:
        # 有些 present 只给 display_rows
        rows = out.get("display_rows") if isinstance(out.get("display_rows"), list) else []
        records = [r for r in rows if isinstance(r, dict)]
    if not records:
        return _card_gap(card, f"口径「{out.get('metric_label') or metric_name}」返回 0 条")

    field = None
    available = []
    if records and isinstance(records[0], dict):
        available = [str(k) for k in records[0].keys()]
    for hint in card.get("group_by_hints") or []:
        field = resolve_group_by(str(hint), available)
        if field:
            break
    if not field:
        # 退化：直接尝试从 records 抽 series
        cats, vals, note = series_from_records(
            records,
            category_fields=["priority", "status", "value", "name"],
            value_fields=["count", "quantity", "value"],
        )
        if not cats:
            return _card_gap(card, f"无法按优先级等字段分组（{note}）")
    else:
        groups = summarize_records(records, field)
        cats = [str(g.get("value") or "") for g in groups]
        vals = []
        for g in groups:
            try:
                vals.append(float(g.get("count") or 0))
            except (TypeError, ValueError):
                vals.append(0.0)

    title = str(card.get("title") or out.get("metric_label") or metric_name)
    intent = f"{user_intent} {card.get('chart_intent') or ''} {title}".strip()
    card_ct = str(card.get("chart_type") or "auto").strip() or "auto"
    chart = render_analysis_chart(
        chart_type=card_ct,
        title=title,
        categories=cats,
        values=vals,
        series_name=str(card.get("series_name") or "条数"),
        definition=str(out.get("definition") or card.get("definition") or ""),
        source_note=(
            f"口径 `{out.get('metric')}` → `{out.get('entity')}`，"
            f"本次 {out.get('returned') or len(records)} 条"
        ),
        user_intent=intent,
    )
    if chart.get("error"):
        return _card_gap(card, str(chart.get("error")))
    caveats = list(out.get("caveats") or []) + list(chart.get("caveats") or [])
    display_rows = out.get("display_rows") if isinstance(out.get("display_rows"), list) else None
    drill = build_drill_payload(
        card_id=str(card.get("id") or metric_name),
        title=title,
        group_field=field,
        categories=cats,
        values=vals,
        records=records,
        display_rows=display_rows,
        entity=str(out.get("entity") or ""),
    )
    return {
        "id": card.get("id"),
        "title": title,
        "status": "ok",
        "entity": out.get("entity"),
        "metric": out.get("metric"),
        "point_count": chart.get("point_count"),
        "chart_type": chart.get("chart_type"),
        "chart_option": chart.get("chart_option"),
        "caveats": caveats,
        "definition": chart.get("definition") or out.get("definition") or "",
        "layout": chart.get("layout") or {},
        "drill": drill,
    }


def _run_card(
    card: dict[str, Any],
    *,
    catalog: list[dict[str, Any]],
    user_intent: str,
) -> dict[str, Any]:
    if not isinstance(card, dict):
        return _card_gap({"id": "?", "title": "?"}, "非法卡配置")
    kind = str(card.get("kind") or "").strip().lower()
    if kind == "gap":
        return _card_gap(card, str(card.get("gap_reason") or "资料包未覆盖该能力"))
    if kind == "entity_series":
        return _run_entity_series(card, catalog=catalog, user_intent=user_intent)
    if kind == "metric_groups":
        return _run_metric_groups(card, user_intent=user_intent)
    return _card_gap(card, f"未知卡类型 kind={kind!r}")


def render_analysis_dashboard(
    template_id: Annotated[
        str,
        "看板模板 id，默认 pcb_ops；资料包可放 dashboards/{id}.json 覆盖",
    ] = "pcb_ops",
    user_intent: Annotated[str, "用户原话，用于图表自动选型"] = "",
    max_cards: Annotated[int, "最多渲染卡数，默认 6"] = 6,
) -> dict:
    """按模板渲染多卡分析看板：能出图的出图，不能的标缺口。禁止编造。"""
    # analysis.json 可指定默认模板
    tid = (template_id or "").strip() or "pcb_ops"
    try:
        from tools.query_tool.analysis_config import load_analysis_config

        acfg = load_analysis_config()
        if tid in ("auto", "default", "") and acfg.get("dashboard_template"):
            tid = str(acfg.get("dashboard_template") or "pcb_ops")
    except Exception:
        pass

    tmpl = load_dashboard_template(tid)
    if tmpl.get("error") and not tmpl.get("cards"):
        return {
            "error": tmpl["error"],
            "hint": "可在资料包 dashboards/ 放置模板，或使用内置 pcb_ops。",
        }

    catalog = load_catalog()
    if not catalog:
        return {
            "error": "当前未配置可查对象，请先在系统配置接入 MES。",
            "gaps": [
                {
                    "id": "catalog",
                    "title": "资料包",
                    "status": "gap",
                    "reason": "entities 目录为空",
                }
            ],
        }

    n = max(1, min(int(max_cards or 6), _MAX_CARDS))
    cards_in = [c for c in (tmpl.get("cards") or []) if isinstance(c, dict)][:n]
    results: list[dict[str, Any]] = []
    charts: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    for card in cards_in:
        try:
            one = _run_card(card, catalog=catalog, user_intent=user_intent)
        except Exception as e:  # noqa: BLE001 — 单卡隔离，勿拖垮整板
            one = _card_gap(card, f"卡执行异常：{type(e).__name__}: {e}")
        results.append(one)
        if one.get("status") == "ok" and isinstance(one.get("chart_option"), dict):
            charts.append(
                {
                    "id": one.get("id"),
                    "title": one.get("title"),
                    "chart_type": one.get("chart_type"),
                    "chart_option": one.get("chart_option"),
                    "definition": one.get("definition") or "",
                    "caveats": (one.get("caveats") or [])[:5],
                    "layout": one.get("layout") or {},
                    "drill": one.get("drill") if isinstance(one.get("drill"), dict) else None,
                    "entity": one.get("entity"),
                }
            )
        elif one.get("status") == "gap":
            gaps.append(one)

    # 运营大屏 KPI：图表汇总 + 可选口径（失败跳过）
    pres = tmpl.get("presentation") if isinstance(tmpl.get("presentation"), dict) else {}
    kpi_specs = pres.get("kpi") if isinstance(pres.get("kpi"), list) else None
    kpis = build_kpis_from_charts(charts, specs=kpi_specs)
    # 未完工：插到最前（有则）；且不得小于同屏「急单」图合计（逻辑护栏）
    if pres.get("lead_metric"):
        lead = try_metric_kpi(
            str(pres.get("lead_metric")),
            label=str(pres.get("lead_label") or "未完工"),
        )
        if lead:
            urgent_kpi = next(
                (k for k in kpis if str(k.get("chart_id") or "") == "K2" or k.get("id") == "urgent"),
                None,
            )
            try:
                urgent_n = float((urgent_kpi or {}).get("raw") or 0)
                lead_n = float(lead.get("raw") or 0)
            except (TypeError, ValueError):
                urgent_n, lead_n = 0.0, 0.0
            if urgent_n > 0 and lead_n + 1e-6 < urgent_n:
                # 截断/口径不一致时：用急单合计兜底并标明，避免领导看到未完工<急单
                lead = {
                    **lead,
                    "value": str(int(round(urgent_n))),
                    "raw": urgent_n,
                    "hint": (
                        f"{lead.get('hint') or '未完工'}；"
                        f"口径拉取偏少，已与急单图合计 {int(urgent_n)} 对齐（勿当全库）"
                    ),
                    "source": "chart_guard",
                }
            kpis = [lead] + [k for k in kpis if k.get("id") != lead.get("id")]
    kpis = kpis[:5]
    skin = str(pres.get("skin") or "ops_dark").strip() or "ops_dark"
    if skin not in ("ops_dark", "ops_light", "default"):
        skin = "ops_dark"

    lines = [
        f"## {tmpl.get('label') or tid}",
        "",
        f"- 模板：`{tid}`（{tmpl.get('_source') or ''}）",
        f"- 成功出图：{len(charts)} / 缺口：{len(gaps)}",
        "",
    ]
    for c in results:
        if c.get("status") == "ok":
            lines.append(
                f"- ✅ **{c.get('title')}**：{c.get('chart_type')}，{c.get('point_count')} 点"
                + (f"（`{c.get('entity')}`）" if c.get("entity") else "")
            )
        else:
            lines.append(f"- ⚠ **{c.get('title')}**：{c.get('reason')}")

    first = charts[0] if charts else None
    return {
        "ok": True,
        "template_id": tid,
        "label": tmpl.get("label") or tid,
        "source": tmpl.get("_source"),
        "presentation": True,
        "skin": skin,
        "kpis": kpis,
        "cards": results,
        "charts": charts,
        "gaps": gaps,
        "chart_count": len(charts),
        "gap_count": len(gaps),
        # 兼容单图 SSE：首张成功图
        "chart_option": (first or {}).get("chart_option"),
        "title": (first or {}).get("title") or tmpl.get("label"),
        "chart_type": (first or {}).get("chart_type"),
        "definition": (first or {}).get("definition") or "",
        "caveats": (first or {}).get("caveats") or [],
        "layout": (first or {}).get("layout") or {},
        "markdown_report": "\n".join(lines),
        "reply_hint": (
            "展示运营大屏（KPI+多图）；可提示用户点击扇区/柱查看下钻明细。"
            "缺口项照实告知；禁止编造工序在制或 Lot。不要追问用户用什么图。"
        ),
    }
