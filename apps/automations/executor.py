"""到点唤醒 Deep Agents 执行自动化指令。"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _is_weekly_work_report(automation: dict[str, Any]) -> bool:
    name = str(automation.get("name") or "")
    aid = str(automation.get("id") or "")
    prompt = str(automation.get("prompt") or "")
    keys = ("周报", "工作周报", "weekly-work-report", "weekly_work_report")
    return any(k in name or k in prompt or k in aid for k in keys)


def _is_daily_production_report(automation: dict[str, Any]) -> bool:
    name = str(automation.get("name") or "")
    aid = str(automation.get("id") or "")
    prompt = str(automation.get("prompt") or "")
    keys = (
        "生产运营日报",
        "生产日报",
        "mes-daily-production-report",
        "昨日生产",
    )
    return any(k in name or k in prompt or k in aid for k in keys)


def _daily_production_report_prefix() -> str:
    from datetime import date, timedelta

    from automations.production_report import DAILY_PRODUCTION_REPORT_OUTPUT_PREFIX

    today = date.today()
    yesterday = today - timedelta(days=1)
    return (
        f"【日期基准】今天 {today.isoformat()}，「昨日」= {yesterday.isoformat()}。\n"
        "查数时 filters / as_of 须用上述昨日日期；禁止臆造日期。\n"
        f"{DAILY_PRODUCTION_REPORT_OUTPUT_PREFIX}\n"
    )


def _weekly_report_prefix(cwds: list[str]) -> str:
    from automations.repo_digest import build_weekly_repo_digest

    digest = build_weekly_repo_digest(cwds[0] if cwds else None)
    return (
        digest
        + "\n\n"
        + "【周报输出要求】\n"
        "1. 只根据上方 git 提交与变更文件归纳「本周在 ZR WorkBuddy 新增/改动的功能」；必须真实，禁止编造。\n"
        "2. 禁止把 MES 查数、接口探活、写操作审计等运维操作写成「本周开发交付」（除非提交里明确是相关功能开发）。\n"
        "3. 若本周无提交，已完成工作写「本周仓库暂无新提交」，勿虚构功能点。\n"
        "4. 格式：一、已完成工作（编号列表）；二、进行中事项；三、下周计划。\n"
        "5. 每条已完成工作写清功能名 + 对应文件/提交要点；不要输出「数据说明」类元信息。\n\n"
    )


def _ensure_api_paths() -> None:
    apps = Path(__file__).resolve().parents[1]
    api = apps / "api"
    agent = apps / "agent"
    for p in (str(apps), str(api), str(agent)):
        if p not in sys.path:
            sys.path.insert(0, p)


async def execute_automation(data_dir: Path, automation: dict[str, Any]) -> dict[str, Any]:
    """执行单个自动化；若用户流式对话占用锁则 defer。"""
    from automations import runtime as rt
    from automations import store
    from automations.schedule import compute_next_run_at, enrich_automation_schedule

    automation_id = str(automation.get("id") or "")
    run_id = f"run-{uuid.uuid4().hex[:16]}"
    started = int(time.time())
    thread_id = f"automation-{automation_id}-{run_id}"

    if not rt.mark_running(data_dir, automation_id, run_id):
        return {"ok": False, "skipped": True, "reason": "already_running"}

    cwds_raw = automation.get("cwds") or []
    if isinstance(cwds_raw, list):
        cwds = [str(p).strip() for p in cwds_raw if str(p).strip()][:8]
    else:
        cwds = []

    run_rec = store.append_run(
        data_dir,
        {
            "automation_id": automation_id,
            "automation_name": automation.get("name") or "",
            "status": "running",
            "started_at": started,
            "thread_id": thread_id,
            "cwd": cwds[0] if cwds else None,
        },
    )

    _ensure_api_paths()
    from agent_wrapper import AgentRunner
    from middleware.request_context import reset_request_agent_context, set_request_agent_context
    from stream_concurrency import try_acquire_stream_lock

    runner = AgentRunner()
    lock = runner._get_stream_lock()
    acquired = await try_acquire_stream_lock(lock, wait_sec=0.0)
    if not acquired:
        rt.clear_running(data_dir, automation_id, run_id)
        store.update_run(data_dir, run_rec["id"], status="failed", error="用户对话进行中，本轮跳过", finished_at=int(time.time()))
        return {"ok": False, "skipped": True, "reason": "stream_busy"}

    page_context: dict[str, Any] = {
        "automation_run": True,
        "source": "scheduler",
        "automation_id": automation_id,
    }
    if cwds:
        page_context["automation_cwds"] = cwds

    ctx = set_request_agent_context(
        thread_id=thread_id,
        user_id="automation",
        username="automation",
        page_context=page_context,
    )
    summary = ""
    err: str | None = None
    status = "failed"
    try:
        prompt = str(automation.get("prompt") or "").strip()
        if not prompt:
            err = "任务缺少执行指令"
        else:
            prefix = (
                "【自动化任务】请按指令完成任务并直接给出结果摘要；"
                "执行指令为用户自定义内容，按字面含义执行，勿因不在内置模板而拒绝；"
                "不要反问用户，不要发起写码/提交/部署等需人工确认的操作。\n"
            )
            if _is_weekly_work_report(automation):
                prefix += _weekly_report_prefix(cwds)
            if _is_daily_production_report(automation):
                prefix += _daily_production_report_prefix()
            bitable_cfg = automation.get("bitable_sync")
            if isinstance(bitable_cfg, dict) and bitable_cfg.get("enabled"):
                from automations.bitable_writer import BITABLE_JSON_INSTRUCTION

                prefix += BITABLE_JSON_INSTRUCTION + "\n"
            if cwds:
                prefix += f"【工作目录】{', '.join(cwds)}\n"
            prefix += "\n"
            reply = await runner.chat(prefix + prompt, thread_id=thread_id)
            # 完整回复留给写表；落库/企微再用 truncate 保住 bitable_json
            summary = (reply or "").strip()
            status = "succeeded" if summary else "failed"
            if not summary:
                err = "Agent 未返回有效摘要"
    except Exception as exc:  # noqa: BLE001
        logger.warning("automation execute failed id=%s: %s", automation_id, exc)
        err = str(exc)[:2000]
        status = "failed"
    finally:
        reset_request_agent_context(ctx)
        lock.release()
        rt.clear_running(data_dir, automation_id, run_id)

    from automations.bitable_writer import truncate_summary_keep_bitable

    stored_summary = truncate_summary_keep_bitable(summary, 16000) if summary else ""
    finished = int(time.time())
    store.update_run(
        data_dir,
        run_rec["id"],
        status=status,
        finished_at=finished,
        summary=stored_summary,
        error=err,
    )

    delivery_fields: dict[str, Any] = {}
    bitable_fields: dict[str, Any] = {}
    if status == "succeeded" and summary:
        # 企微与飞书写表并列、互不依赖：任一段异常不影响另一段
        try:
            from automations.delivery import deliver_automation_run

            delivery_fields = deliver_automation_run(
                data_dir,
                automation,
                run_rec["id"],
                stored_summary,
                started_at=started,
            )
            if delivery_fields.get("delivery_status"):
                store.update_run(data_dir, run_rec["id"], **delivery_fields)
        except Exception as exc:  # noqa: BLE001
            logger.warning("wecom delivery error id=%s: %s", automation_id, exc)
            delivery_fields = {
                "delivery_status": "failed",
                "delivery_error": str(exc)[:500],
            }
            store.update_run(data_dir, run_rec["id"], **delivery_fields)

        try:
            from automations.bitable_sync import sync_automation_run_to_bitable

            # 必须用未截断的 summary，否则多行 bitable_json 会被砍断
            bitable_fields = sync_automation_run_to_bitable(
                data_dir,
                automation,
                run_rec["id"],
                summary,
            )
            if bitable_fields.get("bitable_status"):
                store.update_run(data_dir, run_rec["id"], **bitable_fields)
        except Exception as exc:  # noqa: BLE001
            logger.warning("bitable sync error id=%s: %s", automation_id, exc)
            bitable_fields = {
                "bitable_status": "failed",
                "bitable_error": str(exc)[:500],
            }
            store.update_run(data_dir, run_rec["id"], **bitable_fields)

    fields: dict[str, Any] = {"last_run_at": finished}
    updated = dict(automation)
    updated["last_run_at"] = finished
    if str(automation.get("schedule_type") or "") == "once":
        fields["status"] = "paused"
        fields["next_run_at"] = None
    else:
        fields["next_run_at"] = compute_next_run_at(updated, base=datetime.fromtimestamp(finished))
    store.update_automation(data_dir, automation_id, fields)

    return {
        "ok": status == "succeeded",
        "run_id": run_rec["id"],
        "status": status,
        "summary": stored_summary,
        "error": err,
        **delivery_fields,
        **bitable_fields,
    }
