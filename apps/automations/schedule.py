"""自动化任务 RRULE / 单次调度计算（P0：DAILY / WEEKLY / once）。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

_WEEKDAY_MAP = {
    "MO": 0,
    "TU": 1,
    "WE": 2,
    "TH": 3,
    "FR": 4,
    "SA": 5,
    "SU": 6,
}


def _parse_iso_date(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if len(raw) == 10 and raw[4] == "-":
            return datetime.strptime(raw, "%Y-%m-%d")
        norm = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(norm)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except ValueError:
        return None


def _parse_rrule(rrule: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for seg in str(rrule or "").split(";"):
        seg = seg.strip()
        if not seg or "=" not in seg:
            continue
        key, val = seg.split("=", 1)
        out[key.strip().upper()] = val.strip()
    return out


def _within_valid_window(automation: dict[str, Any], when: datetime) -> bool:
    vf = _parse_iso_date(automation.get("valid_from"))
    vu = _parse_iso_date(automation.get("valid_until"))
    if vf and when < vf:
        return False
    if vu:
        end = vu.replace(hour=23, minute=59, second=59, microsecond=0)
        if when > end:
            return False
    return True


def _daily_next(when: datetime, hour: int, minute: int) -> datetime:
    candidate = when.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= when:
        candidate += timedelta(days=1)
    return candidate


def _weekly_next(when: datetime, hour: int, minute: int, byday: list[str]) -> datetime | None:
    allowed = {_WEEKDAY_MAP[d.strip().upper()] for d in byday if d.strip().upper() in _WEEKDAY_MAP}
    if not allowed:
        allowed = {0}
    probe = when.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if probe <= when:
        probe += timedelta(days=1)
        probe = probe.replace(hour=hour, minute=minute, second=0, microsecond=0)
    for _ in range(370):
        if probe.weekday() in allowed and probe > when:
            return probe
        probe += timedelta(days=1)
        probe = probe.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return None


def compute_next_run_at(automation: dict[str, Any], *, base: datetime | None = None) -> int | None:
    """计算下次执行时间（Unix 秒）。无法调度时返回 None。"""
    now = base or datetime.now()
    if str(automation.get("status") or "").lower() != "active":
        return None
    if not _within_valid_window(automation, now):
        return None

    schedule_type = str(automation.get("schedule_type") or "recurring").lower()
    if schedule_type == "once":
        dt = _parse_iso_date(automation.get("scheduled_at"))
        if dt is None or dt <= now:
            return None
        return int(dt.timestamp())

    parts = _parse_rrule(str(automation.get("rrule") or ""))
    freq = parts.get("FREQ", "DAILY").upper()
    hour = int(parts.get("BYHOUR", "9"))
    minute = int(parts.get("BYMINUTE", "0"))
    hour = max(0, min(23, hour))
    minute = max(0, min(59, minute))

    if freq == "DAILY":
        nxt = _daily_next(now, hour, minute)
    elif freq == "WEEKLY":
        byday = re.split(r",", parts.get("BYDAY", "MO"))
        nxt = _weekly_next(now, hour, minute, byday)
        if nxt is None:
            return None
    else:
        nxt = _daily_next(now, hour, minute)

    if not _within_valid_window(automation, nxt):
        return None
    return int(nxt.timestamp())


def enrich_automation_schedule(item: dict[str, Any]) -> dict[str, Any]:
    """写入/更新任务时补齐 next_run_at。"""
    out = dict(item)
    out["next_run_at"] = compute_next_run_at(out)
    return out


def should_run_now(automation: dict[str, Any], *, now_ts: int | None = None) -> bool:
    if str(automation.get("status") or "").lower() != "active":
        return False
    now = int(now_ts or datetime.now().timestamp())
    nra = automation.get("next_run_at")
    if not isinstance(nra, (int, float)):
        return False
    if int(nra) > now:
        return False
    last = automation.get("last_run_at")
    if isinstance(last, (int, float)) and int(last) >= int(nra):
        return False
    return _within_valid_window(automation, datetime.fromtimestamp(now))
