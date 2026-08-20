"""枚举字段展示名：API 常为英文码，列表/图表应对齐中文标签。

查数 filters 仍传英文码；仅展示层（分组、表格单元格、图表类目）替换。
资料包 analysis.json 的 value_labels 可覆盖内置默认。
"""
from __future__ import annotations

from typing import Any

# 通用默认：与常见 MES 列表 UI 对齐；资料包可覆盖
_BUILTIN: dict[str, dict[str, str]] = {
    "status": {
        "pending": "待开工",
        "in_progress": "进行中",
        "completed": "已完成",
        "cancelled": "已取消",
        "canceled": "已取消",
        "closed": "已关闭",
        "draft": "草稿",
        "paused": "已暂停",
        "hold": "挂起",
    },
    "priority": {
        "urgent": "紧急",
        "high": "高",
        "normal": "普通",
        "medium": "中",
        "low": "低",
    },
}

_STATUS_FIELDS = frozenset(
    {
        "status",
        "state",
        "wo_status",
        "order_status",
        "plan_status",
        "bill_status",
    }
)
_PRIORITY_FIELDS = frozenset(
    {
        "priority",
        "pri",
        "urgency",
        "priority_level",
    }
)


def load_value_labels() -> dict[str, dict[str, str]]:
    """合并内置 ← analysis.json.value_labels。"""
    out: dict[str, dict[str, str]] = {
        k: dict(v) for k, v in _BUILTIN.items()
    }
    try:
        from tools.query_tool.analysis_config import load_analysis_config

        cfg = load_analysis_config()
        overlay = cfg.get("value_labels")
    except Exception:
        overlay = None
    if isinstance(overlay, dict):
        for role, mapping in overlay.items():
            if not isinstance(mapping, dict):
                continue
            key = str(role).strip().lower()
            bucket = out.setdefault(key, {})
            for raw, label in mapping.items():
                if raw is None or label is None:
                    continue
                bucket[str(raw).strip()] = str(label).strip()
    return out


def _role_for_field(field: str) -> str | None:
    f = str(field or "").strip().lower().replace("-", "_")
    if not f:
        return None
    if f in _STATUS_FIELDS or f.endswith("_status") or f.endswith("_state"):
        return "status"
    if f in _PRIORITY_FIELDS:
        return "priority"
    return None


def label_enum_value(
    field: str,
    value: Any,
    maps: dict[str, dict[str, str]] | None = None,
) -> str:
    """把枚举原始值换成中文展示；未知值原样返回。"""
    if value is None:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    role = _role_for_field(field)
    if not role:
        return raw
    mapping = (maps or load_value_labels()).get(role) or {}
    if raw in mapping:
        return mapping[raw]
    low = raw.lower()
    for k, v in mapping.items():
        if str(k).lower() == low:
            return v
    return raw
