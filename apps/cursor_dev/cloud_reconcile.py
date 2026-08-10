"""Cursor Cloud 与本地 job 状态对账：避免云端已完成、UI 仍卡在 running。"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def fetch_cloud_agent_status(agent_id: str, *, api_key: str | None = None) -> dict[str, Any]:
    """查询 Cloud Agent 状态。返回 {ok, status, error}。"""
    aid = (agent_id or "").strip()
    if not aid:
        return {"ok": False, "status": "", "error": "missing agent_id"}
    key = (api_key or os.getenv("CURSOR_API_KEY") or "").strip()
    if not key:
        return {"ok": False, "status": "", "error": "missing CURSOR_API_KEY"}
    try:
        import httpx

        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                f"https://api.cursor.com/v0/agents/{aid}",
                headers={"Authorization": f"Bearer {key}"},
            )
            if resp.status_code != 200:
                return {
                    "ok": False,
                    "status": "",
                    "error": f"http {resp.status_code}: {resp.text[:200]}",
                }
            data = resp.json() if resp.content else {}
            return {
                "ok": True,
                "status": str(data.get("status") or "").upper(),
                "raw": data,
                "error": "",
            }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": "", "error": str(exc)}


def fetch_cloud_assistant_summary(agent_id: str, *, api_key: str | None = None) -> str:
    """从 Cloud conversation 取最后一份完整助手摘要。"""
    aid = (agent_id or "").strip()
    key = (api_key or os.getenv("CURSOR_API_KEY") or "").strip()
    if not aid or not key:
        return ""
    try:
        import httpx

        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                f"https://api.cursor.com/v0/agents/{aid}/conversation",
                headers={"Authorization": f"Bearer {key}"},
            )
            if resp.status_code != 200:
                return ""
            data = resp.json() if resp.content else {}
            msgs = data.get("messages") or []
            best = ""
            for m in msgs:
                if not str(m.get("type") or "").startswith("assistant"):
                    continue
                text = str(m.get("text") or "").strip()
                if not text:
                    continue
                if "已完成" in text or text.startswith("##"):
                    best = text
                elif len(text) > len(best):
                    best = text
            for m in reversed(msgs):
                if not str(m.get("type") or "").startswith("assistant"):
                    continue
                text = str(m.get("text") or "").strip()
                if "已完成" in text or text.startswith("##"):
                    return text
            return best
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch conversation failed: %s", exc)
        return ""


def cloud_status_is_finished(status: str) -> bool:
    s = (status or "").upper()
    return s in {"FINISHED", "COMPLETED", "DONE", "SUCCEEDED", "SUCCESS"}


def reconcile_running_job_with_cloud(
    data_dir: Path,
    job_id: str,
    *,
    api_key: str | None = None,
) -> dict[str, Any] | None:
    """若本地仍 running/queued 但 Cloud 已结束，收尾为 idle_for_followup 并写入摘要。

    返回更新后的 job；无需对账则返回 None。
    """
    from . import jobs as job_store

    job = job_store.get_job(data_dir, job_id)
    if not job:
        return None
    if job.get("status") not in {"running", "queued", "creating_pr"}:
        return None
    agent_id = str(job.get("agent_id") or "").strip()
    if not agent_id:
        return None

    info = fetch_cloud_agent_status(agent_id, api_key=api_key)
    if not info.get("ok"):
        return None
    status = str(info.get("status") or "")
    if not cloud_status_is_finished(status):
        return None

    summary = fetch_cloud_assistant_summary(agent_id, api_key=api_key)
    if not summary:
        summary = "Cursor Cloud 已完成本轮写码（流式收尾中断，已从云端结果恢复）。"

    updated = job_store.update_job(
        data_dir,
        job_id,
        status="idle_for_followup",
        error=None,
        cancel_requested=False,
        agent_id=agent_id,
    )
    # 避免重复追加同一摘要
    msgs = list((updated or job).get("messages") or [])
    last_as = ""
    for m in reversed(msgs):
        if m.get("role") == "assistant":
            last_as = str(m.get("content") or "")
            break
    if summary[:200] not in last_as:
        job_store.append_message(data_dir, job_id, role="assistant", content=summary[:8000])
    return job_store.get_job(data_dir, job_id)
