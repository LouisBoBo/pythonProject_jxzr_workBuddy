"""
平台查询工具：封装平台数据查询操作，供 Agent 调用。
"""
from typing import Annotated

from tools.query_tool.entity_catalog import catalog_summary, get_entity, load_catalog
from tools.query_tool.metrics_pack import bind_metric, find_metric, load_metrics_pack
from tools.query_tool.query_present import (
    field_label_map,
    present_query_result,
    resolve_group_by,
    summarize_records,
)
from tools.platform_api import get_client


def list_platform_entities() -> dict:
    """列出平台中所有可用的数据实体（表/集合）。

    返回实体 id、中文名、别名、支持操作与目录字段概要（来自资料包，不逐实体打 MES）。
    需要样例数据或实时字段探测时，再调用 describe_entity(单个 entity)。
    """
    catalog = catalog_summary()
    details = []
    for row in catalog:
        details.append(
            {
                "entity": row["entity"],
                "label": row["label"],
                "aliases": row["aliases"],
                "ops": row["ops"],
                "filter_fields": row["fields"],
                "column_fields": row["columns"],
                "field_labels": row.get("field_labels") or {},
            }
        )

    return {
        "entities": [r["entity"] for r in catalog],
        "count": len(catalog),
        "details": details,
        "hint": (
            "调用 query/import/export 时 entity 必须用英文 id；字段以本目录为准。"
            "需要样例/实时字段或条数时，对单个实体调用 describe_entity，不要对本工具期望 record_count。"
        ),
    }


def query_platform_data(
    entity: Annotated[str, "实体英文 id（来自当前可查对象目录），也可用中文别名"],
    filters: Annotated[
        dict | None,
        "可选过滤条件，字段名以 describe_entity / 目录 fields 为准；会作为 API query 参数下发",
    ] = None,
    limit: Annotated[int, "返回记录上限，默认 50"] = 50,
) -> dict:
    """查询平台中指定实体的数据。

    带状态/优先级等条件时必须传 filters（会发给 MES 接口），不要全量拉取后口头过滤。
    成功时附带中文列名、display_rows、markdown_table，便于直接给用户看。
    """
    client = get_client()
    raw = client.query(entity, filters, limit)
    return present_query_result(raw, filters=filters, limit=limit)


def summarize_platform_data(
    entity: Annotated[str, "实体英文 id 或中文别名"],
    group_by: Annotated[
        str | None,
        "分组字段：英文名或中文说法（如 status / 状态）。不传则自动选状态/优先级等真实字段",
    ] = None,
    filters: Annotated[dict | None, "可选过滤条件，与 query_platform_data 相同，会发给 MES"] = None,
    limit: Annotated[int, "参与汇总的记录上限，默认 100（受接口分页限制）"] = 100,
) -> dict:
    """按字段分组计数。默认页内汇总并强制 caveat；若资料包实体声明了聚合接口则优先走服务端。

    不写死某一套 MES 字段名。不是数据库 COUNT(*)；无可靠全库聚合时比例只覆盖本页。
    """
    from tools.query_tool.aggregate import aggregate_by_field

    client = get_client()
    cap = max(1, min(int(limit or 100), 100))
    raw = client.query(entity, filters, cap)
    if isinstance(raw, dict) and "error" in raw:
        return raw
    records = raw.get("records") if isinstance(raw.get("records"), list) else []
    presented = present_query_result(raw, filters=filters, limit=cap)
    meta = get_entity(str(presented.get("entity") or entity))
    entity_meta = meta if isinstance(meta, dict) and "error" not in meta else None
    return aggregate_by_field(
        entity=str(entity),
        group_by=group_by,
        filters=filters,
        limit=cap,
        client=client,
        entity_meta=entity_meta,
        records=records if isinstance(records, list) else [],
        presented=presented if isinstance(presented, dict) else {},
    )


def describe_entity(
    entity: Annotated[str, "实体英文 id 或中文别名"],
) -> dict:
    """查看平台中某个实体的字段结构和样例数据。"""
    client = get_client()
    result = client.describe_entity(entity)
    # 补充目录中的别名与标注字段，方便 Agent 对照
    meta = get_entity(result.get("entity", entity)) if "error" not in result else get_entity(entity)
    if meta and "error" not in result:
        result["label"] = meta.get("label")
        result["aliases"] = meta.get("aliases") or []
        result["ops"] = meta.get("ops") or []
        result["filter_fields"] = _catalog_named_fields(meta.get("fields"))
        result["column_fields"] = _catalog_named_fields(meta.get("columns"))
        result["field_labels"] = field_label_map(str(result.get("entity") or entity), meta)
        result["filter_hint"] = (
            "query_platform_data 的 filters 请用 filter_fields 中的英文名；"
            "这些参数会发给 MES 接口，不要全量拉取后口头过滤。"
        )
    return result


def _catalog_named_fields(items: object) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(items, list):
        return out
    for item in items:
        if isinstance(item, dict) and item.get("name"):
            name = str(item["name"])
            out.append({"name": name, "label": str(item.get("label") or name)})
        elif isinstance(item, str) and item.strip():
            out.append({"name": item.strip(), "label": item.strip()})
    return out


def get_platform_summary(*, include_live_counts: bool = False) -> dict:
    """获取平台的概要信息：有哪些实体、各有多少数据。

    默认只读资料包目录（零 MES 请求）；include_live_counts=True 时对每个实体 describe（较慢）。
    """
    catalog = catalog_summary()
    summary = {}
    total_records = 0
    if include_live_counts:
        client = get_client()
        for row in catalog:
            eid = row["entity"]
            info = client.describe_entity(eid)
            count = info.get("record_count", 0) if "error" not in info else 0
            summary[eid] = {
                "label": row["label"],
                "aliases": row["aliases"],
                "record_count": count,
            }
            total_records += count
    else:
        for row in catalog:
            summary[row["entity"]] = {
                "label": row["label"],
                "aliases": row["aliases"],
            }
    out = {
        "entity_count": len(catalog),
        "breakdown": summary,
        "hint": (
            "breakdown 来自当前资料包目录。"
            + (
                "未探测各实体 record_count；对单个实体用 describe_entity 或 query_platform_data。"
                if not include_live_counts
                else ""
            )
        ),
    }
    if include_live_counts:
        out["total_records"] = total_records
    return out


def list_query_metrics() -> dict:
    """列出当前资料包能绑定的指标口径（在制 / 未完工 / 紧急未完工 / 当日完工等）。

    口径模板是通用的，实体与字段绑定当前可查对象目录；换平台后可在资料包放 metrics.json 覆盖。
    """
    pack = load_metrics_pack()
    catalog = load_catalog()
    items = []
    for m in pack.get("metrics") or []:
        if m.get("explicit_gap"):
            items.append(
                {
                    "id": m.get("id"),
                    "label": m.get("label"),
                    "aliases": m.get("aliases") or [],
                    "definition": m.get("definition") or "",
                    "bindable": False,
                    "status": "gap",
                    "entity": None,
                    "entity_label": None,
                    "reason": m.get("gap_reason") or m.get("definition") or "已知缺口",
                    "caveats": m.get("always_caveats") or [],
                }
            )
            continue
        bound = bind_metric(m, catalog=catalog, observed={})
        items.append(
            {
                "id": m.get("id"),
                "label": m.get("label"),
                "aliases": m.get("aliases") or [],
                "definition": m.get("definition") or "",
                "bindable": "error" not in bound,
                "status": bound.get("status") or ("ok" if "error" not in bound else "error"),
                "entity": bound.get("entity"),
                "entity_label": bound.get("entity_label"),
                "reason": bound.get("error"),
                "caveats": bound.get("caveats") or [],
            }
        )
    return {
        "count": len(items),
        "metrics": items,
        "hint": (
            "用户说在制/未完工/紧急单/当日完工/工序在制/Lot追溯时调用 query_metric。"
            "status=gap 或绑不上须如实说缺口；有 caveats 必须原样告知用户。"
            "禁止套用其它 MES 的实体 id；禁止编造 Lot/过站 WIP。"
        ),
    }


def query_metric(
    name: Annotated[str, "口径 id 或中文说法，如 wip / 在制 / 紧急未完工 / 当日完工"],
    extra_filters: Annotated[
        dict | None, "额外筛选（会与口径 filters 一并下发给 MES），字段名以当前目录为准"
    ] = None,
    limit: Annotated[int, "返回记录上限，默认 50"] = 50,
) -> dict:
    """按指标口径查数：先绑定当前目录的实体与真实枚举，再把 filters 发给 MES。"""
    metric = find_metric(name)
    if not metric:
        pack = load_metrics_pack()
        return {
            "error": f"未知口径：{name!r}",
            "available": [
                {"id": m.get("id"), "label": m.get("label"), "aliases": m.get("aliases") or []}
                for m in pack.get("metrics") or []
            ],
            "hint": "可先 list_query_metrics；或在资料包 metrics.json 增加口径。",
        }
    catalog = load_catalog()
    if not catalog:
        return {"error": "当前未配置可查对象，请先在系统配置接入 MES。"}

    client = get_client()
    probe_entity = bind_metric(metric, catalog=catalog, observed={}).get("entity")
    observed: dict[str, list[str]] = {}
    probe_fields: list[str] = []
    if probe_entity:
        probe = client.query(probe_entity, None, 50)
        recs = probe.get("records") if isinstance(probe, dict) else None
        if isinstance(recs, list):
            for rec in recs:
                if not isinstance(rec, dict):
                    continue
                for k, v in rec.items():
                    ks = str(k)
                    if ks not in probe_fields:
                        probe_fields.append(ks)
                    if v in (None, ""):
                        continue
                    bucket = observed.setdefault(ks, [])
                    sv = str(v)
                    if sv not in bucket:
                        bucket.append(sv)

    bound = bind_metric(
        metric,
        catalog=catalog,
        available_fields=probe_fields or None,
        observed=observed,
    )
    if "error" in bound:
        return bound

    merged: list[dict] = []
    seen: set[str] = set()
    calls: list[dict] = []
    api_totals: list[int] = []
    extra = {k: v for k, v in (extra_filters or {}).items() if v is not None and v != ""}
    fetch_cap = max(1, min(int(limit or 20), 100))
    for fs in bound.get("filter_sets") or []:
        filters = {**fs, **extra}
        raw = client.query(bound["entity"], filters, fetch_cap)
        calls.append({"filters": filters, "error": raw.get("error") if isinstance(raw, dict) else None})
        if not isinstance(raw, dict) or "error" in raw:
            continue
        if isinstance(raw.get("total"), int) and raw["total"] >= 0:
            api_totals.append(int(raw["total"]))
        for rec in raw.get("records") or []:
            if not isinstance(rec, dict):
                continue
            key = str(rec.get("id") or rec.get("order_no") or rec)
            if key in seen:
                continue
            seen.add(key)
            merged.append(rec)

    # total：优先「单次 API total」；多 filter 时用合并去重条数（避免相加重复计）
    if len(api_totals) == 1 and len(bound.get("filter_sets") or []) <= 1:
        total_n = api_totals[0]
    else:
        total_n = len(merged)
        # 若每一支路都报了 total 且只有一支，上面已覆盖；多支路用 merged
        if len(api_totals) == 1 and not merged:
            total_n = api_totals[0]

    presented = present_query_result(
        {"entity": bound["entity"], "total": total_n, "records": merged[:fetch_cap]},
        filters=None,
        limit=limit,
    )
    presented["filters_applied"] = extra
    presented["metric"] = bound.get("id")
    presented["metric_label"] = bound.get("label")
    presented["definition"] = bound.get("definition")
    presented["filter_sets"] = bound.get("filter_sets")
    presented["caveats"] = list(bound.get("caveats") or [])
    if len(bound.get("filter_sets") or []) > 1 and total_n == len(merged) and fetch_cap <= 20:
        presented["caveats"] = list(presented["caveats"]) + [
            f"口径条数按本次合并去重 {total_n} 计（多条件拉取，limit={fetch_cap}）；勿当未截断的全库总数"
        ]
    presented["api_calls"] = len(calls)
    if bound.get("measure"):
        presented["measure"] = bound["measure"]
    if bound.get("prefer_trend_tool"):
        presented["prefer_trend_tool"] = bound["prefer_trend_tool"]
    # 时间维：未能限定当日 → 禁止「今天完工了 N」
    date_unbound = any(
        ("未能限定当日" in str(c)) or ("日期筛选" in str(c) and "未能" in str(c))
        for c in (presented.get("caveats") or [])
    )
    presented["time_filter_applied"] = not date_unbound
    if date_unbound:
        presented["caveats"] = list(presented["caveats"]) + [
            "禁止把本次条数说成「今天/当日完工了 N 条」；只能说明已按其它条件查询并原样复述 caveats。"
        ]
    measure = bound.get("measure") if isinstance(bound.get("measure"), dict) else {}
    if measure.get("rate_mode") == "count_only":
        presented["caveats"] = list(presented["caveats"] or []) + list(measure.get("caveats") or [])
    caveats = presented.get("caveats") or []
    presented["reply_hint"] = (
        f"先复述口径「{bound.get('label')}」：{bound.get('definition')}；"
        f"查的是「{bound.get('entity_label')}」(`{bound.get('entity')}`)，"
        f"本次 {presented.get('returned')} 条。"
        "列出实际下发的 filter_sets；用 markdown_table / display_rows 展示。"
        "有 caveats 必须原样告诉用户（例如接口无日期筛参时不得说成「今天完工了 N 条」）。"
        "不要编造未返回的记录。"
    )
    if measure.get("rate_mode") == "count_only":
        presented["reply_hint"] += " measure.rate_mode=count_only：只报件数，禁止口算报废率/良率。"
    elif measure.get("rate_mode") == "ratio":
        presented["reply_hint"] += (
            f" 可用 `{measure.get('numerator_field')}` / `{measure.get('denominator_field')}` 算率，"
            "须同时展示分子分母。"
        )
    elif measure.get("rate_mode") == "rate_field":
        presented["reply_hint"] += f" 使用现成率字段 `{measure.get('rate_field')}`，勿另编。"
    if bound.get("prefer_trend_tool") == "analyze_time_trend":
        presented["reply_hint"] += (
            " 若用户要「最近N天/趋势」，优先改调 analyze_time_trend"
            "（time_field/value_field 见 measure hints）。"
        )
    if caveats:
        presented["reply_hint"] += " 本次 caveats：" + "；".join(str(c) for c in caveats[:3])
    if date_unbound:
        presented["reply_hint"] += " time_filter_applied=false：严禁「今天完工了 N」表述。"
    if any(c.get("error") for c in calls) and not merged:
        presented["error"] = "按口径请求 MES 失败"
        presented["call_errors"] = [c for c in calls if c.get("error")]
    return presented


def analyze_platform_brief(
    entity: Annotated[
        str | None,
        "实体英文 id 或中文别名；不传则按「生产工单/工单」等 hints 从当前目录解析",
    ] = None,
    limit: Annotated[int, "参与分析的记录上限，默认 100"] = 100,
    include_metrics: Annotated[
        bool, "是否附带当前目录可绑定的指标口径条数（在制/紧急未完工等），默认 true"
    ] = True,
) -> dict:
    """轻量业务分析简报：按状态/优先级分组 + 可选指标口径，输出 markdown_report。

    适合「分析一下工单」「产线概况」「帮我看下异常分布」。不是 SQL、不是 BI 看板。
    分组与指标均绑定当前资料包；绑不上如实跳过。
    """
    from tools.query_tool.metrics_pack import _resolve_entity

    catalog = load_catalog()
    if not catalog:
        return {
            "error": "当前未配置可查对象，请先在系统配置接入 MES。",
            "hint": "分析依赖接口目录，与表结构摸底不同。",
        }
    eid = (entity or "").strip() or None
    if eid:
        from tools.query_tool.entity_catalog import resolve_entity_id

        resolved = resolve_entity_id(eid) or eid
        eid = resolved
    else:
        eid = _resolve_entity(
            ["生产工单", "工单", "派工单", "制造工单", "work order", "mo", "ticket"],
            catalog,
        )
    if not eid:
        return {
            "error": "未能确定分析对象：请传 entity，或确保目录里有工单类对象。",
            "available": [
                {"entity": r.get("id"), "label": r.get("label")} for r in catalog[:12]
            ],
        }

    cap = max(1, min(int(limit or 100), 100))
    client = get_client()
    raw = client.query(eid, None, cap)
    if isinstance(raw, dict) and raw.get("error"):
        return raw
    records = raw.get("records") if isinstance(raw.get("records"), list) else []
    presented = present_query_result(raw, filters=None, limit=cap)
    keys: list[str] = []
    for rec in records:
        if isinstance(rec, dict):
            for k in rec.keys():
                ks = str(k)
                if ks not in keys:
                    keys.append(ks)
    labels = field_label_map(str(presented.get("entity") or eid))
    # 分组标签来自资料包 analysis 配置，现场无对应列则自动跳过
    try:
        from tools.query_tool.analysis_config import load_analysis_config

        acfg = load_analysis_config()
        want_labels = list(acfg.get("group_by_labels") or [])
        brief_ids = {
            str(x) for x in (acfg.get("brief_metric_ids") or []) if str(x).strip()
        }
        brief_cap = int(acfg.get("brief_metric_limit") or 4)
    except Exception:
        want_labels = ["状态", "优先级", "产线", "工序", "线体"]
        brief_ids = {"wip", "unfinished", "urgent-unfinished", "completed-today"}
        brief_cap = 4

    breakdowns: list[dict] = []
    for want in want_labels:
        field = resolve_group_by(want, keys, labels)
        if not field:
            continue
        groups = summarize_records(records, field)
        breakdowns.append(
            {
                "group_by": field,
                "group_by_label": labels.get(field) or want,
                "groups": groups,
            }
        )

    metric_rows: list[dict] = []
    if include_metrics:
        listed = list_query_metrics()
        for m in listed.get("metrics") or []:
            mid = str(m.get("id") or "")
            pack_m = None
            try:
                from tools.query_tool.metrics_pack import find_metric

                pack_m = find_metric(mid)
            except Exception:
                pack_m = None
            if brief_ids:
                if mid not in brief_ids:
                    continue
            elif not bool((pack_m or {}).get("include_in_brief")):
                continue
            if not m.get("bindable"):
                metric_rows.append(
                    {
                        "id": m.get("id"),
                        "label": m.get("label"),
                        "bindable": False,
                        "skipped": m.get("reason") or "绑不上",
                    }
                )
                continue
            if m.get("entity") and str(m.get("entity")) != str(presented.get("entity")):
                continue
            if len([x for x in metric_rows if x.get("bindable") and "total" in x]) >= brief_cap:
                break
            out = query_metric(mid, limit=min(50, cap))
            metric_rows.append(
                {
                    "id": mid,
                    "label": m.get("label"),
                    "bindable": True,
                    "total": out.get("total"),
                    "returned": out.get("returned"),
                    "caveats": out.get("caveats") or [],
                    "error": out.get("error"),
                }
            )

    label = presented.get("label") or eid
    total = presented.get("total")
    returned = presented.get("returned")
    lines = [
        f"## 分析简报：{label}（`{presented.get('entity')}`）",
        "",
        f"- MES 共 **{total}** 条，本次分析用了 **{returned}** 条（轻量汇总，非全库 SQL）。",
    ]
    for b in breakdowns:
        lines.append("")
        lines.append(f"### 按「{b['group_by_label']}」分布")
        lines.append("")
        lines.append("| 取值 | 条数 | 占比 |")
        lines.append("| --- | --- | --- |")
        for g in b.get("groups") or []:
            lines.append(f"| {g.get('value')} | {g.get('count')} | {g.get('pct')}% |")
    if metric_rows:
        lines.append("")
        lines.append("### 指标口径（当前目录可绑定）")
        lines.append("")
        lines.append("| 口径 | 条数 | 说明 |")
        lines.append("| --- | --- | --- |")
        for m in metric_rows:
            if m.get("skipped") or m.get("error"):
                note = m.get("skipped") or m.get("error") or ""
                lines.append(f"| {m.get('label')} | — | {note} |")
            else:
                cave = "；".join(str(c) for c in (m.get("caveats") or [])[:1])
                lines.append(
                    f"| {m.get('label')} | **{m.get('total')}** | {cave or '已下发口径 filters'} |"
                )
    lines.append("")
    lines.append(
        "需要明细清单、按条件筛选或导出 CSV/Excel 时告诉我即可。"
    )
    report = "\n".join(lines)
    return {
        "entity": presented.get("entity"),
        "label": label,
        "total": total,
        "returned": returned,
        "breakdowns": breakdowns,
        "metrics": metric_rows,
        "markdown_report": report,
        "sample_table": presented.get("markdown_table") or "",
        "reply_hint": (
            "直接展示 markdown_report；说明这是当前资料包轻量分析，不是全库 SQL。"
            "有 caveats 的口径必须原样告知。不要编造未出现的分组或条数。"
        ),
    }


def analyze_time_trend(
    entity: Annotated[str, "实体英文 id 或中文别名"],
    grain: Annotated[
        str,
        "分桶粒度：day（默认，按日）或 week（按 ISO 周）",
    ] = "day",
    window: Annotated[int, "窗口长度：最近 N 天或 N 周，默认 7，最大 90/52"] = 7,
    time_field: Annotated[
        str | None,
        "时间字段英文名；不传则用 analysis.time_field_hints + 记录列启发式",
    ] = None,
    value_field: Annotated[
        str | None,
        "数值字段：不传则按条数计数；传入则对该字段求和（如 actual_qty）",
    ] = None,
    filters: Annotated[dict | None, "可选过滤，与 query_platform_data 相同"] = None,
    limit: Annotated[int, "拉取记录上限，默认 100（受接口分页限制）"] = 100,
    include_chart: Annotated[bool, "是否自动出折线图，默认 true"] = True,
    user_intent: Annotated[str, "用户原话，传给出图选型"] = "",
    as_of: Annotated[
        str | None,
        "可选：窗口右端日期 YYYY-MM-DD（默认今天）；验收/复现时可用",
    ] = None,
) -> dict:
    """最近 N 天/周趋势：查数 → 时间分桶 → 可选折线图。

    无可靠日期列时诚实失败，禁止编造日期轴。本页抽样，非全库时间序列。
    """
    from tools.query_tool.analysis_config import load_analysis_config
    from tools.query_tool.time_series import build_time_series, _parse_to_date

    client = get_client()
    cap = max(1, min(int(limit or 100), 100))
    grain_l = str(grain or "day").lower()
    is_week = grain_l in ("week", "weekly", "周", "周度") or grain_l.startswith("w")
    win_cap = 52 if is_week else 90
    win = max(1, min(int(window or 7), win_cap))
    raw = client.query(entity, filters, cap)
    if isinstance(raw, dict) and "error" in raw:
        return raw
    records = raw.get("records") if isinstance(raw.get("records"), list) else []
    presented = present_query_result(raw, filters=filters, limit=cap)
    hints: list[str] = []
    try:
        cfg = load_analysis_config()
        raw_hints = cfg.get("time_field_hints") or []
        if isinstance(raw_hints, list):
            hints = [str(x).strip() for x in raw_hints if str(x).strip()]
    except Exception:
        hints = []

    today_d = _parse_to_date(as_of) if as_of else None

    series = build_time_series(
        records if isinstance(records, list) else [],
        time_field=time_field,
        value_field=value_field,
        grain=grain,
        window=win,
        today=today_d,
        time_field_hints=hints,
    )
    if "error" in series:
        series["entity"] = presented.get("entity")
        series["label"] = presented.get("label")
        series["returned"] = presented.get("returned")
        return series

    caveats = list(series.get("caveats") or [])
    total = presented.get("total")
    returned = presented.get("returned")
    try:
        t_i = int(total) if total is not None else None
        r_i = int(returned) if returned is not None else None
    except (TypeError, ValueError):
        t_i, r_i = None, None
    if t_i is not None and r_i is not None and t_i > r_i:
        caveats.append(f"MES 声明 total={t_i}，本次只用了 {r_i} 条参与分桶。")

    out: dict = {
        "ok": True,
        "entity": presented.get("entity"),
        "label": presented.get("label"),
        "filters_applied": presented.get("filters_applied") or filters or {},
        "total": total,
        "returned": returned,
        "grain": series.get("grain"),
        "window": series.get("window"),
        "time_field": series.get("time_field"),
        "value_field": series.get("value_field"),
        "mode": series.get("mode"),
        "categories": series.get("categories"),
        "values": series.get("values"),
        "points_with_data": series.get("points_with_data"),
        "records_used": series.get("records_used"),
        "caveats": caveats[:8],
        "reply_hint": (
            f"说明「{presented.get('label')}」最近 {series.get('window')} 个"
            f"{'周' if series.get('grain') == 'week' else '日'}趋势；"
            f"时间列 `{series.get('time_field')}`，"
            f"{'求和 ' + str(series.get('value_field')) if series.get('value_field') else '按条数'}。"
            "必须原样告知 caveats（本页≠全库）。"
            "前端若已出图，勿再贴 fence；禁止编造日期或数值。"
        ),
    }

    if include_chart and series.get("categories") and series.get("values") is not None:
        from tools.query_tool.analysis_chart import render_analysis_chart

        intent = (user_intent or "").strip() or (
            f"最近{win}{'周' if str(grain).lower().startswith('w') or grain == '周' else '天'}趋势"
        )
        title = f"{presented.get('label') or entity}·{'周' if series.get('grain') == 'week' else '日'}趋势"
        source = "；".join(caveats[:2])
        chart = render_analysis_chart(
            chart_type="line",
            title=title,
            categories=list(series.get("categories") or []),
            values=list(series.get("values") or []),
            series_name="合计" if series.get("mode") == "sum" else "条数",
            definition=f"按 {series.get('time_field')} 分桶（{series.get('grain')}）",
            source_note=source,
            user_intent=intent,
        )
        if isinstance(chart, dict) and chart.get("ok"):
            out["chart"] = {
                "ok": True,
                "chart_type": chart.get("chart_type"),
                "title": chart.get("title"),
                "markdown_fence": chart.get("markdown_fence"),
                "caveats": chart.get("caveats") or [],
            }
            # 供前端拦截出图（与 render_analysis_chart 同形）
            out["markdown_fence"] = chart.get("markdown_fence")
            out["chart_option"] = chart.get("chart_option")
        elif isinstance(chart, dict) and chart.get("error"):
            out["chart_error"] = chart.get("error")
            caveats.append("自动出图失败，已返回 categories/values，可再调 render_analysis_chart。")
            out["caveats"] = caveats[:8]
    return out

