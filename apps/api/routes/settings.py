"""系统配置 API：整站一份，登录用户可改；保存后热生效。"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from routes.auth import assert_settings_admin, require_auth
from routes_config import DATA_DIR
import user_prefs
from settings_store import (
    ALLOWED_KEYS,
    SECRET_KEYS,
    get_overlay,
    mask_secret,
    resolve_setting,
    setting_source,
    update_settings,
)

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["系统配置"])

# 字段元数据（分组 + 展示）
_FIELD_META: list[dict[str, str]] = [
    {
        "key": "LLM_API_KEY",
        "group": "llm",
        "label": "API Key",
        "secret": "1",
    },
    {
        "key": "LLM_BASE_URL",
        "group": "llm",
        "label": "API Base URL",
        "secret": "0",
    },
    {
        "key": "MAIN_MODEL",
        "group": "llm",
        "label": "模型名称",
        "secret": "0",
    },
    {
        "key": "VISION_API_KEY",
        "group": "vision",
        "label": "API Key",
        "secret": "1",
    },
    {
        "key": "VISION_BASE_URL",
        "group": "vision",
        "label": "API Base URL",
        "secret": "0",
    },
    {
        "key": "VISION_MODEL",
        "group": "vision",
        "label": "视觉模型名称",
        "secret": "0",
    },
    {
        "key": "MES_PROFILE_ID",
        "group": "mes",
        "label": "MES / ERP 平台名称",
        "secret": "0",
    },
    {
        "key": "PLATFORM_BASE_URL",
        "group": "mes",
        "label": "MES / ERP 平台访问地址",
        "secret": "0",
    },
    {
        "key": "MES_API_USERNAME",
        "group": "mes",
        "label": "MES / ERP 接口账号",
        "secret": "0",
    },
    {
        "key": "MES_API_PASSWORD",
        "group": "mes",
        "label": "MES / ERP 接口密码",
        "secret": "1",
    },
    {
        "key": "MES_API_ENTERPRISE_CODE",
        "group": "mes",
        "label": "MES / ERP 企业编码",
        "secret": "0",
    },
    {
        "key": "CURSOR_API_KEY",
        "group": "cursor_dev",
        "label": "Cursor API Key",
        "secret": "1",
    },
    {
        "key": "CURSOR_DEV_ENABLED",
        "group": "cursor_dev",
        "label": "写码车道开关",
        "secret": "0",
    },
    {
        "key": "IDE_GIT_HTTPS_MIRROR",
        "group": "git_review",
        "label": "Git HTTPS 镜像前缀",
        "secret": "0",
    },
    {
        "key": "IDE_GIT_MIRROR_FIRST",
        "group": "git_review",
        "label": "优先走镜像拉仓",
        "secret": "0",
    },
]

_GROUP_LABELS = {
    "llm": "对话模型",
    "vision": "视觉模型",
    "mes": "MES / ERP 接入",
    "cursor_dev": "写码车道",
    "git_review": "Git 审码拉仓",
}

_GROUP_ORDER = ("llm", "vision", "mes", "cursor_dev", "git_review")


class SettingsUpdateBody(BaseModel):
    """部分更新；密钥留空字符串表示清除界面覆盖、回退到环境变量。"""

    values: dict[str, str | bool | None] = Field(
        default_factory=dict,
        description="要更新的配置项（仅白名单字段生效）",
    )


class LocalWorkspaceBody(BaseModel):
    """当前登录用户的本机写码目标目录偏好。"""

    path: str = Field("", description="本机工程绝对路径；空字符串表示清除记忆")


def _auth_username(auth: tuple) -> str:
    _token, user = auth
    return str(getattr(user, "username", None) or "dev")


def _field_payload(key: str, label: str, group: str, is_secret: bool) -> dict[str, Any]:
    from config import (
        _effective_llm_api_key,
        _effective_llm_base_url,
        _effective_vision_api_key,
        _effective_vision_base_url,
        _effective_vision_model,
    )

    resolved = resolve_setting(key, "")
    src = setting_source(key)
    overlay = get_overlay()

    # 通用字段：展示有效值（含旧字段回退）
    if key == "LLM_API_KEY" and not resolved:
        resolved = _effective_llm_api_key()
        if resolved:
            for alias in ("DEEPSEEK_API_KEY", "SILICONFLOW_API_KEY"):
                if setting_source(alias) != "unset":
                    src = setting_source(alias)
                    break
    elif key == "LLM_BASE_URL" and not resolved:
        resolved = _effective_llm_base_url()
        if resolved:
            if setting_source("DEEPSEEK_BASE_URL") != "unset":
                src = setting_source("DEEPSEEK_BASE_URL")
            elif resolved:
                src = "env" if src == "unset" else src
    elif key == "MAIN_MODEL" and not resolved:
        resolved = resolve_setting("MODEL_NAME", "")
        src = setting_source("MODEL_NAME")
        if src == "unset":
            src = setting_source("MAIN_MODEL")
    elif key == "VISION_API_KEY" and not resolved:
        resolved = _effective_vision_api_key()
        if resolved and setting_source("ZHIPU_API_KEY") != "unset":
            src = setting_source("ZHIPU_API_KEY")
    elif key == "VISION_BASE_URL" and not resolved:
        resolved = _effective_vision_base_url().rstrip("/")
        if setting_source("ZHIPU_BASE_URL") != "unset":
            src = setting_source("ZHIPU_BASE_URL")
        elif resolved and src == "unset":
            src = "env"
    elif key == "VISION_MODEL" and not resolved:
        resolved = _effective_vision_model()
        if resolved and src == "unset":
            src = "env"

    if is_secret:
        display = mask_secret(resolved) if resolved else ""
        configured = bool(resolved)
    else:
        display = resolved
        configured = bool(resolved)
    return {
        "key": key,
        "label": label,
        "group": group,
        "group_label": _GROUP_LABELS.get(group, group),
        "secret": is_secret,
        "value": display,
        "configured": configured,
        "source": src if resolved else "unset",
        "has_ui_override": key in overlay
        or (key == "MAIN_MODEL" and "MODEL_NAME" in overlay),
    }


def _llm_status(config_cls: Any) -> dict[str, Any]:
    base = (getattr(config_cls, "LLM_BASE_URL", "") or "").strip()
    vision_key = (getattr(config_cls, "VISION_API_KEY", "") or "").strip()
    vision_base = (getattr(config_cls, "VISION_BASE_URL", "") or "").strip().rstrip("/")
    return {
        "llm_provider": "openai_compatible",
        "llm_model": config_cls.MODEL_NAME,
        "llm_base_url": base,
        "llm_configured": bool((getattr(config_cls, "LLM_API_KEY", "") or "").strip()),
        "vision_configured": bool(vision_key),
        "vision_model": getattr(config_cls, "VISION_MODEL", "") or "",
        "vision_base_url": vision_base,
    }


def _apply_runtime_reload() -> dict[str, Any]:
    """保存后热加载 Config / Cursor / Agent 单例。"""
    from config import Config

    Config.reload_runtime()

    cursor_available = False
    cursor_reason = ""
    try:
        from cursor_dev.config import reload_config

        cfg = reload_config()
        cursor_available, cursor_reason = cfg.availability()
    except Exception as exc:  # noqa: BLE001
        cursor_reason = f"写码配置刷新失败: {exc}"
        logger.warning(cursor_reason)

    try:
        from agent_wrapper import AgentRunner

        AgentRunner().reset_agent()
    except Exception as exc:  # noqa: BLE001
        logger.warning("reset_agent 失败（下次对话仍可能用旧客户端）: %s", exc)

    try:
        from mes_profile import invalidate_mes_data_caches

        invalidate_mes_data_caches()
    except Exception as exc:  # noqa: BLE001
        logger.warning("invalidate_mes_data_caches 失败: %s", exc)

    return {
        **_llm_status(Config),
        "cursor_dev_available": cursor_available,
        "cursor_dev_reason": cursor_reason,
    }


@router.get(
    "/local-workspace",
    summary="读取上次本机写码目录",
    description="按登录用户返回 last_local_workspace；写码确认卡默认带出。与整站 settings.json 分离。",
)
async def get_local_workspace(auth: tuple = Depends(require_auth)) -> dict[str, Any]:
    username = _auth_username(auth)
    path = user_prefs.get_last_local_workspace(DATA_DIR, username)
    return {"path": path, "username": username}


@router.put(
    "/local-workspace",
    summary="保存本机写码目录偏好",
    description="写入当前用户的 last_local_workspace；确认本机写码成功后也会自动更新。",
)
async def put_local_workspace(
    body: LocalWorkspaceBody,
    auth: tuple = Depends(require_auth),
) -> dict[str, Any]:
    username = _auth_username(auth)
    path = user_prefs.set_last_local_workspace(DATA_DIR, username, body.path or "")
    return {"ok": True, "path": path, "username": username}


@router.get(
    "",
    summary="获取系统配置",
    description=(
        "返回整站配置（对话模型 + 写码车道 + Git 审码拉仓）。密钥仅掩码展示，不返回明文。"
        "source 为 ui / env / unset。所有登录用户可访问。"
    ),
)
async def get_settings(_auth: tuple = Depends(require_auth)) -> dict[str, Any]:
    from config import Config

    Config.reload_runtime()

    fields = [
        _field_payload(
            m["key"],
            m["label"],
            m["group"],
            m["secret"] == "1" or m["key"] in SECRET_KEYS,
        )
        for m in _FIELD_META
        if m["key"] in ALLOWED_KEYS
    ]
    groups: dict[str, list[dict[str, Any]]] = {}
    for f in fields:
        groups.setdefault(f["group"], []).append(f)

    cursor_available = False
    cursor_reason = ""
    try:
        from cursor_dev.config import get_config

        ok, reason = get_config().availability()
        cursor_available, cursor_reason = ok, reason
    except Exception as exc:  # noqa: BLE001
        cursor_reason = str(exc)

    return {
        "groups": [
            {
                "id": gid,
                "label": _GROUP_LABELS.get(gid, gid),
                "fields": groups.get(gid, []),
            }
            for gid in _GROUP_ORDER
            if gid in groups
        ],
        "status": {
            **_llm_status(Config),
            "cursor_dev_available": cursor_available,
            "cursor_dev_reason": cursor_reason,
        },
        "hint": (
            "对话/视觉模型均支持 OpenAI 兼容协议。截图改需求依赖视觉模型 Key。"
            "未配置 MES 资料包时无法查数/摸底，请先在 MES 接入上传表结构与接口文档。"
            "密钥留空保存不修改。.env 不会被改写。"
        ),
    }


@router.put(
    "",
    summary="更新系统配置",
    description=(
        "部分更新整站配置并立即热生效（重建对话 Agent、刷新写码配置）。"
        "空字符串清除对应界面覆盖。不写回 .env。"
        "若环境变量 SETTINGS_ADMIN_USERS 非空，仅名单内用户可改。"
        "界面 PLATFORM_BASE_URL 不用于 WorkBuddy 登录。"
    ),
)
async def put_settings(
    body: SettingsUpdateBody,
    auth: tuple = Depends(require_auth),
) -> dict[str, Any]:
    assert_settings_admin(auth)
    values = body.values or {}
    # MAIN_MODEL 同步写 MODEL_NAME，避免两处不一致
    if "MAIN_MODEL" in values and "MODEL_NAME" not in values:
        values = dict(values)
        values["MODEL_NAME"] = values["MAIN_MODEL"]

    if "IDE_GIT_HTTPS_MIRROR" in values:
        values = dict(values)
        raw_mirror = values.get("IDE_GIT_HTTPS_MIRROR")
        if raw_mirror is None:
            pass
        elif isinstance(raw_mirror, bool):
            values["IDE_GIT_HTTPS_MIRROR"] = "1" if raw_mirror else "0"
        else:
            text = str(raw_mirror).strip()
            if text == "":
                values["IDE_GIT_HTTPS_MIRROR"] = ""
            elif text.lower() in {"off", "0", "none", "-", "false", "no"}:
                values["IDE_GIT_HTTPS_MIRROR"] = "off"
            else:
                try:
                    from tools.ide_review.git_review import _sanitize_mirror_prefix
                except Exception as exc:  # noqa: BLE001
                    raise HTTPException(
                        status_code=500,
                        detail=f"镜像校验模块不可用：{exc}",
                    ) from exc
                cleaned: list[str] = []
                for part in text.split(","):
                    item = _sanitize_mirror_prefix(part)
                    if item and item not in cleaned:
                        cleaned.append(item)
                    if len(cleaned) >= 5:
                        break
                if not cleaned:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Git HTTPS 镜像前缀无效：仅允许 https 公网地址"
                            "（禁止 http / localhost / 内网 IP / 账号密码），"
                            "或填 off 关闭。"
                        ),
                    )
                values["IDE_GIT_HTTPS_MIRROR"] = ",".join(cleaned)

    if "PLATFORM_BASE_URL" in values:
        values = dict(values)
        raw_plat = values.get("PLATFORM_BASE_URL")
        if raw_plat is None:
            pass
        elif str(raw_plat).strip() == "":
            values["PLATFORM_BASE_URL"] = ""
        else:
            from safe_http import assert_http_url_allowed

            try:
                values["PLATFORM_BASE_URL"] = assert_http_url_allowed(
                    str(raw_plat), what="PLATFORM_BASE_URL"
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    if "MES_PROFILE_ID" in values:
        values = dict(values)
        raw_pid = values.get("MES_PROFILE_ID")
        if raw_pid is None:
            pass
        elif str(raw_pid).strip() == "":
            values["MES_PROFILE_ID"] = ""
        else:
            from mes_profile import sanitize_profile_id

            pid = sanitize_profile_id(str(raw_pid))
            if not pid:
                raise HTTPException(
                    status_code=400,
                    detail="系统名称无效：可用中文或英文，勿含空格/斜杠，最长 64 字",
                )
            values["MES_PROFILE_ID"] = pid

    update_settings(values)
    # 不在日志打印 values（可能含密钥）
    logger.info(
        "settings updated keys=%s",
        sorted(k for k in values if str(k).strip() in ALLOWED_KEYS),
    )
    if "MES_PROFILE_ID" in values or "MES_SCHEMA_DOC" in values:
        try:
            from mes_profile import invalidate_mes_data_caches

            invalidate_mes_data_caches()
        except Exception as exc:  # noqa: BLE001
            logger.warning("mes profile cache invalidate failed: %s", exc)
    status = _apply_runtime_reload()

    from config import Config

    fields = [
        _field_payload(
            m["key"],
            m["label"],
            m["group"],
            m["secret"] == "1" or m["key"] in SECRET_KEYS,
        )
        for m in _FIELD_META
        if m["key"] in ALLOWED_KEYS
    ]
    groups: dict[str, list[dict[str, Any]]] = {}
    for f in fields:
        groups.setdefault(f["group"], []).append(f)

    return {
        "ok": True,
        "groups": [
            {
                "id": gid,
                "label": _GROUP_LABELS.get(gid, gid),
                "fields": groups.get(gid, []),
            }
            for gid in _GROUP_ORDER
            if gid in groups
        ],
        "status": {
            **_llm_status(Config),
            **status,
        },
        "hint": (
            "对话/视觉模型均支持 OpenAI 兼容协议。截图改需求依赖视觉模型 Key。"
            "未配置 MES 资料包时无法查数/摸底，请先在 MES 接入上传表结构与接口文档。"
            "密钥留空保存不修改。.env 不会被改写。"
        ),
    }