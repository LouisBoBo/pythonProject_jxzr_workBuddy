"""分析图表：把已取回的分组/指标 series 建成 ECharts option（不直连 MES DB）。

柱/折/饼均自适应布局防堆叠；可选 ANALYSIS_CHART_MCP=1 走 MCP 渲染。
图表类型：用户点名 > 意图自动推断（趋势→折线、分布→饼、默认柱）> 入参。
"""
from __future__ import annotations

import json
import os
import re
from typing import Annotated, Any

_MAX_POINTS = 40
_ALLOWED_TYPES = frozenset({"bar", "line", "pie"})
_PIE_TOP_N = 8
_CART_HORIZONTAL_N = 8
_CART_HORIZONTAL_LEN = 8
_CART_ZOOM_N = 12
_LABEL_SHOW_MAX = 10

# 用户点名图表类型（最高优先级）
_EXPLICIT_CHART_PATTERNS: tuple[tuple[str, str], ...] = (
    ("pie", r"(饼图|饼状图|环形图|圆环图|\bpie\b|\bdonut\b)"),
    ("line", r"(折线图|折线|曲线图|趋势图|\bline\s*chart\b)"),
    ("bar", r"(柱状图|柱形图|条形图|棒状图|\bbar\s*chart\b)"),
)
# 意图推断（未点名时）
_INTENT_LINE = re.compile(
    r"(趋势|走势|变化|环比|同比|按日|按周|按月|随时间|时间序列|增长|下降)",
)
_INTENT_PIE = re.compile(
    r"(分布|占比|构成|比例|份额|比重|结构|各占)",
)


def _detect_explicit_chart_type(text: str) -> str | None:
    s = (text or "").strip()
    if not s:
        return None
    # 按出现位置取最先点名的类型，避免「不要用饼图用柱状」误判时偏后词仍可能赢——
    # 简单策略：找所有匹配，取 earliest start；冲突时 bar/line/pie 按用户字面优先最早者
    best: tuple[int, str] | None = None
    for ctype, pat in _EXPLICIT_CHART_PATTERNS:
        m = re.search(pat, s, flags=re.IGNORECASE)
        if not m:
            continue
        pos = m.start()
        if best is None or pos < best[0]:
            best = (pos, ctype)
    return best[1] if best else None


def infer_chart_type(
    *,
    chart_type: str = "auto",
    user_intent: str = "",
    title: str = "",
    definition: str = "",
    source_note: str = "",
) -> tuple[str, list[str]]:
    """解析图表类型。优先级：用户点名 > 意图推断 > 工具入参 bar/line/pie > 默认柱状。

    禁止依赖用户二次确认「用什么图」。
    """
    notes: list[str] = []
    explicit = _detect_explicit_chart_type(user_intent)
    if explicit:
        return explicit, notes

    blob = " ".join(
        x for x in (user_intent, title, definition, source_note) if (x or "").strip()
    )
    if _INTENT_LINE.search(blob):
        notes.append("已按意图选用折线图（趋势/走势类）")
        return "line", notes
    if _INTENT_PIE.search(blob):
        notes.append("已按意图选用饼图（分布/占比类）")
        return "pie", notes

    ct = (chart_type or "").strip().lower()
    if ct in _ALLOWED_TYPES:
        return ct, notes
    if ct and ct not in ("auto", "default", ""):
        notes.append(f"未知 chart_type={ct!r}，已改用柱状图")
    return "bar", notes


def _clip_series(
    categories: list[Any],
    values: list[Any],
) -> tuple[list[str], list[float], list[str]]:
    cats: list[str] = []
    vals: list[float] = []
    caveats: list[str] = []
    n = min(len(categories), len(values), _MAX_POINTS)
    if len(categories) > _MAX_POINTS or len(values) > _MAX_POINTS:
        caveats.append(f"系列超过 {_MAX_POINTS} 点，已截断展示")
    for i in range(n):
        cats.append(str(categories[i] if categories[i] is not None else "")[:80] or "(空)")
        try:
            vals.append(float(values[i]))
        except (TypeError, ValueError):
            vals.append(0.0)
    return cats, vals, caveats


def _pie_aggregate_top_n(
    cats: list[str], vals: list[float], *, top_n: int = _PIE_TOP_N
) -> tuple[list[str], list[float], list[str]]:
    caveats: list[str] = []
    if len(cats) <= top_n:
        return cats, vals, caveats
    paired = sorted(zip(cats, vals, strict=False), key=lambda x: x[1], reverse=True)
    keep, rest = paired[:top_n], paired[top_n:]
    other = sum(v for _, v in rest)
    out_c = [c for c, _ in keep]
    out_v = [v for _, v in keep]
    if other > 0 or rest:
        out_c.append("其他")
        out_v.append(float(other))
        caveats.append(
            f"类目共 {len(cats)} 项，图中展示 Top{top_n}，其余 {len(rest)} 项合并为「其他」"
        )
    return out_c, out_v, caveats


def _pie_label_width(cats: list[str]) -> int:
    max_len = max((len(c) for c in cats), default=0)
    if max_len >= 16:
        return 120
    if max_len >= 10:
        return 100
    return 80


def _build_pie_option(*, title_s: str, name: str, cats: list[str], vals: list[float]) -> dict[str, Any]:
    """饼图：TopN 后每扇区均用引线标注完整名称 + 百分比（防堆叠靠缩小半径 + avoidLabelOverlap）。"""
    n = len(cats)
    dense = n >= 6
    label_w = _pie_label_width(cats)
    # 多扇区时缩小环、居中，给左右引线留位；图例收到底部滚动作对照
    if dense:
        center, radius = ["50%", "48%"], ["28%", "48%"]
        height_hint = 520
        legend: dict[str, Any] = {
            "type": "scroll",
            "orient": "horizontal",
            "bottom": 2,
            "left": "center",
            "width": "94%",
            "itemWidth": 10,
            "itemHeight": 10,
            "textStyle": {"fontSize": 10},
            "pageIconSize": 10,
        }
        label_line = {
            "show": True,
            "length": 14,
            "length2": 12,
            "smooth": 0.2,
        }
    else:
        center, radius = ["50%", "52%"], ["34%", "58%"]
        height_hint = 400
        legend = {"show": False}
        label_line = {
            "show": True,
            "length": 12,
            "length2": 10,
            "smooth": 0.2,
        }

    label = {
        "show": True,
        "formatter": "{b}\n{d}%",
        "fontSize": 11 if not dense else 10,
        "lineHeight": 14,
        "overflow": "truncate",
        "width": label_w,
        "ellipsis": "…",
        "alignTo": "labelLine",
        "bleedMargin": 4,
        "distanceToLabelLine": 4,
    }

    return {
        "title": {"text": title_s, "left": "center", "top": 4, "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "item", "formatter": "{b}<br/>{c}（{d}%）"},
        "legend": legend,
        "series": [
            {
                "name": name,
                "type": "pie",
                "radius": radius,
                "center": center,
                "avoidLabelOverlap": True,
                "minShowLabelAngle": 2,
                "stillShowZeroSum": False,
                "data": [{"name": c, "value": v} for c, v in zip(cats, vals, strict=False)],
                "label": label,
                "labelLayout": {"hideOverlap": False, "moveOverlap": "shiftY"},
                "labelLine": label_line,
                "emphasis": {
                    "label": {
                        "show": True,
                        "fontSize": 12,
                        "fontWeight": "bold",
                        "width": label_w + 20,
                        "overflow": "none",
                    },
                    "labelLine": {"show": True},
                    "itemStyle": {
                        "shadowBlur": 8,
                        "shadowOffsetX": 0,
                        "shadowColor": "rgba(0,0,0,0.2)",
                    },
                },
            }
        ],
        "_wb_layout": {
            "mode": "pie_labeled" if dense else "pie",
            "height_hint": height_hint,
            "category_count": n,
        },
    }


def _axis_label_truncate(max_len: int) -> dict[str, Any]:
    width = 88 if max_len >= 12 else (72 if max_len >= 8 else 56)
    return {
        "interval": 0,
        "fontSize": 11,
        "hideOverlap": True,
        "overflow": "truncate",
        "width": width,
        "ellipsis": "…",
    }


_LINE_GREEN = "#3ecf8e"
_LINE_AREA_STOPS = (
    {"offset": 0, "color": "rgba(62, 207, 142, 0.42)"},
    {"offset": 1, "color": "rgba(62, 207, 142, 0.04)"},
)


def _line_area_series(*, name: str, vals: list[float], show_value_label: bool) -> dict[str, Any]:
    """折线 + 下方阴影区域（面积图），对齐运营看板良率样式。"""
    return {
        "name": name,
        "type": "line",
        "data": vals,
        "smooth": True,
        "symbol": "circle",
        "symbolSize": 8,
        "showSymbol": True,
        "lineStyle": {"width": 3, "color": _LINE_GREEN},
        "itemStyle": {
            "color": "#ffffff",
            "borderColor": _LINE_GREEN,
            "borderWidth": 2,
        },
        "areaStyle": {
            "color": {
                "type": "linear",
                "x": 0,
                "y": 0,
                "x2": 0,
                "y2": 1,
                "colorStops": list(_LINE_AREA_STOPS),
            }
        },
        "label": {
            "show": show_value_label,
            "position": "top",
            "fontSize": 11,
            "color": "#374151",
        },
        "emphasis": {
            "focus": "series",
            "itemStyle": {
                "color": _LINE_GREEN,
                "borderColor": "#ffffff",
                "borderWidth": 2,
            },
        },
    }


def _yield_like_axis(vals: list[float]) -> dict[str, Any]:
    """良率类数据：0～100 刻度，便于对照参考图。"""
    if not vals:
        return {"type": "value", "minInterval": 1, "splitNumber": 4}
    try:
        lo = min(vals)
        hi = max(vals)
    except TypeError:
        return {"type": "value", "minInterval": 1, "splitNumber": 4}
    # 百分数良率（常见 80～100）
    if 0 <= lo and hi <= 100 and hi >= 50:
        return {
            "type": "value",
            "min": 0,
            "max": 100,
            "splitNumber": 5,
            "axisLabel": {"formatter": "{value}"},
        }
    return {"type": "value", "minInterval": 1, "splitNumber": 4}


def _build_bar_line_option(
    *,
    ctype: str,
    title_s: str,
    name: str,
    cats: list[str],
    vals: list[float],
) -> dict[str, Any]:
    n = len(cats)
    max_len = max((len(c) for c in cats), default=0)
    use_horizontal = ctype == "bar" and (
        n >= _CART_HORIZONTAL_N or max_len >= _CART_HORIZONTAL_LEN
    )
    show_value_label = n <= _LABEL_SHOW_MAX
    need_zoom = n >= _CART_ZOOM_N
    title = {"text": title_s, "left": "center", "top": 4, "textStyle": {"fontSize": 14}}
    tooltip = {
        "trigger": "axis",
        "axisPointer": {"type": "shadow" if ctype == "bar" else "line"},
    }

    if use_horizontal:
        height_hint = min(720, max(360, 48 + n * 28))
        option: dict[str, Any] = {
            "title": title,
            "tooltip": tooltip,
            "grid": {
                "left": "4%",
                "right": "10%" if show_value_label else "6%",
                "top": "14%",
                "bottom": "12%" if need_zoom else "6%",
                "containLabel": True,
            },
            "xAxis": {"type": "value", "minInterval": 1, "splitNumber": 4},
            "yAxis": {
                "type": "category",
                "data": cats,
                "inverse": True,
                "axisTick": {"alignWithLabel": True},
                "axisLabel": {**_axis_label_truncate(max_len), "margin": 10},
            },
            "series": [
                {
                    "name": name,
                    "type": ctype,
                    "data": vals,
                    "barMaxWidth": 22,
                    "barCategoryGap": "35%",
                    "label": {"show": show_value_label, "position": "right", "fontSize": 11},
                }
            ],
            "_wb_layout": {
                "mode": "horizontal",
                "height_hint": height_hint,
                "category_count": n,
            },
        }
        if need_zoom:
            option["dataZoom"] = [
                {
                    "type": "slider",
                    "yAxisIndex": 0,
                    "width": 14,
                    "right": 4,
                    "start": 0,
                    "end": max(12.0, 100.0 * min(12, n) / n),
                    "brushSelect": False,
                },
                {
                    "type": "inside",
                    "yAxisIndex": 0,
                    "zoomOnMouseWheel": False,
                    "moveOnMouseWheel": True,
                },
            ]
        return option

    need_tilt = max_len >= 6 or n >= 4
    rotate = 45 if (need_tilt and max_len >= 8) else (35 if need_tilt else 0)
    bottom = "28%" if need_zoom else ("24%" if rotate >= 40 else ("16%" if rotate else "10%"))
    if ctype == "line":
        series = [_line_area_series(name=name, vals=vals, show_value_label=show_value_label)]
        y_axis: dict[str, Any] = _yield_like_axis(vals)
    else:
        series = [
            {
                "name": name,
                "type": ctype,
                "data": vals,
                "smooth": False,
                "barMaxWidth": 48 if n <= 8 else 36,
                "barCategoryGap": "42%" if n <= 6 else "28%",
                "label": {
                    "show": show_value_label and ctype == "bar",
                    "position": "top",
                    "fontSize": 11,
                },
            }
        ]
        y_axis = {"type": "value", "minInterval": 1, "splitNumber": 4}
    option = {
        "title": title,
        "tooltip": tooltip,
        "grid": {
            "left": "8%",
            "right": "6%",
            "top": "16%",
            "bottom": bottom,
            "containLabel": True,
        },
        "xAxis": {
            "type": "category",
            "boundaryGap": ctype != "line",
            "data": cats,
            "axisTick": {"alignWithLabel": True},
            "axisLabel": {
                **_axis_label_truncate(max_len),
                "rotate": rotate,
                "margin": 14,
                "hideOverlap": True,
            },
        },
        "yAxis": y_axis,
        "series": series,
        "_wb_layout": {
            "mode": "vertical",
            "height_hint": 400 if need_zoom or rotate else 360,
            "category_count": n,
            "area": ctype == "line",
        },
    }
    if need_zoom:
        end_pct = max(18.0, 100.0 * min(10, n) / n)
        option["dataZoom"] = [
            {
                "type": "slider",
                "xAxisIndex": 0,
                "height": 18,
                "bottom": 6,
                "start": 0,
                "end": end_pct,
                "brushSelect": False,
            },
            {"type": "inside", "xAxisIndex": 0},
        ]
    return option


def build_echarts_option(
    *,
    chart_type: str,
    title: str,
    categories: list[Any],
    values: list[Any],
    series_name: str = "数量",
    user_intent: str = "",
    definition: str = "",
    source_note: str = "",
) -> dict[str, Any]:
    ctype, type_notes = infer_chart_type(
        chart_type=chart_type,
        user_intent=user_intent,
        title=title,
        definition=definition,
        source_note=source_note,
    )
    cats, vals, caveats = _clip_series(categories, values)
    caveats.extend(type_notes)
    title_s = (title or "分析图").strip()[:120] or "分析图"
    name = (series_name or "数量").strip()[:40] or "数量"

    if ctype == "pie":
        cats, vals, extra = _pie_aggregate_top_n(cats, vals)
        caveats.extend(extra)
        option = _build_pie_option(title_s=title_s, name=name, cats=cats, vals=vals)
    else:
        option = _build_bar_line_option(
            ctype=ctype, title_s=title_s, name=name, cats=cats, vals=vals
        )
        layout = option.get("_wb_layout") or {}
        if layout.get("mode") == "horizontal":
            caveats.append("类目较多或名称较长，已自动改为横向柱图以防堆叠")
        elif int(layout.get("category_count") or 0) >= _CART_ZOOM_N:
            caveats.append("类目较多，可拖动滑块查看全部")

    return {
        "option": option,
        "chart_type": ctype,
        "title": title_s,
        "categories": cats,
        "values": vals,
        "point_count": len(cats),
        "caveats": caveats,
        "layout": option.get("_wb_layout") or {},
    }


def series_from_groups(groups: list[Any] | None) -> tuple[list[str], list[float]]:
    cats: list[str] = []
    vals: list[float] = []
    for g in groups or []:
        if not isinstance(g, dict):
            continue
        cats.append(str(g.get("value") if g.get("value") is not None else g.get("name") or ""))
        try:
            vals.append(
                float(g.get("count") if g.get("count") is not None else g.get("value_num") or 0)
            )
        except (TypeError, ValueError):
            vals.append(0.0)
    return cats, vals


def _try_mcp_render(payload: dict[str, Any]) -> dict[str, Any] | None:
    if os.getenv("ANALYSIS_CHART_MCP", "").lower() not in ("1", "true", "yes"):
        return None
    try:
        from tools.query_tool.chart_mcp_client import call_chart_mcp

        return call_chart_mcp("render_chart", payload)
    except Exception as e:  # noqa: BLE001
        return {"_mcp_error": f"{type(e).__name__}: {e}"}


def render_analysis_chart(
    chart_type: Annotated[
        str,
        "图表类型：auto（推荐，按意图自动选）/ bar / line / pie。"
        "选型规则：用户点名最高优先；趋势/走势→line；分布/占比→pie；其余→bar。"
        "**禁止**向用户追问用什么图。",
    ] = "auto",
    title: Annotated[str, "图表标题（中文）"] = "分析图",
    categories: Annotated[
        list[str] | str | None,
        "类目轴：字符串列表，或 JSON 数组字符串。须来自已取数结果，禁止臆造",
    ] = None,
    values: Annotated[
        list[float | int] | str | None,
        "数值列表，与 categories 一一对应；或 JSON 数组字符串",
    ] = None,
    groups: Annotated[
        list[dict] | str | None,
        "可选：直接传 summarize/brief 的 groups（含 value/count），与 categories/values 二选一",
    ] = None,
    series_name: Annotated[str, "系列名称，默认「数量」"] = "数量",
    definition: Annotated[str, "口径说明（会展示给用户）"] = "",
    source_note: Annotated[str, "数据来源说明，如「本页 12 条按状态汇总，非全库」"] = "",
    user_intent: Annotated[
        str,
        "用户原话（强烈建议传入）：用于自动选型；用户点名图表类型时以此为准",
    ] = "",
) -> dict:
    """根据已取回的分组/指标 series 生成 ECharts option，供对话内出图。

    图表类型由意图自动决定，勿向用户询问用柱/折/饼。
    """

    def _parse_list(raw: Any) -> list[Any]:
        if raw is None:
            return []
        if isinstance(raw, list):
            return raw
        if isinstance(raw, str):
            s = raw.strip()
            if not s:
                return []
            try:
                parsed = json.loads(s)
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return [x.strip() for x in s.split(",") if x.strip()]
        return []

    caveats: list[str] = []
    cats: list[Any] = []
    vals: list[Any] = []

    g_raw = groups
    if isinstance(g_raw, str) and g_raw.strip():
        try:
            g_raw = json.loads(g_raw)
        except json.JSONDecodeError:
            g_raw = None
    if isinstance(g_raw, list) and g_raw:
        cats, vals = series_from_groups(g_raw)
    else:
        cats = _parse_list(categories)
        vals = _parse_list(values)

    if not cats or not vals:
        return {
            "error": "缺少 categories/values 或 groups。请先查数/汇总，再把真实分组传入。",
            "hint": "示例：先 summarize_platform_data，再 render_analysis_chart(groups=返回的 groups, user_intent=用户原话)。",
        }
    if len(cats) != len(vals):
        m = min(len(cats), len(vals))
        cats, vals = cats[:m], vals[:m]
        caveats.append("类目与数值长度不一致，已按较短一侧截齐")

    built = build_echarts_option(
        chart_type=chart_type,
        title=title,
        categories=cats,
        values=vals,
        series_name=series_name,
        user_intent=user_intent,
        definition=definition,
        source_note=source_note,
    )
    caveats.extend(built.get("caveats") or [])
    if source_note.strip():
        caveats.append(source_note.strip()[:200])

    option = built["option"]
    mcp_meta: dict[str, Any] = {}
    mcp_out = _try_mcp_render(
        {
            "chart_type": built["chart_type"],
            "title": built["title"],
            "categories": built["categories"],
            "values": built["values"],
            "series_name": series_name,
        }
    )
    if isinstance(mcp_out, dict) and mcp_out.get("option"):
        option = mcp_out["option"]
        mcp_meta["mcp"] = True
        mcp_meta["mcp_tool"] = mcp_out.get("mcp_tool") or "render_chart"
    elif isinstance(mcp_out, dict) and mcp_out.get("_mcp_error"):
        mcp_meta["mcp"] = False
        mcp_meta["mcp_fallback"] = str(mcp_out["_mcp_error"])[:200]
        caveats.append("MCP 图表服务不可用，已用本地渲染")

    fence_payload = {
        "chart_type": built["chart_type"],
        "title": built["title"],
        "option": option,
        "definition": (definition or "").strip()[:300],
        "caveats": caveats[:5],
        "layout": built.get("layout") or option.get("_wb_layout") or {},
    }
    fence = ":::analysis_chart\n" + json.dumps(fence_payload, ensure_ascii=False) + "\n:::"

    return {
        "ok": True,
        "chart_type": built["chart_type"],
        "title": built["title"],
        "chart_option": option,
        "categories": built["categories"],
        "values": built["values"],
        "point_count": built["point_count"],
        "definition": (definition or "").strip()[:300],
        "caveats": caveats,
        "layout": built.get("layout") or {},
        "markdown_fence": fence,
        "reply_hint": (
            "前端会通过工具结果自动出图。"
            "回复只写：结论（各组条数/占比）+ 口径/caveats；"
            "**不要**再贴 markdown_fence / :::analysis_chart，**不要**再贴一整份与图相同的分组表（避免数据重复）。"
            "**不要**询问用户用柱状/折线/饼图；类型已按意图自动选定。"
            "禁止编造未出现在 categories/values 中的数。"
        ),
        **mcp_meta,
    }
