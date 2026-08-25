"""通用聚合（M1）：页内分组为默认；资料包可选声明服务端聚合接口。

原则：
- 不写死任何厂的实体 id / path / 字段名
- 无可靠全库聚合时，必须带 caveat，禁止暗示「全库比例」
- 聚合失败只降级，不抛错、不阻断 query_platform_data
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from tools.query_tool.query_present import (
    field_label_map,
    resolve_group_by,
    summarize_records,
)

# 统一 caveat 文案（可被资料包覆盖前缀，但语义不可删）
CAVEAT_PAGE_SCOPE = (
    "按本次返回记录分组，不是全库 COUNT(*)；占比仅覆盖本页，勿当成全库分布。"
)
CAVEAT_TRUNCATED = "MES 声明总条数大于本页 returned，汇总未覆盖全部记录。"
CAVEAT_NO_TOTAL = "接口未返回可靠 total，无法确认是否已覆盖全库。"
CAVEAT_AGG_FALLBACK = "资料包声明的聚合接口不可用或返回无法解析，已降级为本页汇总。"


def page_scope_caveats(
    *,
    total: Any,
    returned: Any,
    extra: list[str] | None = None,
) -> list[str]:
    """页内汇总必须附带的口径说明。"""
    out: list[str] = [CAVEAT_PAGE_SCOPE]
    try:
        t = int(total) if total is not None else None
    except (TypeError, ValueError):
        t = None
    try:
        r = int(returned) if returned is not None else None
    except (TypeError, ValueError):
        r = None
    if t is None or t < 0:
        out.append(CAVEAT_NO_TOTAL)
    elif r is not None and t > r:
        out.append(f"{CAVEAT_TRUNCATED}（total={t}，本页={r}）")
    if extra:
        for c in extra:
            s = str(c or "").strip()
            if s and s not in out:
                out.append(s)
    return out[:8]


def entity_aggregate_spec(entity_meta: dict[str, Any] | None) -> dict[str, Any] | None:
    """从资料包实体上读取可选聚合声明（无则 None，走页内）。

    支持形态（任选，均由资料包配置，产品不写死 path）：
    - entity.aggregate = { "path", "group_param"?, "method"? }
    - entity.paths.aggregate + entity.aggregate_param
    """
    if not isinstance(entity_meta, dict):
        return None
    agg = entity_meta.get("aggregate")
    if isinstance(agg, dict) and (agg.get("path") or agg.get("url")):
        path = str(agg.get("path") or agg.get("url") or "").strip()
        if not path:
            return None
        method = str(agg.get("method") or "GET").upper()
        if method not in ("GET", "POST"):
            return None
        return {
            "path": path,
            "group_param": str(agg.get("group_param") or agg.get("groupBy") or "groupBy").strip()
            or "groupBy",
            "method": method,
        }
    paths = entity_meta.get("paths")
    if isinstance(paths, dict) and paths.get("aggregate"):
        path = str(paths.get("aggregate") or "").strip()
        if not path:
            return None
        return {
            "path": path,
            "group_param": str(
                entity_meta.get("aggregate_param")
                or entity_meta.get("group_param")
                or "groupBy"
            ).strip()
            or "groupBy",
            "method": "GET",
        }
    return None


def parse_aggregate_payload(payload: Any, *, group_field: str) -> list[dict[str, Any]] | None:
    """把各厂常见聚合 JSON 解析成 [{value, count}]；解析不了返回 None（触发降级）。"""
    if payload is None:
        return None
    if isinstance(payload, dict) and payload.get("error"):
        return None

    candidates: list[Any] = []
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        for key in ("groups", "data", "items", "rows", "result", "list"):
            raw = payload.get(key)
            if isinstance(raw, list) and raw:
                candidates = raw
                break
        if not candidates:
            # { "pending": 3, "done": 1 } 扁平计数
            flat: list[dict[str, Any]] = []
            for k, v in payload.items():
                if k in ("error", "ok", "message", "total", "entity", "code"):
                    continue
                try:
                    n = int(v)
                except (TypeError, ValueError):
                    continue
                if n < 0:
                    continue
                flat.append({"value": str(k), "count": n})
            if flat:
                total = sum(g["count"] for g in flat) or 1
                for g in flat:
                    g["pct"] = round(100.0 * g["count"] / total, 1)
                return sorted(flat, key=lambda x: (-x["count"], str(x["value"])))
            return None
    else:
        return None

    groups: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        value = None
        for vk in (
            "value",
            "name",
            "key",
            "label",
            group_field,
            "status",
            "priority",
            "category",
        ):
            if item.get(vk) is not None and str(item.get(vk)).strip() != "":
                value = str(item.get(vk)).strip()
                break
        if value is None:
            continue
        count = None
        for ck in ("count", "total", "num", "qty", "quantity", "value_count"):
            if item.get(ck) is not None:
                try:
                    count = int(item[ck])
                except (TypeError, ValueError):
                    count = None
                if count is not None:
                    break
        if count is None:
            continue
        groups.append({"value": value, "count": max(0, count)})
    if not groups:
        return None
    total = sum(g["count"] for g in groups) or 1
    for g in groups:
        g["pct"] = round(100.0 * g["count"] / total, 1)
    return sorted(groups, key=lambda x: (-x["count"], str(x["value"])))


def try_server_aggregate(
    *,
    client: Any,
    entity_meta: dict[str, Any],
    group_by_field: str,
    filters: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """若实体声明了聚合接口则尝试调用；失败返回 None（由调用方降级）。

    安全：仅 GET/POST；path 经 safe_request_path；query 名经 safe_query_name。
    """
    spec = entity_aggregate_spec(entity_meta)
    if not spec:
        return None
    path = str(spec["path"]).strip()
    if not path:
        return None
    method = str(spec["method"] or "GET").upper()
    if method not in ("GET", "POST"):
        return None
    from safe_http import safe_query_name, safe_request_path

    group_param = safe_query_name(str(spec.get("group_param") or "groupBy"))
    if not group_param:
        return None
    cleaned = safe_request_path(path if path.startswith("/") else f"/{path}")
    if not cleaned:
        return None

    params: dict[str, str] = {group_param: str(group_by_field)[:128]}
    if isinstance(filters, dict):
        for k, v in filters.items():
            if v is None or v == "":
                continue
            pk = safe_query_name(str(k))
            if not pk or pk == group_param:
                continue
            # 列表筛参压成逗号串，长度封顶，避免异常大 query
            if isinstance(v, (list, tuple)):
                sv = ",".join(str(x) for x in v[:20])
            else:
                sv = str(v)
            params[pk] = sv[:256]

    try:
        if not hasattr(client, "_request"):
            return None
        if method == "GET":
            qs = urlencode(params, doseq=True)
            # path 不含 ?；query 另拼（safe_request_path 禁查询串）
            full = f"{cleaned}?{qs}" if qs else cleaned
            payload = client._request("GET", full)  # noqa: SLF001
        else:
            payload = client._request("POST", cleaned, params)  # noqa: SLF001
    except Exception:
        return None
    if isinstance(payload, dict) and payload.get("error"):
        return None
    groups = parse_aggregate_payload(payload, group_field=group_by_field)
    if not groups:
        return None
    total = None
    if isinstance(payload, dict) and isinstance(payload.get("total"), int):
        total = payload["total"]
    else:
        total = sum(g["count"] for g in groups)
    return {
        "mode": "server",
        "groups": groups,
        "total": total,
        "returned": total,
        "caveats": [
            "分组来自资料包声明的聚合接口（非页内抽样）。",
            "勿默认说成全厂/全库比例，除非接口文档明确保证覆盖范围。",
        ],
        "source": "entity_aggregate",
    }


def aggregate_by_field(
    *,
    entity: str,
    group_by: str | None,
    filters: dict[str, Any] | None,
    limit: int,
    client: Any,
    entity_meta: dict[str, Any] | None,
    records: list[dict[str, Any]],
    presented: dict[str, Any],
) -> dict[str, Any]:
    """统一聚合入口：先试服务端声明，再页内分组。"""
    labels = field_label_map(str(presented.get("entity") or entity), entity_meta)
    keys: list[str] = []
    for rec in records:
        if isinstance(rec, dict):
            for k in rec.keys():
                ks = str(k)
                if ks not in keys:
                    keys.append(ks)
    # 目录字段也并入候选，便于尚无样例行时解析 group_by
    if entity_meta:
        for bucket in (entity_meta.get("columns"), entity_meta.get("fields")):
            if not isinstance(bucket, list):
                continue
            for item in bucket:
                name = item.get("name") if isinstance(item, dict) else item
                if name and str(name) not in keys:
                    keys.append(str(name))

    field = resolve_group_by(group_by, keys, labels)
    if not field:
        return {
            "error": (
                f"无法按 {group_by!r} 汇总：该字段不在本次返回记录/目录中。"
                if group_by
                else "无法自动选择分组字段：本次记录没有状态/优先级等常见列。"
            ),
            "available_fields": keys,
            "entity": presented.get("entity"),
            "label": presented.get("label"),
            "hint": "group_by 必须是本次返回记录里真实存在的字段（可用中文标签，如「状态」）。",
        }

    server = None
    if entity_meta:
        server = try_server_aggregate(
            client=client,
            entity_meta=entity_meta,
            group_by_field=field,
            filters=filters,
        )
    if server and server.get("groups"):
        caveats = list(server.get("caveats") or [])
        return {
            "entity": presented.get("entity"),
            "label": presented.get("label"),
            "group_by": field,
            "group_by_label": labels.get(field) or field,
            "filters_applied": presented.get("filters_applied") or filters or {},
            "total": server.get("total"),
            "returned": server.get("returned"),
            "groups": server["groups"],
            "mode": "server",
            "caveats": caveats,
            "note": "；".join(caveats[:2]),
            "reply_hint": (
                f"说明「{presented.get('label')}」按「{labels.get(field) or field}」分组；"
                "列出 groups；这是聚合接口结果。"
                "必须原样告知 caveats；勿默认说成全库比例。有 filters 须复述。"
            ),
        }

    groups = summarize_records(records, field)
    total = presented.get("total")
    returned = presented.get("returned") or len(records)
    extra: list[str] = []
    if entity_aggregate_spec(entity_meta):
        extra.append(CAVEAT_AGG_FALLBACK)
    caveats = page_scope_caveats(total=total, returned=returned, extra=extra)
    return {
        "entity": presented.get("entity"),
        "label": presented.get("label"),
        "group_by": field,
        "group_by_label": labels.get(field) or field,
        "filters_applied": presented.get("filters_applied") or filters or {},
        "total": total,
        "returned": returned,
        "groups": groups,
        "mode": "page",
        "caveats": caveats,
        "note": "；".join(caveats[:2]),
        "reply_hint": (
            f"说明「{presented.get('label')}」(`{presented.get('entity')}`) "
            f"按「{labels.get(field) or field}」分组；列出 groups 的 value/count/pct；"
            "必须原样告知 caveats（本页≠全库）。有 filters_applied 须复述。"
            "不要编造未出现的分组值。"
        ),
    }
