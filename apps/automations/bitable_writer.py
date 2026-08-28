"""从 Agent 摘要解析 rows，并按 field_map 转成飞书 fields。"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

# 摘要中约定块：```bitable_json ... ``` 或 【BITABLE_JSON】...【/BITABLE_JSON】
_BITABLE_FENCE_RE = re.compile(
    r"```(?:bitable_json|json)\s*([\s\S]*?)```",
    re.IGNORECASE,
)
_BITABLE_TAG_RE = re.compile(
    r"【BITABLE_JSON】\s*([\s\S]*?)\s*【/BITABLE_JSON】",
    re.IGNORECASE,
)

MAX_BITABLE_ROWS = 30
MAX_BITABLE_COLS = 30
# 写表解析摘要上限，防止 Agent 超长回复拖垮内存/正则
MAX_BITABLE_SUMMARY_CHARS = 262_144
_MAX_ORDER_NO_LEN = 64

DEFAULT_FIELD_MAP: dict[str, str] = {
    "date": "日期",
    "wip_count": "在制工单",
    "open_count": "未完工",
    "urgent_open": "紧急未完工",
    "utilization_avg": "平均稼动率",
    "output_total": "日产合计",
    "yield_min": "良率下限",
    "yield_max": "良率上限",
    "note": "需关注摘要",
    # 工单明细英文键 → 中文列
    "order_no": "工单号",
    "product_name": "产品",
    "product_code": "料号",
    "production_line": "产线",
    "current_process": "工序",
    "process": "工序",
    "plan_quantity": "计划量",
    "actual_quantity": "完工量",
    "status": "状态",
    "priority": "优先级",
    "actual_end_time": "完工时间",
    "end_date": "完工时间",
    "yield_rate": "良率",
    "total_inspected": "检验数",
}

# 期望列名 → 常见人工写法（含 %、简称等）；写表前会与飞书真实表头宽松对齐
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "日期": ("日期", "业务日", "统计日", "日报日期", "日期时间"),
    "在制工单": ("在制工单", "在制", "在制数", "WIP"),
    "未完工": ("未完工", "未完工数", "未完成", "未完成工单"),
    "紧急未完工": ("紧急未完工", "紧急未完成", "急单未完工", "紧急在制"),
    "平均稼动率": ("平均稼动率", "平均稼动率%", "稼动率", "设备稼动率", "利用率", "平均利用率"),
    "日产合计": ("日产合计", "日产量", "产量合计", "当日产出", "产出合计"),
    "良率下限": ("良率下限", "良率下限%", "最低良率", "良率min"),
    "良率上限": ("良率上限", "良率上限%", "最高良率", "良率max"),
    "需关注摘要": ("需关注摘要", "需关注", "备注", "摘要", "关注事项"),
}


def normalize_field_label(name: str) -> str:
    """列名规范化：去空白、%、全角符号，便于人工建表时宽松匹配。"""
    text = str(name or "").strip().lower()
    for ch in (" ", "\u3000", "%", "％", ":", "：", "(", ")", "（", "）", "-", "_"):
        text = text.replace(ch, "")
    return text


def _alias_norms_for_desired(desired: str) -> set[str]:
    key = str(desired or "").strip()
    aliases = _FIELD_ALIASES.get(key, (key,))
    norms = {normalize_field_label(a) for a in aliases}
    norms.add(normalize_field_label(key))
    return {n for n in norms if n}


def resolve_column_name(desired: str, table_fields: list[str]) -> str | None:
    """把配置里的期望列名对齐到飞书表真实列名；找不到返回 None。"""
    want = str(desired or "").strip()
    if not want or not table_fields:
        return None
    for name in table_fields:
        if name == want:
            return name
    want_norm = normalize_field_label(want)
    alias_norms = _alias_norms_for_desired(want)
    for name in table_fields:
        n = normalize_field_label(name)
        if n and (n == want_norm or n in alias_norms):
            return name
    for name in table_fields:
        n = normalize_field_label(name)
        if not n:
            continue
        if want_norm and (want_norm in n or n in want_norm):
            return name
        if any(a and (a in n or n in a) for a in alias_norms):
            return name
    return None


def resolve_column_meta(
    desired: str,
    table_fields: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """对齐到真实字段元数据 {field_id, field_name, type}。"""
    names = [str(f.get("field_name") or "") for f in table_fields if isinstance(f, dict)]
    hit = resolve_column_name(desired, names)
    if not hit:
        return None
    for f in table_fields:
        if isinstance(f, dict) and str(f.get("field_name") or "") == hit:
            return f
    return None


# 缺列时自动创建用的类型：1 文本 / 2 数字 / 5 日期
DESIRED_FIELD_SPECS: dict[str, dict[str, Any]] = {
    "日期": {"type": 5, "property": {"date_formatter": "yyyy/MM/dd"}},
    "工序": {"type": 1},
    "完工时间": {"type": 1},  # 保留时分秒，用文本列
    "在制工单": {"type": 2},
    "未完工": {"type": 2},
    "紧急未完工": {"type": 2},
    "平均稼动率": {"type": 2},
    "日产合计": {"type": 2},
    "良率下限": {"type": 2},
    "良率上限": {"type": 2},
    "良率": {"type": 2},
    "检验数": {"type": 2},
    "需关注摘要": {"type": 1},
}


def coerce_value_for_field_type(value: Any, field_type: int | None) -> Any:
    """按飞书字段类型改写值，避免「数字写进文本列 / 日期格式不对」。"""
    if value is None:
        return None
    ft = int(field_type) if field_type is not None else -1
    # 日期
    if ft == 5:
        if isinstance(value, (int, float)) and value > 10_000_000_000:
            return int(value)
        if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}", value.strip()):
            d = datetime.strptime(value.strip()[:10], "%Y-%m-%d")
            return int(d.timestamp() * 1000)
        return value
    # 数字
    if ft == 2:
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str) and re.match(r"^-?\d+(\.\d+)?$", value.strip()):
            return float(value) if "." in value else int(value)
        return value
    # 文本及其他：日期戳转可读；数字转字符串
    if ft == 1:
        if isinstance(value, (int, float)) and value > 10_000_000_000:
            try:
                return datetime.fromtimestamp(value / 1000.0).strftime("%Y-%m-%d")
            except (OverflowError, OSError, ValueError):
                return str(value)
        return str(value)
    return value


def remap_records_to_table_fields(
    records: list[dict[str, Any]],
    table_fields: list[str] | list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """按真实表头重写 records.fields；支持纯名字列表或字段元数据列表。"""
    metas: list[dict[str, Any]]
    if table_fields and isinstance(table_fields[0], dict):
        metas = [f for f in table_fields if isinstance(f, dict)]
    else:
        metas = [{"field_name": str(n), "type": None} for n in table_fields]

    matched: list[str] = []
    missing: list[str] = []
    seen_desired: set[str] = set()
    cache: dict[str, dict[str, Any] | None] = {}

    out: list[dict[str, Any]] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        raw_fields = rec.get("fields")
        if not isinstance(raw_fields, dict):
            continue
        new_fields: dict[str, Any] = {}
        for desired, value in raw_fields.items():
            ds = str(desired)
            if ds not in cache:
                cache[ds] = resolve_column_meta(ds, metas)
            meta = cache[ds]
            if ds not in seen_desired:
                seen_desired.add(ds)
                if meta:
                    actual = str(meta.get("field_name") or "")
                    matched.append(f"{ds}→{actual}" if actual != ds else ds)
                else:
                    missing.append(ds)
            if not meta:
                continue
            actual = str(meta.get("field_name") or "")
            if not actual:
                continue
            ft = meta.get("type")
            try:
                ft_n = int(ft) if ft is not None else None
            except (TypeError, ValueError):
                ft_n = None
            new_fields[actual] = coerce_value_for_field_type(value, ft_n)
        if new_fields:
            # 表常见默认主列「文本」：用首个像主键的文本字段或拼摘要
            has_text_col = any(str(m.get("field_name") or "") == "文本" for m in metas)
            if has_text_col and "文本" not in new_fields:
                primary = None
                for k in ("工单号", "订单号", "产品", "料号", "名称", "标题"):
                    if k in new_fields and new_fields[k] not in (None, ""):
                        primary = str(new_fields[k])
                        break
                if primary is None:
                    bits: list[str] = []
                    for k, val in list(new_fields.items())[:4]:
                        if k == "日期" and isinstance(val, (int, float)) and val > 10_000_000_000:
                            try:
                                val = datetime.fromtimestamp(float(val) / 1000.0).strftime("%Y-%m-%d")
                            except (OverflowError, OSError, ValueError):
                                val = str(val)
                        bits.append(f"{k}:{val}")
                    primary = " · ".join(bits) if bits else "数据行"
                new_fields["文本"] = str(primary)[:500]
            out.append({"fields": new_fields})
    return out, matched, missing


def collect_desired_columns(records: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for rec in records:
        if not isinstance(rec, dict):
            continue
        fields = rec.get("fields")
        if not isinstance(fields, dict):
            continue
        for k in fields:
            ks = str(k)
            if ks not in seen:
                seen.add(ks)
                names.append(ks)
    return names

BITABLE_JSON_INSTRUCTION = """
【多维表格输出 · 必须】先输出简短正文（明细最多列 8 条示例），再追加完整结构化数据（勿省略、勿截断）：
```bitable_json
{"rows":[{"工单号":"WO-1","产品":"…","料号":"…","产线":"…","工序":"贴片","计划量":0,"完工量":0,"状态":"已完成","完工时间":"2026-08-28 16:00:00","优先级":"普通","良率":97.8,"检验数":100}]}
```
规则（查什么写什么）：
1. rows = 本轮查到的业务明细；一条记录一行；最多 30 行。
2. 键=飞书列名（中文）；值必须来自本轮 MES；查不到的键省略。
3. 工单列表任务：rows 以工单字段为主（工单号/产品/料号/产线/工序/计划量/完工量/状态/完工时间/优先级）；若有「挂在单张工单上」的良率/检验数，写入同一行的「良率」「检验数」。
4. 强制映射：current_process→工序，actual_end_time/end_date→完工时间；以 records 的 keys 为准，不要因 filter_fields 未声明就省略。
5. 「完工时间」优先 actual_end_time（可写成 YYYY-MM-DD HH:MM:SS）；禁止编造。
6. 禁止：工序良率汇总行、稼动率、日产、在制汇总；禁止把列表压成一行日报；bitable_json 须完整并以 ``` 结束。
"""


def _loads_json_loose(raw: str) -> Any | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    end = text.rfind("}")
    if end >= 0:
        try:
            return json.loads(text[: end + 1])
        except json.JSONDecodeError:
            pass
    # 截断的 {"rows":[{...},{... 半截 → 回收已完整的对象
    rows = _recover_rows_array(text)
    if rows is not None:
        return {"rows": rows}
    return None


def _recover_rows_array(raw: str) -> list[Any] | None:
    """从可能被截断的 JSON 文本中回收 rows 里已完整的对象。"""
    m = re.search(r'"rows"\s*:\s*\[', raw)
    if not m:
        return None
    i = m.end()
    n = len(raw)
    rows: list[Any] = []
    while i < n:
        while i < n and raw[i] in " \t\r\n,":
            i += 1
        if i >= n or raw[i] == "]":
            break
        if raw[i] != "{":
            break
        depth = 0
        in_str = False
        esc = False
        start = i
        while i < n:
            ch = raw[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        chunk = raw[start : i + 1]
                        try:
                            rows.append(json.loads(chunk))
                        except json.JSONDecodeError:
                            return rows or None
                        i += 1
                        break
            i += 1
        else:
            break
    return rows or None


def extract_bitable_payload(summary: str) -> dict[str, Any] | None:
    """从摘要中提取 bitable JSON；支持尾部截断时回收已完整的 rows。"""
    text = str(summary or "")
    if len(text) > MAX_BITABLE_SUMMARY_CHARS:
        text = truncate_summary_keep_bitable(text, MAX_BITABLE_SUMMARY_CHARS)
    candidates: list[str] = []
    for m in _BITABLE_TAG_RE.finditer(text):
        candidates.append(m.group(1).strip())
    for m in _BITABLE_FENCE_RE.finditer(text):
        candidates.append(m.group(1).strip())
    # 未闭合的 ```bitable_json（常因摘要截断）
    open_fence = re.search(r"```(?:bitable_json|json)\s*", text, re.IGNORECASE)
    if open_fence and not candidates:
        candidates.append(text[open_fence.end() :].strip())
    if not candidates:
        idx = text.rfind('"rows"')
        if idx >= 0:
            start = text.rfind("{", 0, idx)
            if start >= 0:
                candidates.append(text[start:])

    for raw in candidates:
        if len(raw) > MAX_BITABLE_SUMMARY_CHARS:
            raw = raw[:MAX_BITABLE_SUMMARY_CHARS]
        data = _loads_json_loose(raw)
        if isinstance(data, dict) and isinstance(data.get("rows"), list) and data["rows"]:
            # 硬顶行数，避免恶意超大 rows
            data = {**data, "rows": data["rows"][:MAX_BITABLE_ROWS]}
            return data
        if isinstance(data, list) and data:
            return {"rows": data[:MAX_BITABLE_ROWS]}
    return None


def truncate_summary_keep_bitable(text: str, max_len: int = 16000) -> str:
    """截断摘要时尽量保留 bitable_json 完整块，避免写表解析失败。"""
    raw = str(text or "").strip()
    if len(raw) <= max_len:
        return raw
    m = re.search(r"```(?:bitable_json|json)\s*[\s\S]*?```", raw, re.IGNORECASE)
    if m:
        block = m.group(0)
        if len(block) >= max_len - 80:
            return block[:max_len]
        budget = max_len - len(block) - 8
        head = raw[: m.start()]
        if len(head) > budget:
            head = head[: max(0, budget)] + "\n…\n"
        return head + block
    # 无完整 fence：优先保留从 bitable_json / "rows" 起的尾部
    for marker in ("```bitable_json", '"rows"'):
        idx = raw.find(marker)
        if idx >= 0:
            tail = raw[idx:]
            if len(tail) >= max_len - 80:
                return raw[:40] + "\n…\n" + raw[-(max_len - 50) :]
            head_budget = max_len - len(tail) - 8
            head = raw[:idx]
            if len(head) > head_budget:
                head = head[: max(0, head_budget)] + "\n…\n"
            return head + tail
    return raw[:max_len]


def _to_feishu_value(key: str, value: Any) -> Any:
    if value is None or value == "":
        return None
    key_l = str(key or "").strip().lower()
    if (
        key_l in {"date", "日期", "业务日", "完工日"}
        or (isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", value.strip()))
    ):
        raw = str(value).strip()[:10]
        try:
            d = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return str(value)[:2000]
        dt = datetime(d.year, d.month, d.day)
        return int(dt.timestamp() * 1000)
    # 完工时间：保留完整字符串（含时分秒），不强行压成日期
    if key_l in {"完工时间", "完成时间", "结案时间", "end_time", "finished_at"}:
        return str(value).strip()[:2000]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        s = _clean_text(value, 2000)
        if not s:
            return None
        if re.match(r"^-?\d+(\.\d+)?$", s):
            return float(s) if "." in s else int(s)
        return s
    if isinstance(value, (list, dict)):
        return _clean_text(json.dumps(value, ensure_ascii=False), 2000) or None
    return _clean_text(value, 2000) or None


def infer_field_spec(column: str, sample: Any) -> dict[str, Any]:
    """按列名/样例值推断飞书字段类型（缺列自动创建用）。"""
    name = str(column or "").strip()
    if name in DESIRED_FIELD_SPECS:
        return dict(DESIRED_FIELD_SPECS[name])
    if name.endswith("日期") or name in {"日期", "业务日", "完工日"} or str(column) in {"date"}:
        return {"type": 5, "property": {"date_formatter": "yyyy/MM/dd"}}
    if isinstance(sample, bool):
        return {"type": 1}
    if isinstance(sample, (int, float)) and not (
        isinstance(sample, (int, float)) and sample > 10_000_000_000
    ):
        return {"type": 2}
    if isinstance(sample, str) and re.match(r"^\d{4}-\d{2}-\d{2}", sample.strip()):
        return {"type": 5, "property": {"date_formatter": "yyyy/MM/dd"}}
    if isinstance(sample, str) and re.match(r"^-?\d+(\.\d+)?$", sample.strip()):
        return {"type": 2}
    # 含「率/量/数/合计」且样例像数字 → 数字列
    if any(x in name for x in ("率", "量", "数", "合计", "在制", "未完工")) and isinstance(
        sample, (int, float)
    ):
        return {"type": 2}
    return {"type": 1}


def _clean_text(value: Any, max_len: int) -> str:
    text = str(value or "")
    # 去掉控制字符，避免异常字节写入飞书/落库
    text = "".join(ch for ch in text if ord(ch) >= 32 or ch in "\t\n\r")
    return text.strip()[:max_len]


def _fmt_wo_end_time(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and float(value) > 1e11:
        try:
            return datetime.fromtimestamp(float(value) / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
        except (OverflowError, OSError, ValueError):
            return None
    text = _clean_text(value, 64)
    if not text:
        return None
    return text.replace("T", " ")[:19]


def _wo_order_no(row: dict[str, Any]) -> str:
    for k in ("工单号", "order_no", "orderNo", "wo_no"):
        v = row.get(k)
        if v is not None and str(v).strip():
            return _clean_text(v, _MAX_ORDER_NO_LEN)
    return ""


def _looks_like_work_order_row(row: dict[str, Any]) -> bool:
    """避免日报汇总行误触发 MES 回填。"""
    if not _wo_order_no(row):
        return False
    markers = (
        "产品",
        "料号",
        "产线",
        "计划量",
        "完工量",
        "状态",
        "product_name",
        "product_code",
        "plan_quantity",
        "actual_quantity",
        "status",
        "production_line",
    )
    return any(k in row for k in markers)


def fetch_work_order_lookup(limit: int = 200) -> dict[str, dict[str, Any]]:
    """从 MES 拉已完成工单，按工单号建索引（用于补全工序/完工时间）。"""
    limit = max(1, min(int(limit or 200), 500))
    try:
        from tools.platform_api import get_client
    except Exception:
        return {}
    try:
        client = get_client()
        out = client.query("work-orders", filters={"status": "completed"}, limit=limit)
    except Exception:
        return {}
    if not isinstance(out, dict) or out.get("error"):
        return {}
    records = out.get("records") if isinstance(out.get("records"), list) else []
    index: dict[str, dict[str, Any]] = {}
    for rec in records[:limit]:
        if not isinstance(rec, dict):
            continue
        no = _clean_text(rec.get("order_no"), _MAX_ORDER_NO_LEN)
        if no:
            index[no] = rec
    return index


def enrich_work_order_rows(rows: list[Any]) -> list[dict[str, Any]]:
    """Agent 常漏写工序/完工时间时，按工单号从 MES 回填 current_process / actual_end_time。"""
    normalized: list[dict[str, Any]] = [
        r for r in rows[:MAX_BITABLE_ROWS] if isinstance(r, dict)
    ]
    if not normalized:
        return []
    need_rows = [
        r
        for r in normalized
        if _looks_like_work_order_row(r)
        and (
            not str(r.get("工序") or "").strip()
            or not str(r.get("完工时间") or "").strip()
        )
    ]
    if not need_rows:
        return normalized
    lookup = fetch_work_order_lookup()
    if not lookup:
        return normalized
    filled: list[dict[str, Any]] = []
    for row in normalized:
        item = dict(row)
        if not _looks_like_work_order_row(item):
            filled.append(item)
            continue
        no = _wo_order_no(item)
        src = lookup.get(no) if no else None
        if src:
            if not str(item.get("工序") or "").strip():
                proc = src.get("current_process") or src.get("process")
                cleaned = _clean_text(proc, 64) if proc is not None else ""
                if cleaned:
                    item["工序"] = cleaned
            if not str(item.get("完工时间") or "").strip():
                end = _fmt_wo_end_time(src.get("actual_end_time")) or _fmt_wo_end_time(
                    src.get("end_date")
                )
                if end:
                    item["完工时间"] = end
        filled.append(item)
    return filled


def map_rows_to_records(
    rows: list[Any],
    field_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """rows → [{fields: {列名: 值}}]。

    查什么写什么：以每行对象的键为列名；field_map / DEFAULT_FIELD_MAP 仅作英文键别名，不限制列集合。
    """
    aliases = dict(DEFAULT_FIELD_MAP)
    if isinstance(field_map, dict):
        for k, v in field_map.items():
            ks = str(k or "").strip()
            vs = str(v or "").strip()
            if ks and vs:
                aliases[ks] = vs

    records: list[dict[str, Any]] = []
    for row in rows[:MAX_BITABLE_ROWS]:
        if not isinstance(row, dict):
            continue
        fields: dict[str, Any] = {}
        # 优先保留 actual_end_time 覆盖 end_date
        items = list(row.items())
        items.sort(key=lambda kv: 0 if str(kv[0]) == "actual_end_time" else 1)
        for src_raw, raw_val in items:
            src = str(src_raw or "").strip()
            if not src or src.startswith("_"):
                continue
            col = str(aliases.get(src) or src).strip()[:64]
            if not col:
                continue
            val = _to_feishu_value(col if col in {"完工时间", "工序"} else src, raw_val)
            if val is None:
                continue
            if col == "完工时间":
                val = _fmt_wo_end_time(val) or val
            if isinstance(val, str):
                val = _clean_text(val, 2000)
                if not val:
                    continue
            if col not in fields and len(fields) >= MAX_BITABLE_COLS:
                continue
            # 已有完工时间时，不要被 end_date 空值/粗粒度覆盖
            if col in fields and col == "完工时间" and src == "end_date":
                continue
            fields[col] = val
        if fields:
            records.append({"fields": fields})
    return records


def yesterday_iso() -> str:
    from datetime import timedelta

    return (date.today() - timedelta(days=1)).isoformat()
