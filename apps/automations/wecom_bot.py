"""企业微信群机器人 Webhook 推送。"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request

logger = logging.getLogger(__name__)

WECOM_WEBHOOK_HOST = "qyapi.weixin.qq.com"
WECOM_WEBHOOK_PATH = "/cgi-bin/webhook/send"


def _resolve_setting(key: str, default: str = "") -> str:
    try:
        from settings_store import resolve_setting

        return resolve_setting(key, default)
    except Exception:
        return os.getenv(key, default).strip()


def _truthy(val: str | None, *, default: bool = False) -> bool:
    if val is None or val == "":
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def normalize_webhook_key(raw: str) -> str:
    """支持填 key 或完整 Webhook URL（自动提取 key= 参数）。"""
    text = (raw or "").strip()
    if not text:
        return ""
    if "://" in text or text.lower().startswith(WECOM_WEBHOOK_HOST):
        from urllib.parse import parse_qs, urlparse

        url = text if "://" in text else f"https://{text}"
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host != WECOM_WEBHOOK_HOST:
            raise ValueError(f"Webhook 须为 {WECOM_WEBHOOK_HOST}，当前为 {host or '未知'}")
        keys = parse_qs(parsed.query).get("key") or []
        key = str(keys[0] if keys else "").strip()
        if not key:
            raise ValueError("Webhook URL 中缺少 key 参数")
        return key
    return text


def webhook_key() -> str:
    return normalize_webhook_key(_resolve_setting("WECOM_WEBHOOK_KEY", ""))


def push_enabled() -> bool:
    return _truthy(_resolve_setting("WECOM_PUSH_ENABLED", "0"), default=False)


def push_dry_run() -> bool:
    return _truthy(_resolve_setting("WECOM_PUSH_DRY_RUN", "0"), default=False)


def build_webhook_url(key: str) -> str:
    from safe_http import assert_http_url_allowed

    safe_key = (key or "").strip()
    if not safe_key:
        raise ValueError("未配置企业微信 Webhook Key")
    url = f"https://{WECOM_WEBHOOK_HOST}{WECOM_WEBHOOK_PATH}?key={quote(safe_key, safe='')}"
    return assert_http_url_allowed(url, what="企业微信 Webhook")


def _send_payload(payload: dict[str, Any], *, key: str | None = None, timeout_sec: float = 15.0) -> dict[str, Any]:
    if push_dry_run():
        preview = json.dumps(payload, ensure_ascii=False)[:240]
        logger.info("WECOM dry-run (%d bytes): %s", len(json.dumps(payload, ensure_ascii=False).encode("utf-8")), preview)
        return {"ok": True, "errcode": 0, "errmsg": "dry_run", "dry_run": True}

    webhook = (key or webhook_key()).strip()
    if not webhook:
        return {"ok": False, "errcode": -1, "errmsg": "未配置群机器人 Webhook Key"}

    url = build_webhook_url(webhook)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    from safe_http import urlopen_limited

    try:
        with urlopen_limited(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        return {"ok": False, "errcode": exc.code, "errmsg": detail or str(exc)}
    except URLError as exc:
        return {"ok": False, "errcode": -1, "errmsg": str(exc.reason or exc)}

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"ok": False, "errcode": -1, "errmsg": f"响应非 JSON：{raw[:200]}"}

    errcode = int(data.get("errcode", -1))
    errmsg = str(data.get("errmsg") or "")
    return {"ok": errcode == 0, "errcode": errcode, "errmsg": errmsg}


def send_text(content: str, *, key: str | None = None, timeout_sec: float = 15.0) -> dict[str, Any]:
    """发送 text 消息（换行可靠，适合早报推送）。"""
    text = str(content or "").strip()
    if not text:
        return {"ok": False, "errcode": -1, "errmsg": "消息内容为空"}
    return _send_payload({"msgtype": "text", "text": {"content": text}}, key=key, timeout_sec=timeout_sec)


def send_markdown(content: str, *, key: str | None = None, timeout_sec: float = 15.0) -> dict[str, Any]:
    """发送 markdown 消息；返回 {ok, errcode, errmsg, dry_run?}。"""
    text = str(content or "").strip()
    if not text:
        return {"ok": False, "errcode": -1, "errmsg": "消息内容为空"}
    return _send_payload(
        {"msgtype": "markdown", "markdown": {"content": text}},
        key=key,
        timeout_sec=timeout_sec,
    )


def send_text_with_retry(
    content: str,
    *,
    key: str | None = None,
    retries: int = 1,
    retry_delay_sec: float = 3.0,
) -> dict[str, Any]:
    last = send_text(content, key=key)
    if last.get("ok") or retries <= 0:
        return last
    time.sleep(max(0.0, retry_delay_sec))
    second = send_text(content, key=key)
    if second.get("ok"):
        second["retried"] = True
        return second
    second["first_error"] = last.get("errmsg")
    return second


def send_push_with_retry(
    msgtype: str,
    content: str,
    *,
    key: str | None = None,
    retries: int = 1,
    retry_delay_sec: float = 3.0,
) -> dict[str, Any]:
    """单条推送：text 或 markdown。"""
    kind = str(msgtype or "text").strip().lower()
    if kind == "markdown":
        return send_markdown_with_retry(content, key=key, retries=retries, retry_delay_sec=retry_delay_sec)
    return send_text_with_retry(content, key=key, retries=retries, retry_delay_sec=retry_delay_sec)


def send_markdown_with_retry(
    content: str,
    *,
    key: str | None = None,
    retries: int = 1,
    retry_delay_sec: float = 3.0,
) -> dict[str, Any]:
    last = send_markdown(content, key=key)
    if last.get("ok") or retries <= 0:
        return last
    time.sleep(max(0.0, retry_delay_sec))
    second = send_markdown(content, key=key)
    if second.get("ok"):
        second["retried"] = True
        return second
    second["first_error"] = last.get("errmsg")
    return second
