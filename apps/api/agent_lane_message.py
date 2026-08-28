"""对话入模前的车道上下文与强制路由注入（无 LLM，便于编排单测）。

从 agent_wrapper._build_message 抽出，避免测试依赖 langchain。
"""
from __future__ import annotations

from workbuddy_lanes import (
    LANE_CODE_DEV,
    LANE_CODE_REVIEW,
    LANE_PASTE_CODE,
    resolve_workbuddy_lane,
)


def platform_context_bits(message: str = "", ctx: dict | None = None) -> list[str]:
    """拼入「[平台上下文]」的 key=value 片段。"""
    ctx = ctx or {}
    if ctx.get("automation_run"):
        bits = ["automation_run=1"]
        aid = str(ctx.get("automation_id") or "").strip()
        if aid:
            bits.append(f"automation_id={aid}")
        return bits
    bits: list[str] = []
    if ctx.get("entity"):
        bits.append(f"entity={ctx['entity']}")
    if ctx.get("plan_no"):
        bits.append(f"plan_no={ctx['plan_no']}")
    if ctx.get("order_no"):
        bits.append(f"order_no={ctx['order_no']}")
    lane = resolve_workbuddy_lane(message or "", ctx)
    if lane == LANE_CODE_DEV:
        bits.append("workbuddy_lane=code_dev")
        repo = str(ctx.get("cursor_dev_repo") or "").strip()
        if repo:
            bits.append(f"cursor_dev_repo={repo}")
    elif lane == LANE_CODE_REVIEW:
        bits.append("workbuddy_lane=code_review")
        ide_root = str(ctx.get("ide_workspace_root") or "").strip()
        if ide_root:
            bits.append(f"ide_workspace_root={ide_root}")
        git_url = str(ctx.get("git_repo_url") or "").strip()
        if git_url:
            bits.append(f"git_repo_url={git_url}")
        git_ref = str(ctx.get("git_ref") or "").strip()
        if git_ref:
            bits.append(f"git_ref={git_ref}")
    else:
        ide_root = str(ctx.get("ide_workspace_root") or "").strip()
        if ide_root:
            bits.append(f"ide_workspace_root={ide_root}")
        git_url = str(ctx.get("git_repo_url") or "").strip()
        if git_url:
            bits.append(f"git_repo_url={git_url}")
        git_ref = str(ctx.get("git_ref") or "").strip()
        if git_ref:
            bits.append(f"git_ref={git_ref}")
    return bits


def format_platform_context_prefix(bits: list[str]) -> str:
    if not bits:
        return ""
    if any(b.startswith("automation_run=") for b in bits):
        return (
            "[平台上下文] 本轮为**自动化任务调度执行**（非用户对话）。"
            "严格按任务「执行指令」产出摘要；禁止反问、禁止写码/提交/部署。\n\n"
        )
    return (
        "[平台上下文] 用户从 MES 页面打开助手，当前页："
        + "，".join(bits)
        + "。若问题指「这个/当前」计划或工单，优先用上述字段查询对应实体。\n\n"
    )


def format_automation_run_prefix(ctx: dict | None) -> str:
    """调度触发的自动化执行：强调按用户自定义指令执行，勿拒绝对未知任务类型。"""
    ctx = ctx or {}
    if not ctx.get("automation_run"):
        return ""
    return (
        "【自动化任务执行】本消息由定时调度触发；执行指令为用户在「自动化任务」页自定义内容，"
        "按字面含义完成并直接给出摘要。勿声称平台无定时能力；"
        "若指令仅为到点提醒且无查数步骤，输出简短提醒即可。\n\n"
    )


def append_lane_force_routes(message: str = "", ctx: dict | None = None) -> str:
    """在用户正文后追加本轮强制路由提示（写码 / 审核 / 贴码互斥）。"""
    ctx = ctx or {}
    body = message or ""
    if ctx.get("automation_run"):
        return body
    _git = str(ctx.get("git_repo_url") or "").strip()
    _ide = str(ctx.get("ide_workspace_root") or "").strip()
    lane = resolve_workbuddy_lane(body, ctx)
    if lane == LANE_PASTE_CODE:
        return (
            f"{body}\n\n【路由·贴码】Skill「paste-code-analyze」；禁止审核壳与写码卡。\n"
        )
    if lane == LANE_CODE_DEV:
        return (
            f"{body}\n\n【路由·写码】Skill「cursor-dev-chat」；默认 target=local（Cursor SDK）；"
            "禁止 request_git_* / request_ide_*。\n"
        )
    if lane == LANE_CODE_REVIEW and (
        _git
        or _ide
        or "【Git仓库已确认】" in body
        or "【本机工程已确认】" in body
    ):
        if _git or "【Git仓库已确认】" in body:
            return (
                f"{body}\n\n【路由·Git 审核】Skill「git-code-review」：list → read_batch(按序) → 终稿报告；"
                "禁止抽样 request_git_review。\n"
            )
        return (
            f"{body}\n\n【路由·IDE 审核】Skill「ide-code-review」：list → read_batch(按序) → 终稿报告。\n"
        )
    if lane is None and (_git or "【Git仓库已确认】" in body):
        return (
            f"{body}\n\n【路由·Git 审核】Skill「git-code-review」：list → read_batch → 终稿。\n"
        )
    return body


def compose_lane_user_text(message: str = "", ctx: dict | None = None) -> str:
    """平台上下文前缀 + 强制路由后的用户正文（不含 MES profile / 附件）。"""
    bits = platform_context_bits(message, ctx)
    prefix = format_automation_run_prefix(ctx) + format_platform_context_prefix(bits)
    body = append_lane_force_routes(message, ctx)
    return prefix + body
