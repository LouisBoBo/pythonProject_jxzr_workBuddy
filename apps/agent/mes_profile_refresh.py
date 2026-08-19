"""从运行中的本机 MES 刷新资料包接口目录（Agent 工具入口）。"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _is_localhost_url(url: str) -> bool:
    """仅允许 loopback（127.0.0.1 / ::1 / localhost）。"""
    import ipaddress
    import socket

    from safe_http import assert_http_url_allowed

    try:
        text = assert_http_url_allowed(url, what="MES 接口文档")
        host = (urlparse(text).hostname or "").strip().lower()
    except ValueError:
        return False
    if not host:
        return False
    if host in {"localhost", "localhost.localdomain"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
        return bool(ip.is_loopback)
    except ValueError:
        pass
    try:
        for info in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM):
            addr = info[4][0]
            try:
                if not ipaddress.ip_address(addr).is_loopback:
                    return False
            except ValueError:
                return False
        return True
    except OSError:
        return False


def refresh_mes_profile_from_runtime(
    docs_url: str = "",
) -> dict[str, Any]:
    """从本机运行中的 MES 拉 OpenAPI，合并更新 entities.json（保留既有实体与 api_base）。

    docs_url 可填 /docs 或 /openapi.json；默认用资料包 meta.api_base。
    仅允许 127.0.0.1 / localhost。
    """
    from mes_profile import active_profile_id, resolve_mes_api_base
    from mes_profile_persist import persist_openapi_text
    from safe_http import assert_http_url_allowed
    from tools.query_tool.openapi_fetch import fetch_openapi_text

    pid = active_profile_id()
    if not pid:
        return {
            "ok": False,
            "error": "未配置 MES 资料包，请先在系统配置填写平台名称",
        }

    raw = (docs_url or "").strip()
    if not raw:
        base = str(resolve_mes_api_base() or "").strip().rstrip("/")
        if not base:
            return {
                "ok": False,
                "error": "资料包未配置 api_base，请在 MES 接入导入接口文档或传入 docs_url",
            }
        raw = f"{base}/docs"

    try:
        if not _is_localhost_url(raw):
            return {
                "ok": False,
                "error": "仅允许从本机 MES（127.0.0.1 / localhost）刷新资料包",
            }
        text, used = fetch_openapi_text(raw)
        out = persist_openapi_text(
            pid,
            text,
            source_url=used,
            merge_existing=True,
            reload_agent=True,
            sync_note="运行中 MES 刷新",
            preserve_runtime=True,
        )
        merge = out.get("merge") or {}
        return {
            "ok": True,
            "profile_id": pid,
            "fetched_from": used,
            "entity_count": out.get("entity_count"),
            "entity_ids": out.get("entity_ids"),
            "added": merge.get("added") or [],
            "updated": merge.get("updated") or [],
            "preserved": merge.get("preserved") or [],
            "hint": (
                "资料包已合并最新 OpenAPI。"
                "若用户刚通过写码新增接口，可立刻 list_platform_entities / query_platform_data。"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("refresh_mes_profile_from_runtime failed: %s", exc)
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
