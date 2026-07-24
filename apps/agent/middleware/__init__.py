"""
自定义 Middleware 包。

Deep Agents 已内置 Skills / Filesystem / Summarization 等中间件；
这里放「你们业务自己的」横切逻辑（审计、守卫、配额等）。

启用方式见 agents/agent.py 与 docs/DeepAgents-Middleware使用指南.md。
"""
from __future__ import annotations

import os
from typing import Any

from middleware.audit_tools import AuditToolMiddleware
from middleware.entity_guard import EntityGuardMiddleware


def build_custom_middleware() -> list[Any]:
    """按环境变量组装自定义 middleware 列表（可为空）。

    - ENABLE_AUDIT_MIDDLEWARE=true（默认 true）：记录工具调用
    - ENABLE_ENTITY_GUARD=true（默认 false）：拦截明显选错实体的查询
    """
    stack: list[Any] = []

    if os.getenv("ENABLE_AUDIT_MIDDLEWARE", "true").lower() in ("1", "true", "yes"):
        stack.append(AuditToolMiddleware())

    if os.getenv("ENABLE_ENTITY_GUARD", "false").lower() in ("1", "true", "yes"):
        stack.append(EntityGuardMiddleware())

    return stack
