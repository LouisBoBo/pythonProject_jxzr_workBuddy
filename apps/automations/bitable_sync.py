"""自动化运行结果 → 飞书多维表格（与企微 delivery 互不干涉）。"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from automations.bitable_writer import (
    enrich_work_order_rows,
    extract_bitable_payload,
    map_rows_to_records,
)
from automations.feishu_bitable import (
    app_id,
    app_secret,
    batch_create_records,
    bitable_enabled,
    normalize_app_token,
    normalize_table_id,
)

logger = logging.getLogger(__name__)


def get_bitable_config(automation: dict[str, Any]) -> dict[str, Any] | None:
    raw = automation.get("bitable_sync")
    if not isinstance(raw, dict):
        return None
    if not raw.get("enabled"):
        return None
    return raw


def sanitize_bitable_sync(raw: Any) -> dict[str, Any] | None:
    """清洗任务级 bitable_sync；非法则返回 None（表示清除）。"""
    if raw is None or raw is False:
        return None
    if not isinstance(raw, dict):
        return None
    enabled = bool(raw.get("enabled"))
    try:
        app_token = normalize_app_token(str(raw.get("app_token") or ""))
    except ValueError:
        app_token = ""
    try:
        table_id = normalize_table_id(str(raw.get("table_id") or ""))
    except ValueError:
        table_id = ""
    mode = str(raw.get("mode") or "append").strip().lower()
    if mode not in {"append", "upsert"}:
        mode = "append"
    fmap_raw = raw.get("field_map")
    field_map: dict[str, str] = {}
    if isinstance(fmap_raw, dict):
        for k, v in fmap_raw.items():
            ks = str(k or "").strip()[:64]
            vs = str(v or "").strip()[:64]
            if ks and vs:
                field_map[ks] = vs
    out = {
        "enabled": enabled,
        "app_token": app_token[:128],
        "table_id": table_id[:128],
        "mode": mode,
        "field_map": field_map,
    }
    return out


def sync_automation_run_to_bitable(
    data_dir: Path,
    automation: dict[str, Any],
    run_id: str,
    summary: str,
) -> dict[str, Any]:
    """写多维表格；返回 bitable_* 字段。与企微完全独立。"""
    del data_dir, run_id

    cfg = get_bitable_config(automation)
    if not cfg:
        return {
            "bitable_status": "skipped",
            "bitable_error": None,
            "bitable_record_ids": None,
            "bitable_synced_at": None,
        }

    if not bitable_enabled():
        return {
            "bitable_status": "skipped",
            "bitable_error": "FEISHU_BITABLE_ENABLED=0，请在系统配置开启飞书多维表格同步",
            "bitable_record_ids": None,
            "bitable_synced_at": None,
        }

    if not app_id() or not app_secret():
        return {
            "bitable_status": "skipped",
            "bitable_error": "未配置 FEISHU_APP_ID / FEISHU_APP_SECRET",
            "bitable_record_ids": None,
            "bitable_synced_at": None,
        }

    app_token = str(cfg.get("app_token") or "").strip()
    table_id = str(cfg.get("table_id") or "").strip()
    if not app_token or not table_id:
        return {
            "bitable_status": "failed",
            "bitable_error": "任务未配置 app_token 或 table_id",
            "bitable_record_ids": None,
            "bitable_synced_at": None,
        }

    from automations.bitable_writer import MAX_BITABLE_SUMMARY_CHARS, truncate_summary_keep_bitable

    raw_summary = str(summary or "")
    if len(raw_summary) > MAX_BITABLE_SUMMARY_CHARS:
        raw_summary = truncate_summary_keep_bitable(raw_summary, MAX_BITABLE_SUMMARY_CHARS)

    payload = extract_bitable_payload(raw_summary)
    if not payload:
        return {
            "bitable_status": "failed",
            "bitable_error": "摘要中未找到 bitable_json（请确认指令含多维表格输出块）",
            "bitable_record_ids": None,
            "bitable_synced_at": None,
        }

    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    # Agent 常误判「接口无工序/完工时间」而漏写；写表前按工单号从 MES 回填
    rows = enrich_work_order_rows(rows)
    field_map = cfg.get("field_map") if isinstance(cfg.get("field_map"), dict) else None
    records = map_rows_to_records(rows, field_map)
    if not records:
        return {
            "bitable_status": "failed",
            "bitable_error": "bitable_json.rows 为空或字段映射后无有效列",
            "bitable_record_ids": None,
            "bitable_synced_at": None,
        }

    # P0 仅 append；upsert 留待 P1
    result = batch_create_records(app_token=app_token, table_id=table_id, records=records)
    if result.get("ok"):
        ids = result.get("record_ids") if isinstance(result.get("record_ids"), list) else []
        logger.info(
            "bitable sync ok automation=%s count=%s dry_run=%s",
            automation.get("id"),
            len(ids) or len(records),
            result.get("dry_run"),
        )
        return {
            "bitable_status": "sent",
            "bitable_error": None,
            "bitable_record_ids": ids[:20],
            "bitable_synced_at": int(time.time()),
        }

    errmsg = str(result.get("msg") or "写飞书多维表格失败")[:500]
    logger.warning("bitable sync failed automation=%s: %s", automation.get("id"), errmsg)
    return {
        "bitable_status": "failed",
        "bitable_error": errmsg,
        "bitable_record_ids": None,
        "bitable_synced_at": None,
    }
