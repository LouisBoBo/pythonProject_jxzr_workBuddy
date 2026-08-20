"""MES 资料包：查询状态、上传表结构/接口文档。无仓库内置演示回退。"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from routes.auth import assert_settings_admin, require_auth

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))
_AGENT_DIR = _APPS_DIR / "agent"
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mes-profile", tags=["MES接入"])

_MAX_SCHEMA_BYTES = 25 * 1024 * 1024
_MAX_JSON_BYTES = 2 * 1024 * 1024


class ActivateBody(BaseModel):
    profile_id: str = Field(
        "",
        description="平台名称；空字符串表示清除当前资料包（须重新配置后才能查数/摸底）",
    )


class ImportOpenApiUrlBody(BaseModel):
    profile_id: str = Field(..., description="系统名称")
    url: str = Field(
        ...,
        description="接口文档地址，如 http://主机:端口/docs 或 .../openapi.json",
    )
    activate: bool = Field(True, description="导入后是否设为当前系统")


def _reload_after_profile_change() -> None:
    from mes_profile_persist import _reload_after_profile_change as _reload

    _reload()


def _persist_openapi_text(pid: str, text: str, *, activate: bool, source_url: str = "") -> dict[str, Any]:
    from mes_profile_persist import persist_openapi_text
    from settings_store import update_settings

    if activate:
        update_settings({"MES_PROFILE_ID": pid})
    try:
        out = persist_openapi_text(
            pid,
            text,
            source_url=source_url,
            merge_existing=False,
            reload_agent=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "entity_count": out.get("entity_count"),
        "entity_ids": out.get("entity_ids"),
        "meta": out.get("meta"),
        "fetched_from": source_url or "",
        **{k: v for k, v in out.items() if k not in {"merge", "profile_dir"}},
    }


@router.get(
    "",
    summary="MES 接入状态",
    description=(
        "返回当前系统名称、可用列表，以及表结构/实体/能力地图的实际路径与来源"
        "（override / profile / none）。未配置时 source=none，须先接入 MES。"
        "打开本页或应用时会后台触发「每日资料包同步」（本机 MES OpenAPI 合并），失败不影响本接口。"
    ),
)
async def get_mes_profile(_auth: tuple = Depends(require_auth)) -> dict[str, Any]:
    from mes_profile import profile_status

    try:
        from mes_profile_daily_sync import schedule_daily_sync_openapi

        # 用户打开设置/应用即触发；已同步过则瞬间跳过
        schedule_daily_sync_openapi(delay_sec=0.3)
    except Exception:
        pass

    status = profile_status()
    try:
        from mes_profile import profile_dir
        from mes_profile_daily_sync import _read_stamp, daily_sync_enabled

        pdir = profile_dir()
        stamp = _read_stamp(pdir) if pdir else {}
        status["daily_openapi_sync"] = {
            "enabled": daily_sync_enabled(),
            "last": stamp or None,
        }
    except Exception:
        pass
    return status


@router.put(
    "/active",
    summary="切换当前 MES 系统",
    description=(
        "写入 settings.json 的 MES_PROFILE_ID 并清缓存、热重置 Agent。"
        "传空字符串清除系统名称；清除后须重新配置才能查数/摸底。"
        "若环境变量 SETTINGS_ADMIN_USERS 非空，仅名单内用户可改。"
    ),
)
async def put_active_profile(
    body: ActivateBody,
    auth: tuple = Depends(require_auth),
) -> dict[str, Any]:
    assert_settings_admin(auth)
    from mes_profile import profile_status, sanitize_profile_id
    from settings_store import update_settings

    raw = (body.profile_id or "").strip()
    if raw and not sanitize_profile_id(raw):
        raise HTTPException(
            status_code=400,
            detail="系统名称无效：可用中文或英文，勿含空格/斜杠，最长 64 字",
        )
    pid = sanitize_profile_id(raw)
    update_settings({"MES_PROFILE_ID": pid})
    _reload_after_profile_change()
    status = profile_status()
    return {"ok": True, **status}


@router.post(
    "/upload-schema",
    summary="上传表结构文档",
    description=(
        "保存为当前系统名称目录下的 schema.md；"
        "可选立即将该系统设为当前。仅 Markdown/文本，最大约 25MB。"
    ),
)
async def upload_schema(
    profile_id: str = Form(..., description="系统名称"),
    activate: bool = Form(True, description="上传后是否设为当前系统"),
    file: UploadFile = File(..., description="表结构 Markdown 文件"),
    _auth: tuple = Depends(require_auth),
) -> dict[str, Any]:
    assert_settings_admin(_auth)
    from mes_profile import (
        SCHEMA_FILENAME,
        ensure_profile_dir,
        profile_status,
        sanitize_profile_id,
    )
    from settings_store import update_settings

    pid = sanitize_profile_id(profile_id)
    if not pid:
        raise HTTPException(status_code=400, detail="系统名称无效")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > _MAX_SCHEMA_BYTES:
        raise HTTPException(status_code=400, detail="表结构文件过大（上限 25MB）")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="文件须为 UTF-8 文本") from exc
    if not text.strip():
        raise HTTPException(status_code=400, detail="表结构内容为空")

    root = ensure_profile_dir(pid)
    dest = root / SCHEMA_FILENAME
    dest.write_text(text, encoding="utf-8")
    if activate:
        update_settings({"MES_PROFILE_ID": pid})
    _reload_after_profile_change()
    logger.info("mes schema uploaded profile=%s bytes=%s", pid, len(raw))
    return {"ok": True, "saved": str(dest), **profile_status()}


@router.post(
    "/upload-openapi",
    summary="上传接口文档并生成可查实体草稿",
    description=(
        "保存 openapi.json，并根据 paths 生成 entities.json 草稿（列表 GET → 可查询实体）。"
        "也可改用「从地址导入」（支持 /docs 自动找 openapi.json）。"
    ),
)
async def upload_openapi(
    profile_id: str = Form(..., description="目标系统名称"),
    activate: bool = Form(True, description="上传后是否设为当前系统"),
    file: UploadFile = File(..., description="OpenAPI/Swagger JSON（推荐 /openapi.json）"),
    _auth: tuple = Depends(require_auth),
) -> dict[str, Any]:
    assert_settings_admin(_auth)
    from mes_profile import sanitize_profile_id

    pid = sanitize_profile_id(profile_id)
    if not pid:
        raise HTTPException(status_code=400, detail="系统名称无效")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > _MAX_JSON_BYTES * 8:
        raise HTTPException(status_code=400, detail="接口文档过大（上限约 16MB）")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="文件须为 UTF-8 文本") from exc
    try:
        return _persist_openapi_text(pid, text, activate=activate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/import-openapi-url",
    summary="从地址导入接口文档",
    description=(
        "填写当前 MES 的 Swagger 页面（…/docs）或直接填 /openapi.json。"
        "服务端会自动拉取 OpenAPI，并据此生成可查对象（列表路径、分页随文档变化）。"
        "与 WorkBuddy 登录无关。"
    ),
)
async def import_openapi_url(
    body: ImportOpenApiUrlBody,
    _auth: tuple = Depends(require_auth),
) -> dict[str, Any]:
    assert_settings_admin(_auth)
    from mes_profile import sanitize_profile_id
    from tools.query_tool.openapi_fetch import fetch_openapi_text

    pid = sanitize_profile_id(body.profile_id)
    if not pid:
        raise HTTPException(status_code=400, detail="系统名称无效")
    try:
        text, used = fetch_openapi_text(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return _persist_openapi_text(pid, text, activate=body.activate, source_url=used)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/upload-entities",
    summary="（高级）直接上传实体目录",
    description=(
        "一般请改用「上传接口文档」或「从地址导入」。"
        "本接口用于人工精修后的 entities.json 覆盖写入。"
    ),
)
async def upload_entities(
    profile_id: str = Form(..., description="目标系统名称"),
    activate: bool = Form(True, description="上传后是否设为当前系统"),
    file: UploadFile = File(..., description="entities.json"),
    _auth: tuple = Depends(require_auth),
) -> dict[str, Any]:
    assert_settings_admin(_auth)
    from mes_profile import (
        ENTITIES_FILENAME,
        ensure_profile_dir,
        profile_status,
        sanitize_profile_id,
        validate_entities_payload,
    )
    from settings_store import update_settings

    pid = sanitize_profile_id(profile_id)
    if not pid:
        raise HTTPException(status_code=400, detail="系统名称 无效")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > _MAX_JSON_BYTES:
        raise HTTPException(status_code=400, detail="实体文件过大（上限 2MB）")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"JSON 无效：{exc}") from exc
    try:
        entities = validate_entities_payload(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    root = ensure_profile_dir(pid)
    dest = root / ENTITIES_FILENAME
    dest.write_text(
        json.dumps({"entities": entities}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if activate:
        update_settings({"MES_PROFILE_ID": pid})
    _reload_after_profile_change()
    logger.info("mes entities uploaded profile=%s count=%s", pid, len(entities))
    return {"ok": True, "saved": str(dest), "entity_count": len(entities), **profile_status()}
