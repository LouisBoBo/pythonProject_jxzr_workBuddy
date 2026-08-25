"""对话模型名硬闸：禁止高价误配（如 deepseek-v4-pro）。

默认拦截；应急可设 LLM_ALLOW_BLOCKED_MODELS=1 放行（不推荐）。
"""
from __future__ import annotations

import os
import re
from typing import Iterable

# 精确命中（小写比较）
_BLOCKED_EXACT = frozenset(
    {
        "deepseek-v4-pro",
    }
)

# 子串/模式命中（小写）：拦截 deepseek-*-pro / deepseek-vN-pro
_BLOCKED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^deepseek-.*-pro$"),
    re.compile(r"^deepseek-v\d+-pro$"),
)

_SUGGEST = "deepseek-v4-flash 或 deepseek-chat"


def _allow_blocked() -> bool:
    return os.getenv("LLM_ALLOW_BLOCKED_MODELS", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def normalize_model_name(name: str | None) -> str:
    return (name or "").strip()


def is_llm_model_blocked(name: str | None) -> bool:
    """是否在默认黑名单中（忽略放行开关）。"""
    raw = normalize_model_name(name)
    if not raw:
        return False
    low = raw.lower()
    if low in _BLOCKED_EXACT:
        return True
    return any(p.search(low) for p in _BLOCKED_PATTERNS)


def blocked_model_message(name: str | None, *, what: str = "对话模型") -> str:
    raw = normalize_model_name(name) or "(空)"
    return (
        f"已禁止使用高价{what}「{raw}」，避免误烧费用。"
        f"请在系统配置改为 {_SUGGEST}。"
        f"（应急放行：环境变量 LLM_ALLOW_BLOCKED_MODELS=1，不推荐）"
    )


def assert_llm_model_allowed(name: str | None, *, what: str = "对话模型") -> str:
    """校验模型名；非法则抛 ValueError。返回规范化名称（可为空串）。"""
    raw = normalize_model_name(name)
    if not raw:
        return raw
    if is_llm_model_blocked(raw) and not _allow_blocked():
        raise ValueError(blocked_model_message(raw, what=what))
    return raw


def assert_models_in_mapping(
    values: dict,
    keys: Iterable[str] = ("MAIN_MODEL", "MODEL_NAME"),
) -> None:
    """保存配置前批量校验。"""
    for key in keys:
        if key not in values:
            continue
        val = values.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if not text:
            continue
        assert_llm_model_allowed(text, what=f"配置项 {key}")
