"""
MES 资料包解析（站点级，落 DATA_DIR，不写死客户数据到仓库）。

解析顺序：
1. 环境变量 / settings 显式路径覆盖（仅 schema：MES_SCHEMA_DOC）
2. 当前资料包目录下对应文件（若存在且可读）

未配置资料包或资料包缺文件时：不回退任何仓库内置演示数据。
须在「系统配置 → MES 接入」填写平台名称并上传表结构 / 接口文档。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from bundle_root import resolve_repo_root

_REPO_ROOT = resolve_repo_root()
_PROFILE_ID_RE = re.compile(
    r"^[a-zA-Z0-9\u4e00-\u9fff][a-zA-Z0-9\u4e00-\u9fff_-]{0,63}$"
)

SCHEMA_FILENAME = "schema.md"
ENTITIES_FILENAME = "entities.json"
CAPABILITY_FILENAME = "capability_map.json"
OPENAPI_FILENAME = "openapi.json"
PROFILE_META_FILENAME = "profile.json"

_MISSING_HINT = (
    "请先在「系统配置 → MES 接入」填写平台名称，并上传表结构（.md）"
    "与接口文档（地址或 openapi.json）。"
)


def data_dir() -> Path:
    raw = (os.getenv("DATA_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (_REPO_ROOT / "data").resolve()


def profiles_root() -> Path:
    return data_dir() / "mes_profiles"


def sanitize_profile_id(raw: str | None) -> str:
    """空或非法 → 空字符串（表示未配置资料包）。"""
    s = (raw or "").strip()
    if not s:
        return ""
    if not _PROFILE_ID_RE.match(s):
        return ""
    return s


def active_profile_id() -> str:
    try:
        from settings_store import resolve_setting

        return sanitize_profile_id(resolve_setting("MES_PROFILE_ID", ""))
    except Exception:
        return sanitize_profile_id(os.getenv("MES_PROFILE_ID", ""))


def profile_dir(profile_id: str | None = None) -> Path | None:
    pid = sanitize_profile_id(
        profile_id if profile_id is not None else active_profile_id()
    )
    if not pid:
        return None
    return profiles_root() / pid


def ensure_profile_dir(profile_id: str) -> Path:
    pid = sanitize_profile_id(profile_id)
    if not pid:
        raise ValueError(
            "系统名称无效：可用中文或英文，勿含空格/斜杠，最长 64 字"
        )
    root = profiles_root() / pid
    root.mkdir(parents=True, exist_ok=True)
    meta = root / PROFILE_META_FILENAME
    if not meta.is_file():
        meta.write_text(
            json.dumps(
                {"id": pid, "label": pid, "created_by": "workbuddy"},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return root


def list_profile_ids() -> list[str]:
    root = profiles_root()
    if not root.is_dir():
        return []
    out: list[str] = []
    for p in sorted(root.iterdir()):
        if p.is_dir() and sanitize_profile_id(p.name) == p.name:
            out.append(p.name)
    return out


def _explicit_schema_override() -> Path | None:
    """MES_SCHEMA_DOC：settings / env 显式路径。"""
    raw = ""
    try:
        from settings_store import resolve_setting

        raw = resolve_setting("MES_SCHEMA_DOC", "").strip()
    except Exception:
        raw = (os.getenv("MES_SCHEMA_DOC") or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    if path.is_file():
        return path
    return None


def resolve_schema_doc() -> tuple[Path | None, str]:
    """
    返回 (绝对路径或 None, 来源标签)。
    来源：override | profile | none
    """
    override = _explicit_schema_override()
    if override is not None:
        return override, "override"

    pdir = profile_dir()
    if pdir is not None:
        candidate = (pdir / SCHEMA_FILENAME).resolve()
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate, "profile"

    return None, "none"


def resolve_entities_path() -> tuple[Path | None, str]:
    pdir = profile_dir()
    if pdir is not None:
        candidate = (pdir / ENTITIES_FILENAME).resolve()
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate, "profile"
    return None, "none"


def resolve_capability_map_path() -> tuple[Path | None, str]:
    pdir = profile_dir()
    if pdir is not None:
        candidate = (pdir / CAPABILITY_FILENAME).resolve()
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate, "profile"
    return None, "none"


def validate_entities_payload(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        raise ValueError("entities.json 须为 JSON 对象")
    entities = data.get("entities")
    if not isinstance(entities, list):
        raise ValueError("entities.json 须包含 entities 数组")
    if not entities:
        raise ValueError("entities 不能为空")
    for i, e in enumerate(entities):
        if not isinstance(e, dict):
            raise ValueError(f"entities[{i}] 须为对象")
        if not str(e.get("id") or "").strip():
            raise ValueError(f"entities[{i}] 缺少 id")
    return entities


def _load_entities_payload() -> dict[str, Any]:
    path, src = resolve_entities_path()
    if src != "profile" or path is None or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def load_entities_meta() -> dict[str, Any]:
    payload = _load_entities_payload()
    meta = payload.get("meta")
    return meta if isinstance(meta, dict) else {}


def resolve_path_prefix() -> str:
    """资料包声明的 API 路径前缀（如 /api 或 /api/v1），无则从实体 path 推断。"""
    from safe_http import safe_request_path

    meta = load_entities_meta()
    raw = str(meta.get("path_prefix") or "").strip()
    if raw:
        cleaned = safe_request_path(raw)
        return cleaned or ""
    path, src = resolve_entities_path()
    if src == "profile" and path is not None and path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            ents = payload.get("entities") if isinstance(payload, dict) else None
            if isinstance(ents, list):
                prefixes: list[str] = []
                for e in ents:
                    if not isinstance(e, dict):
                        continue
                    segs = [s for s in str(e.get("path") or "").split("/") if s]
                    if segs and segs[0].lower() == "api":
                        if len(segs) > 1 and segs[1].lower() in {"v1", "v2", "v3"}:
                            prefixes.append("/" + "/".join(segs[:2]))
                        else:
                            prefixes.append("/api")
                if prefixes:
                    return max(set(prefixes), key=prefixes.count)
        except Exception:
            pass
    return ""


def resolve_login_paths() -> list[str]:
    """登录 POST 路径：优先 entities.json meta，其次扫描当前 OpenAPI。"""
    from safe_http import safe_request_path

    meta = load_entities_meta()
    out: list[str] = []
    raw_list = meta.get("login_paths")
    if isinstance(raw_list, list):
        for item in raw_list:
            s = safe_request_path(str(item or ""))
            if s and s not in out:
                out.append(s)
    if out:
        return out

    pdir = profile_dir()
    if pdir is not None:
        openapi = pdir / OPENAPI_FILENAME
        if openapi.is_file():
            try:
                from tools.query_tool.openapi_to_entities import login_paths_from_openapi

                doc = json.loads(openapi.read_text(encoding="utf-8"))
                if isinstance(doc, dict):
                    cleaned: list[str] = []
                    for p in login_paths_from_openapi(doc):
                        s = safe_request_path(p)
                        if s and s not in cleaned:
                            cleaned.append(s)
                    return cleaned
            except Exception:
                pass
    return []


def resolve_mes_login_required_fields() -> list[str]:
    """MES 业务登录请求体必填字段（来自接口文档，不是 WorkBuddy 登录）。"""
    meta = load_entities_meta()
    raw = meta.get("login_required_fields")
    if isinstance(raw, list) and raw:
        return [str(x).strip() for x in raw if str(x).strip()]
    pdir = profile_dir()
    if pdir is not None:
        openapi = pdir / OPENAPI_FILENAME
        if openapi.is_file():
            try:
                from tools.query_tool.openapi_to_entities import login_body_spec_from_openapi

                doc = json.loads(openapi.read_text(encoding="utf-8"))
                if isinstance(doc, dict):
                    spec = login_body_spec_from_openapi(doc)
                    req = spec.get("required") or []
                    if req:
                        return [str(x) for x in req]
            except Exception:
                pass
    return ["username", "password"]


def origin_from_docs_url(url: str) -> str:
    """http://host:port/docs → http://host:port"""
    from safe_http import origin_of

    return origin_of(url)


def _safe_api_origin(url: str, *, peer: str = "") -> str:
    """校验 http(s) 源站；若给定 peer（如 source_url），必须同主机。"""
    from safe_http import assert_http_url_allowed, same_http_origin

    origin = origin_from_docs_url(url)
    if not origin:
        return ""
    try:
        origin = assert_http_url_allowed(origin, what="MES 接口地址")
    except ValueError:
        return ""
    if peer:
        peer_origin = origin_from_docs_url(peer)
        if peer_origin and not same_http_origin(origin, peer_origin):
            return ""
    return origin


def resolve_mes_api_base() -> str:
    """
    查数/登录用的 API 根地址。
    优先接口文档来源（OpenAPI servers / source_url）。
    若同时有 source_url 与 api_base / servers，必须同主机，防止资料包把查数密码打到别处。
    不回退界面 PLATFORM_BASE_URL（与 WorkBuddy 登录、网页端口无关）。
    """
    source_url = ""
    path, src = resolve_entities_path()
    if src == "profile" and path is not None and path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            meta = payload.get("meta") if isinstance(payload, dict) else None
            if isinstance(meta, dict):
                source_url = str(meta.get("source_url") or "").strip()
                api_base = _safe_api_origin(str(meta.get("api_base") or ""), peer=source_url)
                if api_base:
                    return api_base
                src_origin = _safe_api_origin(source_url)
                if src_origin:
                    return src_origin
        except Exception:
            pass

    pdir = profile_dir()
    if pdir is not None:
        openapi = pdir / OPENAPI_FILENAME
        if openapi.is_file():
            try:
                doc = json.loads(openapi.read_text(encoding="utf-8"))
                if isinstance(doc, dict):
                    servers = doc.get("servers")
                    if isinstance(servers, list):
                        for s in servers:
                            if isinstance(s, dict):
                                origin = _safe_api_origin(str(s.get("url") or ""), peer=source_url)
                                if origin:
                                    return origin
                    host = str(doc.get("host") or "").strip()
                    if host:
                        schemes = doc.get("schemes")
                        scheme = "http"
                        if isinstance(schemes, list) and schemes:
                            scheme = str(schemes[0] or "http")
                        origin = _safe_api_origin(f"{scheme}://{host}", peer=source_url)
                        if origin:
                            return origin
            except Exception:
                pass

    return _safe_api_origin(source_url)


def _file_info(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"path": "", "exists": False, "size": 0}
    ok = path.is_file()
    return {
        "path": str(path),
        "exists": ok,
        "size": path.stat().st_size if ok else 0,
    }


def profile_status() -> dict[str, Any]:
    pid = active_profile_id()
    pdir = profile_dir(pid) if pid else None
    schema_path, schema_src = resolve_schema_doc()
    entities_path, entities_src = resolve_entities_path()
    cap_path, cap_src = resolve_capability_map_path()
    openapi_path = None
    openapi_exists = False
    if pdir is not None:
        openapi_path = pdir / OPENAPI_FILENAME
        openapi_exists = openapi_path.is_file()

    entity_count = 0
    openapi_source_url = ""
    if entities_src == "profile" and entities_path is not None and entities_path.is_file():
        try:
            payload = json.loads(entities_path.read_text(encoding="utf-8"))
            ents = payload.get("entities") if isinstance(payload, dict) else None
            if isinstance(ents, list):
                entity_count = len(ents)
            meta = payload.get("meta") if isinstance(payload, dict) else None
            if isinstance(meta, dict):
                openapi_source_url = str(meta.get("source_url") or "").strip()
        except Exception:
            pass

    schema_uploaded = bool(pdir and (pdir / SCHEMA_FILENAME).is_file())
    runtime_api_base = resolve_mes_api_base()
    runtime_login = resolve_login_paths()
    runtime_prefix = resolve_path_prefix()
    return {
        "active_profile_id": pid or "",
        "configured": bool(pid),
        "profile_dir": str(pdir) if pdir else "",
        "available_profiles": list_profile_ids(),
        "schema": {**_file_info(schema_path), "source": schema_src},
        "entities": {**_file_info(entities_path), "source": entities_src},
        "capability_map": {**_file_info(cap_path), "source": cap_src},
        "openapi": {
            "path": str(openapi_path) if openapi_path else "",
            "exists": openapi_exists,
            "size": openapi_path.stat().st_size if openapi_exists and openapi_path else 0,
            "source_url": openapi_source_url,
        },
        "ui": {
            "schema_uploaded": schema_uploaded,
            "openapi_imported": openapi_exists,
            "entity_count": entity_count,
            "schema_size": (pdir / SCHEMA_FILENAME).stat().st_size if schema_uploaded and pdir else 0,
            "openapi_size": openapi_path.stat().st_size if openapi_exists and openapi_path else 0,
        },
        "runtime": {
            "api_base": runtime_api_base,
            "login_paths": runtime_login,
            "path_prefix": runtime_prefix,
        },
        "hint": (
            "须配置：① 平台名称 ② 表结构文档（.md）③ 接口文档（地址或 openapi.json）。"
            "换平台只需改名称并重新上传这两份资料。"
            "接口文档只用于生成可查对象；WorkBuddy 登录不走这份文档。"
            "查数另需填写 MES 接口账号（与 WorkBuddy 登录分开）。"
            f" {_MISSING_HINT}"
        ),
        "missing_hint": _MISSING_HINT,
    }


def invalidate_mes_data_caches() -> None:
    """资料包或 schema 变更后清相关缓存。"""
    try:
        from tools.query_tool.entity_catalog import invalidate_catalog

        invalidate_catalog()
    except Exception:
        pass
    try:
        from tools.schema_tool.capability_map import reload_capability_map

        reload_capability_map()
    except Exception:
        pass
    try:
        from tools.schema_tool.mes_schema_parser import invalidate_schema_caches

        invalidate_schema_caches()
    except Exception:
        pass
    try:
        import tools.platform_api as platform_api

        platform_api._client_instance = None
    except Exception:
        pass
