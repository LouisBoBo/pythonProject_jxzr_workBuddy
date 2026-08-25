"""CORS 解析：禁止规范上无效的「* + credentials」。

规则：
- ``CORS_ALLOW_ORIGINS=*``（或缺省）：``allow_origins=["*"]`` 且 **关闭** credentials，并打警告。
- 显式域名列表：默认 ``allow_credentials=True``（可用 ``CORS_ALLOW_CREDENTIALS=false`` 关掉）。
- ``WORKBUDDY_ENV=production|prod`` 时禁止 ``*``，启动直接失败。
"""
from __future__ import annotations

import os
import warnings
from typing import NamedTuple


class CorsSettings(NamedTuple):
    allow_origins: list[str]
    allow_credentials: bool
    wildcard: bool
    warning: str


def _env_is_production() -> bool:
    raw = (
        os.getenv("WORKBUDDY_ENV", "")
        or os.getenv("APP_ENV", "")
        or os.getenv("ENV", "")
    ).strip().lower()
    return raw in ("prod", "production")


def resolve_cors_settings(
    raw: str | None = None,
    *,
    allow_credentials_env: str | None = None,
    is_production: bool | None = None,
) -> CorsSettings:
    """解析 CORS；可注入参数便于单测。"""
    if raw is None:
        raw = os.getenv("CORS_ALLOW_ORIGINS", "*")
    text = (raw or "").strip()
    parts = [o.strip() for o in text.split(",") if o.strip()]
    if not parts:
        parts = ["*"]

    wildcard = any(p == "*" for p in parts)
    prod = _env_is_production() if is_production is None else is_production

    if prod and wildcard:
        raise RuntimeError(
            "生产环境禁止 CORS_ALLOW_ORIGINS=*。"
            "请设为具体前端源，例如："
            "CORS_ALLOW_ORIGINS=https://mes.example.com,https://wb.example.com"
            "（并设置 WORKBUDDY_ENV=production）。"
        )

    if wildcard:
        # 规范：Access-Control-Allow-Origin: * 时不能带 Allow-Credentials: true
        warn = (
            "CORS_ALLOW_ORIGINS=*：已关闭 allow_credentials（浏览器规范禁止 * + credentials）。"
            "本地 Vite 同源代理不受影响；平台 iframe 跨域嵌入请改为具体域名，"
            "例如 CORS_ALLOW_ORIGINS=https://mes.example.com,http://127.0.0.1:5180"
        )
        return CorsSettings(
            allow_origins=["*"],
            allow_credentials=False,
            wildcard=True,
            warning=warn,
        )

    if allow_credentials_env is None:
        allow_credentials_env = os.getenv("CORS_ALLOW_CREDENTIALS", "true")
    cred_raw = (allow_credentials_env or "true").strip().lower()
    allow_credentials = cred_raw not in ("0", "false", "no", "off")

    return CorsSettings(
        allow_origins=parts,
        allow_credentials=allow_credentials,
        wildcard=False,
        warning="",
    )


def apply_cors_warning(settings: CorsSettings) -> None:
    if settings.warning:
        warnings.warn(settings.warning, UserWarning, stacklevel=2)
        print(f"[warn] {settings.warning}")
