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

    返回实体 id、中文名、别名、支持操作与字段概要。
    导入/查询前应先调用此工具确认目标实体与正确的英文 id。
    """
    client = get_client()
    catalog = catalog_summary()
    details = []
    for row in catalog:
        eid = row["entity"]
        info = client.describe_entity(eid)
        item = {
            "entity": eid,
            "label": row["label"],
            "aliases": row["aliases"],
            "ops": row["ops"],
            "catalog_fields": row["fields"],
            "field_labels": row.get("field_labels") or {},
        }
        if "error" not in info:
            item["fields"] = info.get("fields", [])
            item["record_count"] = info.get("record_count", 0)
        else:
            item["error"] = info["error"]
            item["fields"] = row["fields"]
            item["record_count"] = 0
        details.append(item)

    return {
        "entities": [r["entity"] for r in catalog],
        "count": len(catalog),
        "details": details,
        "hint": "调用 query/import/export 时 entity 必须用上方英文 id；换平台后目录会变，禁止沿用其它 MES 的 id",
    }


def query_platform_data(
    entity: Annotated[str, "实体英文 id（来自当前可查对象目录），也可用中文别名"],
    filters: Annotated[
        dict | None,
        "可选过滤条件，字段名以 describe_entity / 目录 fields 为准；会作为 API query 参数下发",
    ] = None,
    limit: Annotated[int, "返回记录上限，默认 20"] = 20,
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
    """按返回记录里真实存在的字段做轻量分组计数（如按状态各多少）。

    分组字段来自本次返回列或用户指定；不写死某一套 MES 的字段名。
    不是数据库 COUNT(*)；MES 总条数大于本次 returned 时，比例只覆盖本页。
    """
    client = get_client()
    cap = max(1, min(int(limit or 100), 100))
    raw = client.query(entity, filters, cap)
    if isinstance(raw, dict) and "error" in raw:
        return raw
    presented = present_query_result(raw, filters=filters, limit=cap)
    records = presented.get("records") or []
    keys: list[str] = []
    for rec in records:
        if isinstance(rec, dict):
            for k in rec.keys():
                ks = str(k)
                if ks not in keys:
                    keys.append(ks)
    labels = field_label_map(str(presented.get("entity") or entity))
    field = resolve_group_by(group_by, keys, labels)
    if not field:
        return {
            "error": (
                f"无法按 {group_by!r} 汇总：该字段不在本次返回记录中。"
                if group_by
                else "无法自动选择分组字段：本次记录没有状态/优先级等常见列。"
            ),
            "available_fields": keys,
            "entity": presented.get("entity"),
            "label": presented.get("label"),
            "hint": "group_by 必须是本次返回记录里真实存在的字段（可用中文标签，如「状态」）。",
        }
    groups = summarize_records(records, field)
    total = presented.get("total") or 0
    returned = presented.get("returned") or 0
    note = "按本次返回记录分组，不是数据库全表 COUNT。"
    if isinstance(total, int) and isinstance(returned, int) and total > returned:
        note += f" MES 共 {total} 条，本次只用了 {returned} 条，比例仅覆盖本页。"
    return {
        "entity": presented.get("entity"),
        "label": presented.get("label"),
        "group_by": field,
        "group_by_label": labels.get(field) or field,
        "filters_applied": presented.get("filters_applied") or {},
        "total": total,
        "returned": returned,
        "groups": groups,
        "note": note,
        "reply_hint": (
            f"说明「{presented.get('label')}」(`{presented.get('entity')}`) "
            f"按「{labels.get(field) or field}」分组；列出 groups 的 value/count/pct；"
            "有 filters_applied 须复述。不要编造未出现的分组值。"
        ),
    }


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


def get_platform_summary() -> dict:
    """获取平台的概要信息：有哪些实体、各有多少数据。

    适合作为 Agent 了解平台全貌的第一步。
    """
    client = get_client()
    catalog = catalog_summary()
    summary = {}
    total_records = 0
    for row in catalog:
        eid = row["entity"]
        info = client.describe_entity(eid)
        count = info.get("record_count", 0)
        summary[eid] = {
            "label": row["label"],
            "aliases": row["aliases"],
            "record_count": count,
        }
        total_records += count
    return {
        "entity_count": len(catalog),
        "total_records": total_records,
        "breakdown": summary,
    }


def list_query_metrics() -> dict:
    """列出当前资料包能绑定的指标口径（在制 / 未完工 / 紧急未完工 / 当日完工等）。

    口径模板是通用的，实体与字段绑定当前可查对象目录；换平台后可在资料包放 metrics.json 覆盖。
    """
    pack = load_metrics_pack()
    catalog = load_catalog()
    items = []
    for m in pack.get("metrics") or []:
        bound = bind_metric(m, catalog=catalog, observed={})
        items.append(
            {
                "id": m.get("id"),
                "label": m.get("label"),
                "aliases": m.get("aliases") or [],
                "definition": m.get("definition") or "",
                "bindable": "error" not in bound,
                "entity": bound.get("entity"),
                "entity_label": bound.get("entity_label"),
                "reason": bound.get("error"),
            }
        )
    return {
        "count": len(items),
        "metrics": items,
        "hint": (
            "用户说在制/未完工/紧急单/当日完工时调用 query_metric(name=口径id或中文名)。"
            "禁止套用其它 MES 的实体 id；绑不上就如实说。"
        ),
    }


def query_metric(
    name: Annotated[str, "口径 id 或中文说法，如 wip / 在制 / 紧急未完工 / 当日完工"],
    extra_filters: Annotated[
        dict | None, "额外筛选（会与口径 filters 一并下发给 MES），字段名以当前目录为准"
    ] = None,
    limit: Annotated[int, "返回记录上限，默认 20"] = 20,
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
    extra = {k: v for k, v in (extra_filters or {}).items() if v is not None and v != ""}
    for fs in bound.get("filter_sets") or []:
        filters = {**fs, **extra}
        raw = client.query(bound["entity"], filters, max(1, min(int(limit or 20), 100)))
        calls.append({"filters": filters, "error": raw.get("error") if isinstance(raw, dict) else None})
        if not isinstance(raw, dict) or "error" in raw:
            continue
        for rec in raw.get("records") or []:
            if not isinstance(rec, dict):
                continue
            key = str(rec.get("id") or rec.get("order_no") or rec)
            if key in seen:
                continue
            seen.add(key)
            merged.append(rec)

    presented = present_query_result(
        {"entity": bound["entity"], "total": len(merged), "records": merged[: max(1, int(limit or 20))]},
        filters=None,
        limit=limit,
    )
    presented["filters_applied"] = extra
    presented["metric"] = bound.get("id")
    presented["metric_label"] = bound.get("label")
    presented["definition"] = bound.get("definition")
    presented["filter_sets"] = bound.get("filter_sets")
    presented["caveats"] = bound.get("caveats") or []
    presented["api_calls"] = len(calls)
    presented["reply_hint"] = (
        f"先复述口径「{bound.get('label')}」：{bound.get('definition')}；"
        f"查的是「{bound.get('entity_label')}」(`{bound.get('entity')}`)，"
        f"本次 {presented.get('returned')} 条。"
        "列出实际下发的 filter_sets；有 caveats 必须告诉用户。"
        "不要编造未返回的记录。"
    )
    if any(c.get("error") for c in calls) and not merged:
        presented["error"] = "按口径请求 MES 失败"
        presented["call_errors"] = [c for c in calls if c.get("error")]
    return presented
