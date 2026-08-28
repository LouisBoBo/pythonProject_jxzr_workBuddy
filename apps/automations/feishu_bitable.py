"""飞书多维表格 Open API（tenant token + 批量写记录）。"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

logger = logging.getLogger(__name__)

FEISHU_API_HOST = "open.feishu.cn"
_TOKEN_CACHE: dict[str, Any] = {"token": "", "expire_at": 0.0}
# wiki 节点 token → 真实 bitable app_token（obj_token）
_WIKI_APP_TOKEN_CACHE: dict[str, str] = {}


def _looks_like_bitable_app_token(token: str) -> bool:
    t = (token or "").strip()
    # 独立多维表格常见 basc/bascn；部分文档示例以 app 开头
    return t.startswith(("basc", "bascn", "app"))


def _looks_like_wiki_node_token(token: str) -> bool:
    """wiki 节点 token 常见前缀；无前缀时也允许走 get_node（失败再原样写表）。"""
    t = (token or "").strip()
    if not t or _looks_like_bitable_app_token(t):
        return False
    return t.startswith("wik") or len(t) >= 16


def _resolve_setting(key: str, default: str = "") -> str:
    try:
        from settings_store import resolve_setting

        return resolve_setting(key, default)
    except Exception:
        return (os.getenv(key, default) or "").strip()


def _truthy(val: str | None, *, default: bool = False) -> bool:
    if val is None or val == "":
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def bitable_enabled() -> bool:
    return _truthy(_resolve_setting("FEISHU_BITABLE_ENABLED", "0"), default=False)


def bitable_dry_run() -> bool:
    return _truthy(_resolve_setting("FEISHU_BITABLE_DRY_RUN", "0"), default=False)


def app_id() -> str:
    return (_resolve_setting("FEISHU_APP_ID", "") or "").strip()


def app_secret() -> str:
    return (_resolve_setting("FEISHU_APP_SECRET", "") or "").strip()


def normalize_app_token(raw: str) -> str:
    """支持 basc…、wiki 节点 token，或完整 base/wiki URL 中截取。"""
    text = (raw or "").strip()
    if not text:
        return ""
    if "://" in text or "feishu.cn" in text.lower() or "larksuite.com" in text.lower():
        from urllib.parse import urlparse

        path = urlparse(text if "://" in text else f"https://{text}").path or ""
        parts = [p for p in path.split("/") if p]
        for i, part in enumerate(parts):
            if part in {"base", "basex"} and i + 1 < len(parts):
                return parts[i + 1].strip()
        for i, part in enumerate(parts):
            if part == "wiki" and i + 1 < len(parts):
                # 知识库节点 token，写表前会再解析为真实 app_token
                return parts[i + 1].strip()
        for part in parts:
            if part.startswith("basc") or part.startswith("bascn"):
                return part.strip()
        raise ValueError(
            "无法从飞书链接中解析 app_token；请填 /base/basc… 或 /wiki/… 链接中的 token"
        )
    return text


def normalize_table_id(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    if "://" in text or "table=" in text.lower():
        from urllib.parse import parse_qs, urlparse

        url = text if "://" in text else f"https://feishu.cn/?{text.lstrip('?')}"
        qs = parse_qs(urlparse(url).query)
        vals = qs.get("table") or []
        if vals and str(vals[0]).strip().startswith("tbl"):
            return str(vals[0]).strip()
        raise ValueError("无法从链接解析 table_id，请填 tbl 开头的表 ID")
    return text


def _assert_feishu_url(url: str) -> str:
    from safe_http import assert_http_url_allowed

    allowed = assert_http_url_allowed(url, what="飞书 API")
    from urllib.parse import urlparse

    host = (urlparse(allowed).hostname or "").lower()
    if host != FEISHU_API_HOST:
        raise ValueError(f"飞书 API 主机须为 {FEISHU_API_HOST}，当前为 {host or '未知'}")
    return allowed


def _parse_feishu_response(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"ok": False, "code": -1, "msg": f"响应非 JSON：{raw[:200]}"}
    if not isinstance(data, dict):
        return {"ok": False, "code": -1, "msg": "响应格式异常"}
    code = data.get("code")
    try:
        code_n = int(code) if code is not None else 0
    except (TypeError, ValueError):
        code_n = -1
    if code_n != 0:
        return {
            "ok": False,
            "code": code,
            "msg": str(data.get("msg") or data.get("error") or "飞书 API 失败")[:500],
            "raw": data,
        }
    return {"ok": True, **data}


def _http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    from safe_http import urlopen_limited

    endpoint = _assert_feishu_url(url)
    hdrs = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        hdrs.update(headers)
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(endpoint, data=body, headers=hdrs, method=method)
    try:
        with urlopen_limited(req, timeout=20.0, max_bytes=2_000_000) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            detail = str(exc)
        return {"ok": False, "code": exc.code, "msg": detail or str(exc)}
    except URLError as exc:
        return {"ok": False, "code": -1, "msg": str(exc.reason or exc)}
    except ValueError as exc:
        return {"ok": False, "code": -1, "msg": str(exc)}
    return _parse_feishu_response(raw)


def _post_json(url: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    return _http_json(url, method="POST", payload=payload, headers=headers)


def _get_json(url: str, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    return _http_json(url, method="GET", headers=headers)


def resolve_bitable_app_token(app_token: str, *, access_token: str) -> dict[str, Any]:
    """将 wiki 节点 token 解析为多维表格真实 app_token（obj_token）。

    Happy path：已是 basc/bascn/app… → 原样返回。
    边界：wiki 链接填进 app_token → 调 get_node；已是真实 obj_token → get_node 失败则原样使用。
    失败：明确非 bitable 节点 → 可读错误。
    """
    token = normalize_app_token(app_token)
    if not token:
        return {"ok": False, "code": -1, "msg": "未配置 app_token"}
    if _looks_like_bitable_app_token(token):
        return {"ok": True, "app_token": token}
    if not _looks_like_wiki_node_token(token):
        return {"ok": True, "app_token": token}
    cached = _WIKI_APP_TOKEN_CACHE.get(token)
    if cached:
        return {"ok": True, "app_token": cached, "from_wiki": True}

    if bitable_dry_run():
        return {"ok": True, "app_token": token, "from_wiki": True, "dry_run": True}

    from urllib.parse import quote

    # 仅对疑似 wiki 节点尝试解析；失败则当作已是真实 bitable token（常见 obj_token 无固定前缀）
    out = _get_json(
        f"https://{FEISHU_API_HOST}/open-apis/wiki/v2/spaces/get_node?token={quote(token, safe='')}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not out.get("ok"):
        logger.info(
            "wiki resolve miss, treat token as bitable app_token: %s",
            out.get("msg"),
        )
        return {"ok": True, "app_token": token}
    data = out.get("data") if isinstance(out.get("data"), dict) else {}
    node = data.get("node") if isinstance(data.get("node"), dict) else {}
    obj_type = str(node.get("obj_type") or "").strip().lower()
    obj_token = str(node.get("obj_token") or "").strip()
    if obj_type and obj_type != "bitable":
        return {
            "ok": False,
            "code": -1,
            "msg": f"该 wiki 节点类型为 {obj_type}，不是多维表格（bitable）",
        }
    if not obj_token:
        return {"ok": True, "app_token": token}
    _WIKI_APP_TOKEN_CACHE[token] = obj_token
    logger.info("feishu wiki token resolved to bitable app_token=%s…", obj_token[:8])
    return {"ok": True, "app_token": obj_token, "from_wiki": True}


def _friendly_bitable_error(code: Any, msg: str) -> str:
    text = (msg or "").strip()
    code_s = str(code or "")
    if "91403" in code_s or "Forbidden" in text:
        return (
            "飞书拒绝写入（91403 Forbidden）：请到该多维表格右上角 ⋯ → 更多 → "
            "「添加文档应用」→ 选中你的自建应用 → 权限选「可编辑」；"
            "并确认开放平台已开通「新增记录」且版本已发布。"
        )
    if "91402" in code_s or "NOTEXIST" in text:
        return (
            "飞书资源不存在（91402）：请核对 app_token / table_id；"
            "wiki 链接须能解析出真实 basc token，table_id 须为 tbl 开头。"
        )
    if "FieldNameNotFound" in text or "1254045" in code_s or "FieldName" in text:
        return (
            "飞书列名仍无法对齐（FieldNameNotFound）。"
            "请确认表里有「日期/在制/稼动率/良率」等相近列；"
            "系统已支持 %、空格、简称宽松匹配。若刚改过列名，再测一次。"
        )
    return text[:500] or "飞书 API 失败"


def get_tenant_access_token(*, force: bool = False) -> dict[str, Any]:
    """获取 tenant_access_token（带简易缓存）。"""
    now = time.time()
    if (
        not force
        and _TOKEN_CACHE.get("token")
        and float(_TOKEN_CACHE.get("expire_at") or 0) > now + 60
    ):
        return {"ok": True, "tenant_access_token": _TOKEN_CACHE["token"]}

    aid = app_id()
    secret = app_secret()
    if not aid or not secret:
        return {"ok": False, "code": -1, "msg": "未配置 FEISHU_APP_ID / FEISHU_APP_SECRET"}

    if bitable_dry_run():
        return {"ok": True, "tenant_access_token": "dry_run_token", "dry_run": True}

    out = _post_json(
        f"https://{FEISHU_API_HOST}/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": aid, "app_secret": secret},
    )
    if not out.get("ok"):
        return out
    token = str(out.get("tenant_access_token") or "").strip()
    expire = int(out.get("expire") or 7200)
    if not token:
        return {"ok": False, "code": -1, "msg": "飞书未返回 tenant_access_token"}
    _TOKEN_CACHE["token"] = token
    _TOKEN_CACHE["expire_at"] = now + max(60, expire - 120)
    return {"ok": True, "tenant_access_token": token}


def list_table_fields(
    *,
    app_token: str,
    table_id: str,
    access_token: str,
) -> dict[str, Any]:
    """列出数据表字段元数据：field_id / field_name / type。"""
    token_app = normalize_app_token(app_token)
    tid = normalize_table_id(table_id)
    if not token_app or not tid:
        return {"ok": False, "code": -1, "msg": "未配置 app_token 或 table_id"}
    if bitable_dry_run():
        return {"ok": True, "fields": [], "dry_run": True}

    from urllib.parse import quote

    url = (
        f"https://{FEISHU_API_HOST}/open-apis/bitable/v1/apps/"
        f"{quote(token_app, safe='')}/tables/{quote(tid, safe='')}/fields?page_size=100"
    )
    out = _get_json(url, headers={"Authorization": f"Bearer {access_token}"})
    if not out.get("ok"):
        return {
            "ok": False,
            "code": out.get("code"),
            "msg": str(out.get("msg") or "列出飞书字段失败")[:500],
        }
    data = out.get("data") if isinstance(out.get("data"), dict) else {}
    items = data.get("items") if isinstance(data.get("items"), list) else []
    fields: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("field_name") or "").strip()
        fid = str(item.get("field_id") or "").strip()
        if not name:
            continue
        try:
            ftype = int(item.get("type")) if item.get("type") is not None else None
        except (TypeError, ValueError):
            ftype = None
        fields.append({"field_id": fid, "field_name": name, "type": ftype})
    return {"ok": True, "fields": fields}


def list_table_field_names(
    *,
    app_token: str,
    table_id: str,
    access_token: str,
) -> dict[str, Any]:
    """兼容旧调用：只返回字段名列表。"""
    out = list_table_fields(app_token=app_token, table_id=table_id, access_token=access_token)
    if not out.get("ok"):
        return out
    names = [str(f.get("field_name")) for f in (out.get("fields") or []) if isinstance(f, dict)]
    return {"ok": True, "fields": names, "dry_run": out.get("dry_run")}


def create_table_field(
    *,
    app_token: str,
    table_id: str,
    access_token: str,
    field_name: str,
    field_type: int,
    property: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """新增一个字段；成功返回 field 元数据。"""
    from urllib.parse import quote

    token_app = normalize_app_token(app_token)
    tid = normalize_table_id(table_id)
    payload: dict[str, Any] = {"field_name": field_name, "type": int(field_type)}
    if property:
        payload["property"] = property
    url = (
        f"https://{FEISHU_API_HOST}/open-apis/bitable/v1/apps/"
        f"{quote(token_app, safe='')}/tables/{quote(tid, safe='')}/fields"
    )
    out = _post_json(url, payload, headers={"Authorization": f"Bearer {access_token}"})
    if not out.get("ok"):
        return {
            "ok": False,
            "code": out.get("code"),
            "msg": str(out.get("msg") or "创建飞书字段失败")[:500],
        }
    data = out.get("data") if isinstance(out.get("data"), dict) else {}
    field = data.get("field") if isinstance(data.get("field"), dict) else {}
    return {
        "ok": True,
        "field": {
            "field_id": str(field.get("field_id") or ""),
            "field_name": str(field.get("field_name") or field_name),
            "type": field.get("type", field_type),
        },
    }


def ensure_table_fields(
    *,
    app_token: str,
    table_id: str,
    access_token: str,
    desired_columns: list[str],
    existing: list[dict[str, Any]],
    sample_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """缺列则自动创建；返回最终字段列表。

    Happy path：已有列宽松匹配即可。
    边界：人手建表缺列 / 只有「文本」→ 按样例值推断类型自动补列。
    失败：无建字段权限 → 仍返回已有列，由上层决定能否写入。
    """
    from automations.bitable_writer import infer_field_spec, resolve_column_meta

    samples = sample_values if isinstance(sample_values, dict) else {}
    fields = list(existing)
    created: list[str] = []
    failed: list[str] = []
    for desired in desired_columns:
        if resolve_column_meta(desired, fields):
            continue
        spec = infer_field_spec(desired, samples.get(desired))
        out = create_table_field(
            app_token=app_token,
            table_id=table_id,
            access_token=access_token,
            field_name=desired,
            field_type=int(spec.get("type") or 1),
            property=spec.get("property") if isinstance(spec.get("property"), dict) else None,
        )
        if out.get("ok") and isinstance(out.get("field"), dict):
            fields.append(out["field"])
            created.append(desired)
        else:
            failed.append(f"{desired}:{out.get('msg') or 'fail'}")
    return {"ok": True, "fields": fields, "created": created, "failed": failed}


def batch_create_records(
    *,
    app_token: str,
    table_id: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """向多维表格批量追加记录。records 项为 {fields: {...}}。

    Happy path：拉表头 → 缺列自动建 → 宽松对齐 → 按类型写值 → 写入。
    边界：列名有 %/空格/简称差异；人手漏列。
    失败：权限不足 / 一张都对不上 → 可读错误。
    """
    from automations.bitable_writer import collect_desired_columns, remap_records_to_table_fields

    token_app = normalize_app_token(app_token)
    tid = normalize_table_id(table_id)
    if not token_app:
        return {"ok": False, "code": -1, "msg": "未配置 app_token"}
    if not tid:
        return {"ok": False, "code": -1, "msg": "未配置 table_id"}
    if not records:
        return {"ok": False, "code": -1, "msg": "无待写入记录"}

    if bitable_dry_run():
        preview = json.dumps(records[:2], ensure_ascii=False)[:400]
        logger.info(
            "FEISHU bitable dry-run app=%s table=%s n=%s %s",
            token_app[:8],
            tid,
            len(records),
            preview,
        )
        return {
            "ok": True,
            "dry_run": True,
            "record_ids": [f"dry-{i}" for i in range(len(records))],
        }

    tok = get_tenant_access_token()
    if not tok.get("ok"):
        return tok
    access = str(tok.get("tenant_access_token") or "")

    resolved = resolve_bitable_app_token(token_app, access_token=access)
    if not resolved.get("ok"):
        return resolved
    token_app = str(resolved.get("app_token") or token_app)

    write_records = records
    listed = list_table_fields(app_token=token_app, table_id=tid, access_token=access)
    if listed.get("ok"):
        table_fields = listed.get("fields") if isinstance(listed.get("fields"), list) else []
        if table_fields is not None:
            desired = collect_desired_columns(records)
            samples: dict[str, Any] = {}
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                flds = rec.get("fields")
                if not isinstance(flds, dict):
                    continue
                for k, v in flds.items():
                    if k not in samples and v is not None:
                        samples[str(k)] = v
            ensured = ensure_table_fields(
                app_token=token_app,
                table_id=tid,
                access_token=access,
                desired_columns=desired,
                existing=list(table_fields),
                sample_values=samples,
            )
            table_fields = ensured.get("fields") if isinstance(ensured.get("fields"), list) else table_fields
            if ensured.get("created"):
                logger.info("bitable auto-created fields=%s", ensured.get("created"))
            if ensured.get("failed"):
                logger.warning("bitable auto-create failed=%s", ensured.get("failed"))

        if table_fields:
            remapped, matched, missing = remap_records_to_table_fields(records, table_fields)
            logger.info(
                "bitable field align matched=%s missing=%s",
                matched,
                missing,
            )
            if not remapped:
                names = [
                    str(f.get("field_name") or "")
                    for f in table_fields
                    if isinstance(f, dict)
                ]
                preview = "、".join([n for n in names if n][:12])
                return {
                    "ok": False,
                    "code": -1,
                    "msg": (
                        "未能把数据列对齐到飞书表头。"
                        f"表中现有列：{preview or '（空）'}。"
                        "请开通「新增字段」权限以便自动补列，或手动建好日期/数字列。"
                    )[:500],
                }
            write_records = remapped
    else:
        logger.warning(
            "bitable list fields failed, fallback exact names: %s",
            listed.get("msg"),
        )

    from urllib.parse import quote

    url = (
        f"https://{FEISHU_API_HOST}/open-apis/bitable/v1/apps/"
        f"{quote(token_app, safe='')}/tables/{quote(tid, safe='')}/records/batch_create"
    )
    out = _post_json(
        url,
        {"records": write_records},
        headers={"Authorization": f"Bearer {access}"},
    )
    if not out.get("ok"):
        msg = str(out.get("msg") or "")
        # 若仍 FieldNameNotFound，再拉一次表头硬对齐后重试一次
        if "FieldNameNotFound" in msg or "1254045" in msg:
            listed2 = list_table_fields(app_token=token_app, table_id=tid, access_token=access)
            if listed2.get("ok") and listed2.get("fields"):
                remapped2, _, _ = remap_records_to_table_fields(
                    records, listed2["fields"]  # type: ignore[arg-type]
                )
                if remapped2:
                    write_records = remapped2
                    out = _post_json(
                        url,
                        {"records": write_records},
                        headers={"Authorization": f"Bearer {access}"},
                    )
                    msg = str(out.get("msg") or msg)
        if not out.get("ok"):
            if "99991663" in msg or "token" in msg.lower():
                tok2 = get_tenant_access_token(force=True)
                if tok2.get("ok"):
                    access = str(tok2.get("tenant_access_token") or "")
                    out = _post_json(
                        url,
                        {"records": write_records},
                        headers={"Authorization": f"Bearer {access}"},
                    )
                    msg = str(out.get("msg") or msg)
        if not out.get("ok"):
            return {
                "ok": False,
                "code": out.get("code"),
                "msg": _friendly_bitable_error(out.get("code"), msg or str(out.get("msg") or "")),
                "raw": out.get("raw"),
            }

    data = out.get("data") if isinstance(out.get("data"), dict) else {}
    created = data.get("records") if isinstance(data.get("records"), list) else []
    ids: list[str] = []
    for row in created:
        if isinstance(row, dict) and row.get("record_id"):
            ids.append(str(row["record_id"]))
    return {"ok": True, "record_ids": ids, "count": len(ids) or len(write_records)}
