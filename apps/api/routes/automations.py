"""自动化任务 API（定义 CRUD + 运行记录查询）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from routes_config import DATA_DIR
from routes.auth import require_auth

router = APIRouter(prefix="/api/automations", tags=["自动化任务"])


def _validate_valid_range(valid_from: str | None, valid_until: str | None) -> None:
    if valid_from and valid_until and valid_from > valid_until:
        raise HTTPException(status_code=400, detail="生效结束日期不能早于开始日期")


class AutomationCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="任务名称")
    prompt: str = Field(..., min_length=1, max_length=8000, description="执行指令（仅任务内容）")
    status: str = Field("active", description="状态：active 运行中 / paused 已暂停")
    schedule_type: str = Field("recurring", description="recurring 循环 / once 单次")
    rrule: str = Field("", max_length=500, description="循环规则 RRULE，如 FREQ=DAILY;BYHOUR=9;BYMINUTE=30")
    scheduled_at: str | None = Field(None, description="单次执行时间 ISO 8601")
    valid_from: str | None = Field(None, description="生效开始（可选）")
    valid_until: str | None = Field(None, description="生效结束（可选）")
    cwds: list[str] = Field(default_factory=list, description="工作目录列表")
    push_to_wecom: bool = Field(False, description="成功后推送到企业微信群机器人")
    bitable_sync: dict | None = Field(
        None,
        description="飞书多维表格同步配置（enabled/app_token/table_id/field_map）；与企微互不干涉",
    )


class AutomationUpdateBody(BaseModel):
    name: str | None = Field(None, max_length=120, description="任务名称")
    prompt: str | None = Field(None, max_length=8000, description="执行指令")
    status: str | None = Field(None, description="active / paused")
    schedule_type: str | None = Field(None, description="recurring / once")
    rrule: str | None = Field(None, max_length=500, description="RRULE")
    scheduled_at: str | None = Field(None, description="单次时间")
    valid_from: str | None = Field(None, description="生效开始")
    valid_until: str | None = Field(None, description="生效结束")
    cwds: list[str] | None = Field(None, description="工作目录")
    push_to_wecom: bool | None = Field(None, description="成功后推送到企业微信群机器人")
    bitable_sync: dict | None = Field(None, description="飞书多维表格同步配置")


def _store():
    import sys

    apps = Path(__file__).resolve().parents[2]
    if str(apps) not in sys.path:
        sys.path.insert(0, str(apps))
    from automations import store  # noqa: WPS433

    return store


@router.get(
    "",
    summary="自动化任务列表",
    description="返回当前用户可见的全部定时任务定义（按更新时间倒序）。",
)
def list_automations_api(_auth: tuple = Depends(require_auth)):
    store = _store()
    return {"ok": True, "items": store.list_automations(DATA_DIR)}


@router.get(
    "/runs",
    summary="自动化运行记录",
    description="分页返回自动化执行记录（按开始时间倒序）；用于运行记录页表格与总条数展示。",
)
def list_runs_api(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数，默认 10"),
    _auth: tuple = Depends(require_auth),
):
    store = _store()
    items, total = store.list_runs(DATA_DIR, page=page, page_size=page_size)
    return {"ok": True, "items": items, "total": total, "page": page, "page_size": page_size}


class AutomationRewritePromptBody(BaseModel):
    draft: str = Field(..., min_length=1, max_length=8000, description="用户草稿意图或待改写的执行指令")
    task_name: str = Field("", max_length=120, description="任务名称（可选，辅助理解意图）")


@router.post(
    "/rewrite-prompt",
    summary="AI 改写执行指令",
    description=(
        "自定义自动化任务时，基于指令骨架扩写用户草稿；"
        "不曲解意图，只让表述更清晰、更易被执行 Agent 理解。"
    ),
)
def rewrite_prompt_api(body: AutomationRewritePromptBody, _auth: tuple = Depends(require_auth)):
    from automations.prompt_rewrite import rewrite_automation_prompt

    try:
        prompt = rewrite_automation_prompt(body.draft, task_name=body.task_name or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        # 不回传上游原始异常细节（可能含 URL/密钥片段）
        msg = str(exc)
        if "未配置" in msg or "未返回" in msg:
            detail = msg
        else:
            detail = "AI 改写暂时不可用，请稍后重试或手工完善指令"
        raise HTTPException(status_code=502, detail=detail) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail="AI 改写暂时不可用，请稍后重试或手工完善指令",
        ) from exc
    return {"ok": True, "prompt": prompt}


@router.post(
    "",
    summary="创建自动化任务",
    description="新建定时任务定义；保存后由调度器按 rrule/scheduled_at 自动执行。",
)
def create_automation_api(body: AutomationCreateBody, _auth: tuple = Depends(require_auth)):
    _validate_valid_range(body.valid_from, body.valid_until)
    store = _store()
    item = store.create_automation(DATA_DIR, body.model_dump())
    return {"ok": True, "item": item}


@router.patch(
    "/{automation_id}",
    summary="更新自动化任务",
    description="修改名称、指令、调度规则或暂停/恢复任务。",
)
def update_automation_api(
    automation_id: str,
    body: AutomationUpdateBody,
    _auth: tuple = Depends(require_auth),
):
    store = _store()
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        item = store.get_automation(DATA_DIR, automation_id)
        if not item:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"ok": True, "item": item}
    existing = store.get_automation(DATA_DIR, automation_id)
    if not existing:
        raise HTTPException(status_code=404, detail="任务不存在")
    vf = fields.get("valid_from", existing.get("valid_from"))
    vu = fields.get("valid_until", existing.get("valid_until"))
    _validate_valid_range(vf, vu)
    item = store.update_automation(DATA_DIR, automation_id, fields)
    if not item:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"ok": True, "item": item}


@router.delete(
    "/{automation_id}",
    summary="删除自动化任务",
    description="永久删除任务定义（运行记录保留）。",
)
def delete_automation_api(automation_id: str, _auth: tuple = Depends(require_auth)):
    store = _store()
    if not store.delete_automation(DATA_DIR, automation_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"ok": True}


@router.post(
    "/{automation_id}/run",
    summary="立即执行自动化任务（测试）",
    description="手动触发一次执行（不等定时）；若当前有用户流式对话则返回 skipped。",
)
async def run_automation_now_api(automation_id: str, _auth: tuple = Depends(require_auth)):
    store = _store()
    item = store.get_automation(DATA_DIR, automation_id)
    if not item:
        raise HTTPException(status_code=404, detail="任务不存在")
    from automations.executor import execute_automation

    result = await execute_automation(DATA_DIR, item)
    return {"ok": True, **result}
