"""打开 WorkBuddy 时按日自动刷新资料包 OpenAPI（用户无感）。

触发：API 启动、拉取 MES 接入状态时。
策略：每个资料包每天成功同步至多一次；失败短冷却后可重试（本机 MES 晚于助手启动时仍能追上）。
仅 localhost；失败静默，不影响登录/对话。
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_STAMP_NAME = ".daily_openapi_sync.json"
_LOCK = threading.Lock()
_INFLIGHT = False
_FAIL_COOLDOWN_SEC = 15 * 60  # 失败后 15 分钟内不反复打 MES


def daily_sync_enabled() -> bool:
    raw = (
        os.getenv("MES_PROFILE_DAILY_SYNC", "true") or "true"
    ).strip().lower()
    return raw not in ("0", "false", "no", "off")


def _today() -> str:
    return date.today().isoformat()


def _stamp_path(pdir: Path) -> Path:
    return pdir / _STAMP_NAME


def _read_stamp(pdir: Path) -> dict[str, Any]:
    path = _stamp_path(pdir)
    if not path.is_file() or path.stat().st_size <= 0:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_stamp(pdir: Path, payload: dict[str, Any]) -> None:
    path = _stamp_path(pdir)
    tmp = path.with_suffix(".tmp")
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _should_run(pdir: Path) -> tuple[bool, str]:
    if not daily_sync_enabled():
        return False, "disabled"
    stamp = _read_stamp(pdir)
    today = _today()
    if stamp.get("ok") and str(stamp.get("date") or "") == today:
        return False, "already_synced_today"
    last_fail = str(stamp.get("last_attempt_iso") or "").strip()
    if last_fail and not stamp.get("ok"):
        try:
            # 仅对「今天失败」做冷却；跨日清掉逻辑靠 date 不等
            if str(stamp.get("date") or "") == today:
                ts = datetime.fromisoformat(last_fail.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    age = (datetime.now() - ts).total_seconds()
                else:
                    age = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
                if age < _FAIL_COOLDOWN_SEC:
                    return False, "fail_cooldown"
        except Exception:
            pass
    return True, "run"


def maybe_daily_sync_openapi(*, force: bool = False) -> dict[str, Any]:
    """若需要则同步；同步执行（调用方应放后台线程）。"""
    global _INFLIGHT
    from mes_profile import active_profile_id, profile_dir

    pid = active_profile_id()
    if not pid:
        return {"ok": False, "skipped": True, "reason": "no_profile"}
    pdir = profile_dir(pid)
    if pdir is None or not pdir.is_dir():
        return {"ok": False, "skipped": True, "reason": "no_profile_dir"}

    if not force:
        run, reason = _should_run(pdir)
        if not run:
            return {"ok": True, "skipped": True, "reason": reason, "profile_id": pid}

    with _LOCK:
        if _INFLIGHT and not force:
            return {"ok": True, "skipped": True, "reason": "inflight", "profile_id": pid}
        _INFLIGHT = True

    try:
        from mes_profile_refresh import refresh_mes_profile_from_runtime

        t0 = time.monotonic()
        out = refresh_mes_profile_from_runtime("")
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        now_iso = datetime.now(timezone.utc).isoformat()
        if out.get("ok"):
            added = out.get("added") or []
            _write_stamp(
                pdir,
                {
                    "date": _today(),
                    "ok": True,
                    "profile_id": pid,
                    "entity_count": out.get("entity_count"),
                    "added": added[:40],
                    "fetched_from": out.get("fetched_from"),
                    "elapsed_ms": elapsed_ms,
                    "synced_at": now_iso,
                    "source": "daily_open",
                },
            )
            logger.info(
                "MES 资料包日同步成功 profile=%s entities=%s added=%s",
                pid,
                out.get("entity_count"),
                len(added),
            )
            return {
                "ok": True,
                "skipped": False,
                "profile_id": pid,
                "entity_count": out.get("entity_count"),
                "added": added,
                "elapsed_ms": elapsed_ms,
            }

        _write_stamp(
            pdir,
            {
                "date": _today(),
                "ok": False,
                "profile_id": pid,
                "error": str(out.get("error") or "refresh failed")[:300],
                "last_attempt_iso": now_iso,
                "elapsed_ms": elapsed_ms,
                "source": "daily_open",
            },
        )
        logger.info(
            "MES 资料包日同步跳过/失败 profile=%s err=%s",
            pid,
            out.get("error"),
        )
        return {
            "ok": False,
            "skipped": False,
            "profile_id": pid,
            "error": out.get("error"),
            "elapsed_ms": elapsed_ms,
        }
    except Exception as exc:  # noqa: BLE001
        try:
            _write_stamp(
                pdir,
                {
                    "date": _today(),
                    "ok": False,
                    "profile_id": pid,
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                    "last_attempt_iso": datetime.now(timezone.utc).isoformat(),
                    "source": "daily_open",
                },
            )
        except Exception:
            pass
        logger.warning("MES 资料包日同步异常: %s", exc)
        return {"ok": False, "skipped": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        with _LOCK:
            _INFLIGHT = False


def schedule_daily_sync_openapi(*, force: bool = False, delay_sec: float = 0.0) -> None:
    """后台线程调度；不阻塞请求。"""
    if not daily_sync_enabled() and not force:
        return

    def _run() -> None:
        if delay_sec > 0:
            time.sleep(delay_sec)
        try:
            maybe_daily_sync_openapi(force=force)
        except Exception as exc:  # noqa: BLE001
            logger.warning("schedule_daily_sync_openapi: %s", exc)

    threading.Thread(target=_run, name="mes-daily-openapi-sync", daemon=True).start()
