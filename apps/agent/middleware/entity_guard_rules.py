"""实体守卫纯规则（无 LangChain 依赖，可供冒烟脚本直接引用）。"""
from __future__ import annotations

_PLAN_HINTS = (
    "生产计划",
    "排产计划",
    "排程计划",
    "排产",
    "排程",
    "主生产计划",
    "production-plan",
    "production plan",
    "production plans",
)
_WO_HINTS = (
    "工单",
    "派工单",
    "生产工单",
    "制造工单",
    "工作订单",
    "在制工单",
    "异常工单",
    "紧急工单",
    "work order",
    "work-order",
    "workorders",
)

GUARD_TOOLS = frozenset(
    {
        "query_platform_data",
        "describe_entity",
        "export_platform_data",
        "import_file_to_platform",
    }
)


def detect_entity_hints(user_text: str) -> tuple[bool, bool]:
    """返回 (has_plan_hint, has_wo_hint)。"""
    if not user_text:
        return False, False
    text_l = user_text.lower()
    has_plan = any(h in user_text for h in _PLAN_HINTS) or any(
        h in text_l for h in ("production-plan", "production plan", "production plans")
    )
    has_wo = any(h in user_text for h in _WO_HINTS) or any(
        h in text_l for h in ("work order", "work-order", "workorders")
    )
    if not has_wo and ("WO-" in user_text or user_text.strip().upper() == "WO"):
        has_wo = True
    return has_plan, has_wo


def guard_mismatch_tip(entity: str, user_text: str) -> str | None:
    """若实体与用户说法明显冲突，返回提示文案；否则 None。"""
    has_plan, has_wo = detect_entity_hints(user_text)
    if entity == "work-orders" and has_plan and not has_wo:
        return (
            "实体守卫：用户在问生产计划/排产/排程，但工具参数用了 work-orders。"
            "请改用 entity='production-plans' 后重试，不要用工单数据充数。"
        )
    if entity == "production-plans" and has_wo and not has_plan:
        return (
            "实体守卫：用户在问工单，但工具参数用了 production-plans。"
            "请改用 entity='work-orders' 后重试，不要用计划数据充数。"
        )
    return None
