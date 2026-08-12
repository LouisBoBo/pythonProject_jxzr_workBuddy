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
from middleware.write_confirm import WriteConfirmMiddleware
from middleware.access_log_route import AccessLogRouteMiddleware
from middleware.host_path_guard import HostPathGuardMiddleware


def build_custom_middleware() -> list[Any]:
    """按环境变量组装自定义 middleware 列表（可为空）。

    - ENABLE_AUDIT_MIDDLEWARE=true（默认 true）：记录工具调用
    - ENABLE_ENTITY_GUARD=true（默认 false）：拦截明显选错实体的查询
    - REQUIRE_WRITE_CONFIRM=true（默认 true）：写工具须人工确认
    - 访问日志路由：始终启用，纠正对 .jsonl/.log 的误用工具
    - 本机绝对路径守卫：始终启用，拦截 /Users/... 等无效 read_file
    """
    stack: list[Any] = []

    # 最先纠正访问日志误路由，避免 read_file 打到虚拟 FS 外失败
    if os.getenv("ENABLE_ACCESS_LOG_ROUTE", "true").lower() in ("1", "true", "yes"):
        stack.append(AccessLogRouteMiddleware())

    # 拦截本机绝对路径（Desktop/ERP 工程），写码/闲聊误读会直接失败
    if os.getenv("ENABLE_HOST_PATH_GUARD", "true").lower() in ("1", "true", "yes"):
        stack.append(HostPathGuardMiddleware())

    if os.getenv("ENABLE_AUDIT_MIDDLEWARE", "true").lower() in ("1", "true", "yes"):
        stack.append(AuditToolMiddleware())

    if os.getenv("ENABLE_ENTITY_GUARD", "false").lower() in ("1", "true", "yes"):
        stack.append(EntityGuardMiddleware())

    # 写确认放在守卫之后：先拦错实体，再挂起写操作
    if os.getenv("REQUIRE_WRITE_CONFIRM", "true").lower() in ("1", "true", "yes"):
        stack.append(WriteConfirmMiddleware())

    return stack
