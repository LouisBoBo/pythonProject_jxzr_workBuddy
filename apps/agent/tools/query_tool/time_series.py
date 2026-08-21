"""时间维序列（M1-4）：按日/周 bucket 生成 categories/values，供折线图使用。

原则：
- 不写死厂实体 / 字段名；时间列靠入参 + analysis.time_field_hints + 启发式
- 无可靠日期列 → 诚实 error/caveat，禁止编造日期轴
- 默认对「窗口内无记录」的 bucket 填 0，并标明本页抽样口径
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Literal

Grain = Literal["day", "week"]

_CAVEAT_PAGE = (
    "趋势由本次返回记录按时间字段分桶（本页抽样），不是全库时间序列；"
    "无记录日期计为 0，勿当全厂产量曲线。"
)


def _parse_to_date(raw: Any) -> date | None:
    """尽量解析常见 MES 日期/时间；解析不了返回 None。"""
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, (int, float)):
        # 可疑时间戳：秒或毫秒
        try:
            n = float(raw)
            if n > 1e12:  # ms
                n = n / 1000.0
            if 1e9 <= n < 1e11:
                return datetime.fromtimestamp(n).date()
        except (OSError, OverflowError, ValueError):
            return None
        return None
    s = str(raw).strip()
    if not s:
        return None
    # 截断时区/毫秒常见形态
    for cut in ("T", " "):
        if cut in s and len(s) >= 10:
            head = s.split(cut, 1)[0]
            if len(head) >= 10:
                try:
                    return date.fromisoformat(head[:10])
                except ValueError:
                    pass
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        pass
    for fmt in ("%Y/%m/%d", "%Y%m%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s[:10] if len(s) >= 10 and fmt != "%Y%m%d" else s[:8], fmt).date()
        except ValueError:
            continue
    return None


def resolve_time_field(
    available: list[str],
    *,
    requested: str | None = None,
    hints: list[str] | None = None,
) -> str | None:
    """把用户/配置说法映射到记录里真实存在的时间列。"""
    avail = [str(k) for k in available if str(k).strip()]
    folded = {k.lower().replace("-", "").replace("_", ""): k for k in avail}
    if requested and str(requested).strip():
        raw = str(requested).strip()
        if raw in avail:
            return raw
        key = raw.lower().replace("-", "").replace("_", "")
        if key in folded:
            return folded[key]
        # 仅精确/折叠匹配，禁止子串误绑（如 "at" → created_at）
        return None
    for h in hints or []:
        name = str(h or "").strip()
        if not name:
            continue
        if name in avail:
            return name
        key = name.lower().replace("-", "").replace("_", "")
        if key in folded:
            return folded[key]
    # 启发式：完工/结束优先，再通用 date/_at
    prefer_toks = ("end_date", "finish", "complete", "closed_at", "output_date", "prod_date")
    for k in avail:
        n = k.lower().replace("-", "_")
        if any(t in n for t in prefer_toks):
            return k
    for k in avail:
        n = k.lower()
        if "date" in n or n.endswith("_at") or n.endswith("time") or n.endswith("_time"):
            if "create" in n or "update" in n:
                continue
            return k
    for k in avail:
        n = k.lower()
        if "date" in n or n.endswith("_at"):
            return k
    return None


def _bucket_key(d: date, grain: Grain) -> str:
    if grain == "week":
        iso = d.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return d.isoformat()


def _window_keys(
    *,
    grain: Grain,
    window: int,
    today: date,
) -> list[str]:
    window = max(1, min(int(window), 90 if grain == "day" else 52))
    if grain == "day":
        return [(today - timedelta(days=i)).isoformat() for i in range(window - 1, -1, -1)]
    monday = today - timedelta(days=today.weekday())
    return [
        _bucket_key(monday - timedelta(weeks=i), "week")
        for i in range(window - 1, -1, -1)
    ]


def build_time_series(
    records: list[Any],
    *,
    time_field: str | None = None,
    value_field: str | None = None,
    grain: str = "day",
    window: int = 7,
    today: date | None = None,
    time_field_hints: list[str] | None = None,
    fill_zeros: bool = True,
) -> dict[str, Any]:
    """从记录生成时间序列。value_field 为空则按条数计数，否则对该字段求和。"""
    g: Grain = "week" if str(grain).lower() in ("week", "weekly", "周", "周度") else "day"
    today_d = today or date.today()
    rows = [r for r in records if isinstance(r, dict)]
    keys_avail: list[str] = []
    for rec in rows:
        for k in rec.keys():
            ks = str(k)
            if ks not in keys_avail:
                keys_avail.append(ks)

    tf = resolve_time_field(
        keys_avail,
        requested=time_field,
        hints=time_field_hints,
    )
    if not tf:
        return {
            "error": "记录中没有可解析的时间字段，无法做趋势分桶。",
            "available_fields": keys_avail,
            "hint": (
                "请在资料包 analysis.json 配置 time_field_hints，"
                "或调用时传入 time_field=真实列名；不要编造日期轴。"
            ),
            "caveats": ["无时间字段，禁止绘制「最近 N 天」假趋势。"],
        }

    vf = (str(value_field).strip() if value_field else "") or None
    if vf and vf not in keys_avail:
        # 宽松：大小写无关
        folded = {k.lower(): k for k in keys_avail}
        vf = folded.get(vf.lower())
        if not vf:
            return {
                "error": f"数值字段 {value_field!r} 不在本次记录中。",
                "available_fields": keys_avail,
                "time_field": tf,
            }

    buckets: dict[str, float] = defaultdict(float)
    skipped_bad = 0
    skipped_out = 0
    used = 0
    window_keys = _window_keys(grain=g, window=window, today=today_d)
    window_set = set(window_keys)

    for rec in rows:
        d = _parse_to_date(rec.get(tf))
        if d is None:
            skipped_bad += 1
            continue
        bk = _bucket_key(d, g)
        if bk not in window_set:
            skipped_out += 1
            continue
        if vf:
            try:
                buckets[bk] += float(rec.get(vf) or 0)
            except (TypeError, ValueError):
                skipped_bad += 1
                continue
        else:
            buckets[bk] += 1.0
        used += 1

    cats: list[str] = []
    vals: list[float] = []
    for k in window_keys:
        if fill_zeros:
            cats.append(k)
            vals.append(float(buckets.get(k, 0.0)))
        elif k in buckets:
            cats.append(k)
            vals.append(float(buckets[k]))

    caveats: list[str] = [_CAVEAT_PAGE]
    if skipped_bad:
        caveats.append(f"有 {skipped_bad} 条时间/数值无法解析，已跳过。")
    if skipped_out:
        caveats.append(f"有 {skipped_out} 条不在最近窗口内，未计入。")
    if used == 0:
        caveats.append("窗口内无有效记录；折线可能全为 0，勿解读为真实零产量。")

    mode = "sum" if vf else "count"
    return {
        "ok": True,
        "grain": g,
        "window": len(window_keys),
        "time_field": tf,
        "value_field": vf,
        "mode": mode,
        "categories": cats,
        "values": vals,
        "points_with_data": sum(1 for v in vals if v != 0),
        "records_used": used,
        "records_scanned": len(rows),
        "caveats": caveats[:8],
        "reply_hint": (
            f"按「{tf}」{('求和 '+vf) if vf else '计数'}，grain={g}；"
            "列出 categories/values；必须复述 caveats。"
            "出图：render_analysis_chart(chart_type='line' 或 auto + user_intent 含趋势)。"
            "禁止编造未出现在 values 中的点。"
        ),
    }
