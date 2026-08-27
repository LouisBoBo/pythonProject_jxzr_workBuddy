"""API 进程内自动化调度（30s tick）。"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_TASK: asyncio.Task | None = None
_TICK_SEC = 30.0


def scheduler_enabled() -> bool:
    raw = (os.getenv("AUTOMATIONS_SCHEDULER_ENABLED", "true") or "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _tick_seconds() -> float:
    raw = (os.getenv("AUTOMATIONS_TICK_SEC") or "30").strip()
    try:
        return max(5.0, float(raw))
    except ValueError:
        return _TICK_SEC


def _ensure_apps_path() -> None:
    apps = Path(__file__).resolve().parents[1]
    if str(apps) not in sys.path:
        sys.path.insert(0, str(apps))


async def _tick_once(data_dir: Path) -> None:
    from automations import store
    from automations.executor import execute_automation
    from automations.schedule import enrich_automation_schedule, should_run_now

    items = store.list_automations(data_dir)
    now = int(time.time())
    for item in items:
        cur = dict(item)
        if cur.get("next_run_at") is None and str(cur.get("status") or "") == "active":
            enriched = enrich_automation_schedule(cur)
            if enriched.get("next_run_at") is not None:
                store.update_automation(data_dir, cur["id"], {"next_run_at": enriched["next_run_at"]})
                cur["next_run_at"] = enriched["next_run_at"]
        if not should_run_now(cur, now_ts=now):
            continue
        logger.info("[automations] due task id=%s name=%s", cur.get("id"), cur.get("name"))
        result = await execute_automation(data_dir, cur)
        if result.get("skipped") and result.get("reason") == "stream_busy":
            logger.info("[automations] deferred id=%s (user stream busy)", cur.get("id"))
            continue


async def _loop(data_dir: Path) -> None:
    delay = _tick_seconds()
    logger.info("[automations] scheduler started tick=%ss data_dir=%s", delay, data_dir)
    await asyncio.sleep(2.0)
    while True:
        try:
            await _tick_once(data_dir)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[automations] tick failed: %s", exc)
        await asyncio.sleep(delay)


def schedule_automation_scheduler(data_dir: Path) -> None:
    """FastAPI startup 调用；失败不影响主服务。"""
    global _TASK
    if not scheduler_enabled():
        logger.info("[automations] scheduler disabled by AUTOMATIONS_SCHEDULER_ENABLED")
        return
    if _TASK is not None and not _TASK.done():
        return
    _ensure_apps_path()
    _TASK = asyncio.create_task(_loop(Path(data_dir)), name="automation-scheduler")
