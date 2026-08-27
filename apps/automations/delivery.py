"""自动化运行结果 → 企业微信推送（P0：群机器人 Webhook）。"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from automations.run_summary_text import format_wecom_push
from automations.wecom_bot import push_enabled, send_push_with_retry, webhook_key

logger = logging.getLogger(__name__)


def automation_push_enabled(automation: dict[str, Any]) -> bool:
    return bool(automation.get("push_to_wecom"))


def deliver_automation_run(
    data_dir: Path,
    automation: dict[str, Any],
    run_id: str,
    summary: str,
    *,
    started_at: int | None = None,
) -> dict[str, Any]:
    """推送单次运行摘要；返回 delivery_* 字段供 update_run。"""
    del data_dir, run_id  # P1 outbox 会使用

    if not automation_push_enabled(automation):
        return {"delivery_status": "skipped", "delivery_error": None, "delivered_at": None}

    if not push_enabled():
        return {
            "delivery_status": "skipped",
            "delivery_error": "WECOM_PUSH_ENABLED=0，请在系统配置开启自动化结果推送",
            "delivered_at": None,
        }

    if not webhook_key():
        return {
            "delivery_status": "skipped",
            "delivery_error": "未配置群机器人 Webhook Key，请在系统配置 → 自动化任务推送 填写",
            "delivered_at": None,
        }

    name = str(automation.get("name") or "").strip()
    msgtype, content = format_wecom_push(summary, name, started_at=started_at)
    if not content:
        return {
            "delivery_status": "failed",
            "delivery_error": "摘要为空，无法推送",
            "delivered_at": None,
        }

    result = send_push_with_retry(msgtype, content)
    if result.get("ok"):
        logger.info(
            "wecom push ok automation=%s msgtype=%s dry_run=%s",
            automation.get("id"),
            msgtype,
            result.get("dry_run"),
        )
        return {
            "delivery_status": "sent",
            "delivery_error": None,
            "delivered_at": int(time.time()),
        }

    errmsg = str(result.get("errmsg") or "推送失败")[:500]
    if result.get("first_error"):
        errmsg = f"{errmsg}（首次：{result['first_error'][:120]}）"[:500]
    logger.warning("wecom push failed automation=%s: %s", automation.get("id"), errmsg)
    return {
        "delivery_status": "failed",
        "delivery_error": errmsg,
        "delivered_at": None,
    }
