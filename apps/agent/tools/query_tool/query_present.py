"""查数结果展示：中文列名、可读表格、按真实字段分组。"""
from __future__ import annotations

from collections import Counter
from typing import Any

from tools.query_tool.entity_catalog import get_entity

_PREFERRED_COLUMNS = (
    "order_no",
    "work_order_no",
    "wo_no",
    "mo_no",
    "plan_no",
    "code",
    "name",
    "title",
    "product",
    "product_name",
    "product_code",
    "status",
    "state",
    "priority",
    "qty",
    "quantity",
    "plan_qty",
    "workshop",
    "line",
    "updated_at",
    "created_at",
)
_SKIP_COLUMNS = frozenset(
    {
        "id",
        "_id",
        "uuid",
        "pk",
        "tenant_id",
        "enterprise_id",
        "password",
        "passwd",
        "hashed_password",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "api_key",
        "api_secret",
    }
)
_SECRET_COL_MARKERS = ("password", "passwd", "secret", "token", "api_key")
_GROUP_ALIASES: dict[str, tuple[str, ...]] = {
    "状态": ("status", "state", "wo_status", "order_status", "plan_status"),
    "优先级": ("priority", "pri", "urgency"),
    "车间": ("workshop", "workshop_name", "shop"),
    "产线": ("line", "line_name", "production_line"),
    "产品": ("product", "product_name", "product_code", "item_code"),
}
_AUTO_GROUP = (
    "status",
    "state",
    "wo_status",
    "order_status",
    "plan_status",
    "priority",
)
_FALLBACK_LABELS = {
    "order_no": "工单号",
    "work_order_no": "工单号",
    "wo_no": "工单号",
    "mo_no": "工单号",
    "plan_no": "计划号",
    "code": "编码",
    "name": "名称",
    "title": "标题",
    "product": "产品",
    "product_name": "产品",
    "product_code": "产品编码",
    "status": "状态",
    "state": "状态",
    "priority": "优先级",
    "qty": "数量",
    "quantity": "数量",
    "plan_qty": "计划数量",
    "workshop": "车间",
    "line": "产线",
    "production_line": "产线",
    "updated_at": "更新时间",
    "created_at": "创建时间",
}


def _human_label(name: str, catalog_label: str | None = None) -> str:
    if catalog_label and catalog_label.strip() and catalog_label.strip() != name:
        return catalog_label.strip()
    return _FALLBACK_LABELS.get(name) or _FALLBACK_LABELS.get(name.lower()) or catalog_label or name


def field_label_map(entity: str | None, meta: dict[str, Any] | None = None) -> dict[str, str]:
    """catalog fields + columns → {英文名: 中文标签}。"""
    spec = meta if isinstance(meta, dict) else (get_entity(entity or "") or {})
    out: dict[str, str] = {}
    for key in ("columns", "fields"):
        for item in spec.get(key) or []:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                out.setdefault(name, _human_label(name, str(item.get("label") or "")))
            elif isinstance(item, str) and item.strip():
                out.setdefault(item.strip(), _human_label(item.strip()))
    return out


def compact_cell(value: Any, max_len: int = 48) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (dict, list)):
        text = str(value)
    else:
        text = str(value).strip()
    text = " ".join(text.split())
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def pick_display_columns(
    records: list[dict[str, Any]],
    labels: dict[str, str] | None = None,
    max_cols: int = 8,
    preferred: list[str] | None = None,
) -> list[str]:
    """优先选资料包列、业务关键列与带中文标签的列，跳过 id/token。"""
    labels = labels or {}
    seen: list[str] = []
    keys_in_data: set[str] = set()
    for rec in records:
        if isinstance(rec, dict):
            keys_in_data.update(str(k) for k in rec.keys())

    def add(name: str) -> None:
        if name not in keys_in_data or name in seen:
            return
        low = name.lower()
        if low in _SKIP_COLUMNS or any(m in low for m in _SECRET_COL_MARKERS):
            return
        seen.append(name)

    for name in preferred or []:
        add(str(name))
        if len(seen) >= max_cols:
            return seen
    for name in _PREFERRED_COLUMNS:
        add(name)
        if len(seen) >= max_cols:
            return seen
    for name in labels:
        add(name)
        if len(seen) >= max_cols:
            return seen
    if records and isinstance(records[0], dict):
        for name in records[0].keys():
            add(str(name))
            if len(seen) >= max_cols:
                return seen
    return seen


def display_rows(
    records: list[dict[str, Any]],
    columns: list[str],
    labels: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    labels = labels or {}
    rows: list[dict[str, str]] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        row: dict[str, str] = {}
        for col in columns:
            header = labels.get(col) or col
            row[header] = compact_cell(rec.get(col))
        rows.append(row)
    return rows


def markdown_table(
    rows: list[dict[str, str]],
    headers: list[str] | None = None,
) -> str:
    if not rows:
        return ""
    cols = headers or list(rows[0].keys())
    if not cols:
        return ""
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row.get(c, "") for c in cols) + " |")
    return "\n".join(lines)


def _fold_field(name: str) -> str:
    """billStatus / WO-State → bill_status / wo_state，便于跨平台比对。"""
    s = str(name or "").replace("-", "_")
    out: list[str] = []
    for i, ch in enumerate(s):
        prev = s[i - 1] if i else ""
        nxt = s[i + 1] if i + 1 < len(s) else ""
        if ch.isupper() and prev and (prev.islower() or (nxt and nxt.islower())):
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _looks_groupable_status(name: str) -> bool:
    n = _fold_field(name)
    parts = {p for p in n.split("_") if p}
    if parts & {"status", "state", "priority", "pri"}:
        return True
    return "status" in n or n.endswith("state")


def resolve_group_by(
    requested: str | None,
    available: list[str],
    labels: dict[str, str] | None = None,
) -> str | None:
    """把用户说法映射到记录里真实存在的字段名（不写死某一套 MES 字段）。"""
    avail_l = {k.lower(): k for k in available}
    folded = {_fold_field(k): k for k in available}
    labels = labels or {}
    label_to_name = {v: k for k, v in labels.items() if v}
    raw = (requested or "").strip()
    if raw:
        if raw in available:
            return raw
        if raw.lower() in avail_l:
            return avail_l[raw.lower()]
        folded_raw = _fold_field(raw)
        if folded_raw in folded:
            return folded[folded_raw]
        if raw in label_to_name and label_to_name[raw] in available:
            return label_to_name[raw]
        for alias, cands in _GROUP_ALIASES.items():
            if raw == alias or raw.lower() == alias.lower():
                for c in cands:
                    if c in available:
                        return c
                if alias in {"状态", "优先级"}:
                    for k in available:
                        if _looks_groupable_status(k):
                            return k
        for k, lab in labels.items():
            if lab == raw and k in available:
                return k
        return None
    for cand in _AUTO_GROUP:
        if cand in available:
            return cand
    for k in available:
        if _looks_groupable_status(k):
            return k
    for alias_cands in _GROUP_ALIASES.values():
        for c in alias_cands:
            if c in available:
                return c
    return None


def summarize_records(
    records: list[dict[str, Any]],
    group_by: str,
) -> list[dict[str, Any]]:
    values: list[str] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        raw = rec.get(group_by)
        values.append(compact_cell(raw) if raw is not None and raw != "" else "(空)")
    total = len(values) or 1
    groups: list[dict[str, Any]] = []
    for value, count in Counter(values).most_common():
        groups.append(
            {
                "value": value,
                "count": count,
                "pct": round(100.0 * count / total, 1),
            }
        )
    return groups


def _narrow_urgent_filter_hint(applied: dict[str, Any] | None) -> str | None:
    """只用 priority=urgent 时提醒：值班「紧急工单」口径还含 high 且未完工。"""
    if not applied or len(applied) != 1:
        return None
    key, val = next(iter(applied.items()))
    if str(key).strip().lower() not in {"priority", "pri", "urgency"}:
        return None
    if str(val or "").strip().lower() not in {"urgent", "紧急", "critical"}:
        return None
    return (
        "若用户问的是「紧急工单/急单」（未限定只要 urgent 这一档），"
        "请改用 query_metric('紧急未完工') 或 run_ops_scene('urgent-backlog')，"
        "口径含 urgent+high 且未完工；不要把本结果当成最终紧急清单。"
    )


def present_query_result(
    raw: dict[str, Any],
    filters: dict | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """给 Agent 可读的查数结果：中文列、条数、已下发的 filters。"""
    if not isinstance(raw, dict):
        return {"error": "查询结果格式异常"}
    if "error" in raw:
        return raw

    eid = str(raw.get("entity") or "")
    meta = get_entity(eid) or {}
    records = raw.get("records")
    if not isinstance(records, list):
        records = []
    labels = field_label_map(eid, meta)
    for rec in records:
        if isinstance(rec, dict):
            for k in rec.keys():
                ks = str(k)
                labels.setdefault(ks, _human_label(ks))
    preferred: list[str] = []
    for key in ("columns", "fields"):
        for item in meta.get(key) or []:
            name = item.get("name") if isinstance(item, dict) else item
            n = str(name or "").strip()
            if n and n not in preferred:
                preferred.append(n)
    columns = pick_display_columns(records, labels, preferred=preferred)
    shown = display_rows(records, columns, labels)
    headers = [labels.get(c) or c for c in columns]
    applied = {k: v for k, v in (filters or {}).items() if v is not None and v != ""}
    total = raw.get("total")
    if not isinstance(total, int):
        total = len(records)
    label = str(meta.get("label") or eid)
    table = markdown_table(shown, headers)
    hint = (
        f"请用 Markdown 表展示 display_rows（或直接使用 markdown_table）；"
        f"说明查的是「{label}」(`{eid}`)，MES 共 {total} 条，本次返回 {len(records)} 条。"
        "有 filters_applied 必须复述条件。不要编造未返回的字段。"
    )
    if applied:
        hint += " 筛选已作为 API query 参数下发，不是客户端口头过滤。"
    narrow = _narrow_urgent_filter_hint(applied)
    if narrow:
        hint += " " + narrow
    out = {
        "entity": eid,
        "label": label,
        "total": total,
        "returned": len(records),
        "filters_applied": applied,
        "columns": [{"name": c, "label": labels.get(c) or c} for c in columns],
        "display_rows": shown,
        "markdown_table": table,
        "reply_hint": hint,
        "limit": limit,
    }
    # 已有中文表时不再附带 raw records，避免 tool JSON 重复占上下文（汇总类工具读 MES 原始响应）
    if not shown:
        out["records"] = records
    if narrow:
        out["followup_hint"] = narrow
    return out
