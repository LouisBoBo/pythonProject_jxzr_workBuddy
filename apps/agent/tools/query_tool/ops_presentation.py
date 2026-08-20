"""运营看板 KPI / 下钻辅助：只从已成功图表或口径真数汇总，禁止编造。"""
from __future__ import annotations

from typing import Any


def series_from_chart_option(option: dict[str, Any] | None) -> tuple[list[str], list[float]]:
    if not isinstance(option, dict):
        return [], []
    series = option.get("series")
    if not isinstance(series, list) or not series:
        return [], []
    s0 = next((s for s in series if isinstance(s, dict)), None)
    if not s0:
        return [], []
    data = s0.get("data")
    cats: list[str] = []
    vals: list[float] = []
    if isinstance(data, list) and data and isinstance(data[0], dict):
        for d in data:
            if not isinstance(d, dict):
                continue
            cats.append(str(d.get("name") or ""))
            try:
                vals.append(float(d.get("value") or 0))
            except (TypeError, ValueError):
                vals.append(0.0)
        return cats, vals
    # bar/line: categories on axis
    x = option.get("xAxis")
    y = option.get("yAxis")
    axis_data = None
    if isinstance(x, dict) and x.get("type") == "category":
        axis_data = x.get("data")
    elif isinstance(y, dict) and y.get("type") == "category":
        axis_data = y.get("data")
    elif isinstance(x, list) and x and isinstance(x[0], dict):
        axis_data = x[0].get("data")
    if isinstance(axis_data, list):
        cats = [str(c) for c in axis_data]
    if isinstance(data, list):
        for v in data:
            try:
                vals.append(float(v if not isinstance(v, dict) else v.get("value") or 0))
            except (TypeError, ValueError):
                vals.append(0.0)
    if cats and vals and len(cats) != len(vals):
        n = min(len(cats), len(vals))
        return cats[:n], vals[:n]
    return cats, vals


def _fmt_num(v: float, *, unit: str = "") -> str:
    if unit == "%":
        return f"{v:.2f}".rstrip("0").rstrip(".")
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _agg(vals: list[float], how: str) -> float | None:
    if not vals:
        return None
    how = (how or "sum").lower()
    if how == "avg":
        return sum(vals) / len(vals)
    if how == "max":
        return max(vals)
    if how == "min":
        return min(vals)
    if how == "count":
        return float(len(vals))
    return float(sum(vals))


def build_kpis_from_charts(
    charts: list[dict[str, Any]],
    *,
    specs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """按模板 presentation.kpi 从已出图 series 汇总；缺图则跳过该项。"""
    by_id = {
        str(c.get("id") or ""): c
        for c in charts
        if isinstance(c, dict) and c.get("id")
    }
    default_specs = [
        {
            "id": "urgent",
            "label": "急单",
            "chart_id": "K2",
            "agg": "sum",
            "unit": "",
            "hint": "急单堆积合计",
        },
        {
            "id": "defect_top",
            "label": "不良 Top 合计",
            "chart_id": "K4",
            "agg": "sum",
            "unit": "",
            "hint": "不良 Top 图合计",
        },
        {
            "id": "yield_avg",
            "label": "均良率",
            "chart_id": "K5",
            "agg": "avg",
            "unit": "%",
            "hint": "工序良率均值",
        },
        {
            "id": "output",
            "label": "产出合计",
            "chart_id": "K3",
            "agg": "sum",
            "unit": "",
            "hint": "日产出概览合计",
        },
    ]
    use_specs = specs if isinstance(specs, list) and specs else default_specs
    out: list[dict[str, Any]] = []
    for spec in use_specs:
        if not isinstance(spec, dict):
            continue
        cid = str(spec.get("chart_id") or "").strip()
        ch = by_id.get(cid)
        if not ch:
            continue
        opt = ch.get("chart_option") or ch.get("option")
        _cats, vals = series_from_chart_option(opt if isinstance(opt, dict) else None)
        num = _agg(vals, str(spec.get("agg") or "sum"))
        if num is None:
            continue
        unit = str(spec.get("unit") or "")
        out.append(
            {
                "id": str(spec.get("id") or cid),
                "label": str(spec.get("label") or ch.get("title") or cid),
                "value": _fmt_num(num, unit=unit),
                "raw": round(num, 4),
                "unit": unit,
                "hint": str(spec.get("hint") or ch.get("title") or ""),
                "chart_id": cid,
                "source": "chart",
            }
        )
    return out[:6]


def try_metric_kpi(metric: str, *, label: str, unit: str = "") -> dict[str, Any] | None:
    """可选：从口径取 KPI 条数；失败返回 None，不抛。

    注意：须用足够大的 limit，否则 multi-filter 合并后 total=len(merged)
    会被截断（曾出现未完工=10 < 急单=23 的矛盾）。
    """
    mid = str(metric or "").strip()
    if not mid:
        return None
    try:
        from tools.query_tool.platform_query import query_metric

        # 100：与看板卡一致量级；仅取条数不展示明细
        out = query_metric(mid, limit=100)
    except Exception:
        return None
    if not isinstance(out, dict) or out.get("error"):
        return None
    total = out.get("total")
    if not isinstance(total, int):
        total = out.get("returned")
    if not isinstance(total, int):
        records = out.get("records")
        total = len(records) if isinstance(records, list) else None
    if total is None:
        return None
    # 逻辑护栏：若同屏已有更大真数，调用方负责；此处只保证本口径尽量拉全
    hint = str(out.get("metric_label") or out.get("definition") or mid)[:120]
    caveats = out.get("caveats") if isinstance(out.get("caveats"), list) else []
    if caveats:
        hint = f"{hint}；" + "；".join(str(c) for c in caveats[:2])
    return {
        "id": f"metric:{mid}",
        "label": label,
        "value": str(total),
        "raw": float(total),
        "unit": unit,
        "hint": hint,
        "metric": mid,
        "source": "metric",
    }


def compact_drill_rows(
    records: list[Any],
    *,
    limit: int = 40,
    group_field: str | None = None,
) -> list[dict[str, str]]:
    """下钻用精简行：优先中文展示行，否则原字段截断。"""
    try:
        from tools.query_tool.value_labels import label_enum_value
    except Exception:
        label_enum_value = None  # type: ignore[assignment]

    rows: list[dict[str, str]] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        # 已是展示行（中文表头）
        sample_keys = [str(k) for k in list(rec.keys())[:8]]
        if any("\u4e00" <= ch <= "\u9fff" for k in sample_keys for ch in k):
            row = {str(k): str(v)[:80] if v is not None else "" for k, v in list(rec.items())[:10]}
        else:
            row = {}
            for k, v in list(rec.items())[:10]:
                if str(k).startswith("_"):
                    continue
                row[str(k)] = str(v)[:80] if v is not None else ""
        if group_field and group_field in rec:
            raw_g = rec.get(group_field)
            if label_enum_value:
                labeled = label_enum_value(group_field, raw_g)
                row["_group"] = labeled or (str(raw_g) if raw_g is not None else "")
            else:
                row["_group"] = str(raw_g) if raw_g is not None else ""
        rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def build_drill_payload(
    *,
    card_id: str,
    title: str,
    group_field: str | None,
    categories: list[str],
    values: list[float],
    records: list[Any] | None = None,
    display_rows: list[Any] | None = None,
    entity: str | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    if isinstance(display_rows, list) and display_rows:
        rows = compact_drill_rows(display_rows, group_field=group_field)
    elif isinstance(records, list) and records:
        rows = compact_drill_rows(records, group_field=group_field)
    return {
        "enabled": True,
        "card_id": card_id,
        "title": title,
        "group_field": group_field or "",
        "categories": categories[:40],
        "values": values[:40],
        "entity": entity or "",
        "rows": rows,
        "hint": "点击图上类目查看明细；无明细时可对话追问。",
    }
