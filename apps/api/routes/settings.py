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
    {
        "key": "READONLY_SQL_ENABLED",
        "group": "mes_analysis",
        "label": "开启只读 SQL（默认关）",
        "secret": "0",
    },
    {
        "key": "READONLY_SQL_DSN",
        "group": "mes_analysis",
        "label": "只读 SQL DSN（本期 sqlite 路径）",
        "secret": "0",
    },
    {
        "key": "READONLY_SQL_TABLE_WHITELIST",
        "group": "mes_analysis",
        "label": "只读表白名单（逗号分隔）",
        "secret": "0",
    },
    {
        "key": "DEPLOY_ENABLED",
        "group": "deploy",
        "label": "开启自动化部署",
        "secret": "0",
        "required": "1",
        "example": "打开后，在对话里说「部署到预发」才会走确认卡并发版",
        "hint": "总开关；关闭时只提示配置、绝不触发 CI",
    },
    {
        "key": "DEPLOY_GITHUB_REPO",
        "group": "deploy",
        "label": "GitHub 仓库（Actions）",
        "secret": "0",
        "required": "0",
        "example": "owner/repo",
        "hint": "仅 github_actions；格式 owner/仓库名。本机 SSH 可不填",
    },
    {
        "key": "DEPLOY_GITHUB_WORKFLOW",
        "group": "deploy",
        "label": "Workflow 文件名（Actions）",
        "secret": "0",
        "required": "0",
        "example": "deploy-staging.yml",
        "hint": "仅 github_actions；本机 SSH 可不填",
    },
    {
        "key": "DEPLOY_GITHUB_TOKEN",
        "group": "deploy",
        "label": "GitHub Token（Actions）",
        "secret": "1",
        "required": "0",
        "example": "ghp_xxxxxxxx（classic PAT，需能触发该仓 Actions）",
        "hint": "仅 github_actions；本机 SSH 可不填。也可回落环境变量 GITHUB_TOKEN",
    },
    {
        "key": "DEPLOY_ENV_WHITELIST",
        "group": "deploy",
        "label": "允许的环境",
        "secret": "0",
        "required": "0",
        "example": "staging",
        "hint": "逗号分隔；默认仅预发。生产须另开「允许生产环境」",
    },
    {
        "key": "DEPLOY_DEFAULT_REF",
        "group": "deploy",
        "label": "默认 Git 分支/tag",
        "secret": "0",
        "required": "0",
        "example": "hebo 或 staging",
        "hint": "确认卡预填；空则回落本机/写码工作分支配置",
    },
    {
        "key": "DEPLOY_ALLOW_PRODUCTION",
        "group": "deploy",
        "label": "允许生产环境",
        "secret": "0",
        "required": "0",
        "example": "默认关闭；仅预发联调时保持关",
        "hint": "打开后才可把 production 加入白名单（高风险）",
    },
    {
        "key": "DEPLOY_CI_PROVIDER",
        "group": "deploy",
        "label": "部署执行方式",
        "secret": "0",
        "required": "0",
        "example": "github_actions 或 local_ssh",
        "hint": "默认 github_actions。国内机境外 Actions 连不上时改 local_ssh（本机构建+SSH），不影响写码/审码",
    },
    {
        "key": "DEPLOY_REQUIRE_PUSHED_REF",
        "group": "deploy",
        "label": "要求已推送的 ref",
        "secret": "0",
        "required": "0",
        "example": "建议保持开启",
        "hint": "GitHub Actions 路径：须远程已存在的分支/tag。本机 SSH 路径表示本地存在的 ref",
    },
    {
        "key": "DEPLOY_SSH_HOST",
        "group": "deploy",
        "label": "本机 SSH：主机",
        "secret": "0",
        "required": "0",
        "example": "203.0.113.1",
        "hint": "仅 DEPLOY_CI_PROVIDER=local_ssh 时需要",
    },
    {
        "key": "DEPLOY_SSH_USER",
        "group": "deploy",
        "label": "本机 SSH：用户",
        "secret": "0",
        "required": "0",
        "example": "root",
        "hint": "仅 local_ssh；须能免密登录",
    },
    {
        "key": "DEPLOY_SSH_KEY_PATH",
        "group": "deploy",
        "label": "本机 SSH：私钥路径",
        "secret": "0",
        "required": "0",
        "example": "~/.ssh/deploy_key",
        "hint": "仅 local_ssh；填本机私钥文件路径（不要把私钥内容贴进对话）",
    },
    {
        "key": "DEPLOY_SSH_APP_PATH",
        "group": "deploy",
        "label": "本机 SSH：远端目录",
        "secret": "0",
        "required": "0",
        "example": "/var/www/myapp",
        "hint": "仅 local_ssh；远端工程根（含 frontend/dist、backend）",
    },
    {
        "key": "DEPLOY_LOCAL_PROJECT_PATH",
        "group": "deploy",
        "label": "本机 SSH：本地项目路径",
        "secret": "0",
        "required": "0",
        "example": "/Users/你/path/to/project",
        "hint": "仅 local_ssh；本机 git 仓库根，须含 frontend/ 与 backend/",
    },
    {
        "key": "DEPLOY_SSH_RESTART_CMD",
        "group": "deploy",
        "label": "本机 SSH：远端重启命令",
        "secret": "0",
        "required": "0",
        "example": "可空；如 systemctl restart myapp-api",
        "hint": "可选；同步完成后在远端执行（勿含换行）",
    },
    {
        "key": "DEPLOY_SSH_PORT",
        "group": "deploy",
        "label": "本机 SSH：端口",
        "secret": "0",
        "required": "0",
        "example": "22",
        "hint": "默认 22",
    },
    {
        "key": "DEPLOY_HEALTH_URL",
        "group": "deploy",
        "label": "部署后探活 URL",
        "secret": "0",
        "required": "0",
        "example": "http://主机:端口/",
        "hint": "P1-3d：本机 SSH 同步并重启后，由 WorkBuddy 本机 GET 探活；空则跳过。勿填 80 旧站",
    },
    {
        "key": "DEPLOY_HEALTH_TIMEOUT_SEC",
        "group": "deploy",
        "label": "探活单次超时（秒）",
        "secret": "0",
        "required": "0",
        "example": "20",
        "hint": "每次 HTTP 请求超时，默认 20",
    },
    {
        "key": "DEPLOY_HEALTH_RETRIES",
        "group": "deploy",
        "label": "探活重试次数",
        "secret": "0",
        "required": "0",
        "example": "5",
        "hint": "重启后服务起来可能较慢，默认重试 5 次",
    },
    {
        "key": "DEPLOY_SSH_SYNC_PAIRS",
        "group": "deploy",
        "label": "本机 SSH：同步路径对",
        "secret": "0",
        "required": "0",
        "example": "frontend/dist:frontend/dist,backend:backend",
        "hint": "local:remote，相对项目根与远端 app 根；空则使用默认 monorepo 布局",
    },
    {
        "key": "DEPLOY_SSH_BUILD_STEPS",
        "group": "deploy",
        "label": "本机 SSH：构建步骤",
        "secret": "0",
        "required": "0",
        "example": "frontend:npm ci,frontend:npm run build",
        "hint": "cwd:命令，cwd 空或 . 为项目根；空则按同步路径推断默认构建",
    },
    {
        "key": "DEPLOY_SSH_RSYNC_EXCLUDES",
        "group": "deploy",
        "label": "本机 SSH：rsync 排除项",
        "secret": "0",
        "required": "0",
        "example": ".env,.venv,__pycache__",
        "hint": "逗号或换行分隔；空则使用内置敏感文件排除列表",
    },
    {
        "key": "DEPLOY_GITHUB_WORKFLOW_ENV_INPUT",
        "group": "deploy",
        "label": "GitHub workflow 环境输入名",
        "secret": "0",
        "required": "0",
        "example": "environment",
        "hint": "workflow_dispatch inputs 的键名；填 none 表示不传 environment 参数",
    },
]

_GROUP_LABELS = {
    "llm": "对话模型",
    "vision": "视觉模型",
    "mes": "MES / ERP 接入",
    "mes_analysis": "MES 数据分析（高级）",
    "cursor_dev": "写码车道",
    "git_review": "Git 审码拉仓",
    "deploy": "自动化部署",
}

_GROUP_ORDER = (
    "llm",
    "vision",
    "mes",
    "mes_analysis",
    "cursor_dev",
    "git_review",
    "deploy",
)

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


def _field_payload(
    key: str,
    label: str,
    group: str,
    is_secret: bool,
    *,
    example: str = "",
    required: bool = False,
    hint: str = "",
) -> dict[str, Any]:
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
        "example": (example or "").strip(),
        "required": bool(required),
        "hint": (hint or "").strip(),
    }


def _fields_from_meta() -> list[dict[str, Any]]:
    return [
        _field_payload(
            m["key"],
            m["label"],
            m["group"],
            m["secret"] == "1" or m["key"] in SECRET_KEYS,
            example=str(m.get("example") or ""),
            required=str(m.get("required") or "") == "1",
            hint=str(m.get("hint") or ""),
        )
        for m in _FIELD_META
        if m["key"] in ALLOWED_KEYS
    ]


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

    fields = _fields_from_meta()
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
            "自动化部署：优先本页配置，确认后才触发 GitHub Actions。"
        ),
    }


@router.put(    "",
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

    try:
        from llm_model_guard import assert_models_in_mapping

        assert_models_in_mapping(values)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    fields = _fields_from_meta()
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
        "hint": "已保存并热更新。自动化部署等配置立即生效，无需改 .env。",
    }
