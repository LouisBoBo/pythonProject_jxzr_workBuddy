"""
从 OpenAPI / Swagger 生成可查对象草稿。

不写死某套 MES 的前缀（/api 或 /api/v1）、登录地址或分页参数。
一律从当前文档的 paths / servers / 查询参数推断。
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

_SKIP_SEGMENTS = frozenset(
    {
        "auth",
        "login",
        "logout",
        "signin",
        "sign-in",
        "health",
        "docs",
        "openapi",
        "redoc",
        "swagger",
        "token",
        "refresh",
        "me",
        "upload",
        "uploads",
        "download",
        "export",
        "import",
        "files",
        "static",
        "ping",
        "version",
    }
)
_SKIP_LAST = frozenset(
    {
        "export",
        "import",
        "download",
        "upload",
        "login",
        "logout",
        "health",
        "me",
        "docs",
        "token",
        "refresh",
        "toggle",
    }
)
_PATH_PARAM = re.compile(r"\{[^}]+\}")
_LOGIN_LAST = frozenset({"login", "signin", "sign-in", "token", "oauth"})
_PAGING_SIZE = frozenset({"size", "page_size", "pagesize", "per_page", "perpage"})
_PAGING_PAGE = frozenset({"page", "page_no", "pageno", "pagenum", "page_num"})
_PAGING_OFFSET = frozenset({"offset", "skip", "from"})


def _load_openapi_text(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("接口文档为空")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            "无法解析接口文档：请上传 OpenAPI/Swagger 的 JSON（推荐从 /openapi.json 下载）。"
            f" 详情：{exc}"
        ) from exc
    raise ValueError("接口文档须为 OpenAPI/Swagger JSON 对象")


def _operations(path_item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(path_item, dict):
        return out
    for method in ("get", "post", "put", "patch", "delete"):
        op = path_item.get(method)
        if isinstance(op, dict):
            out[method] = op
    return out


def _normalize_list_path(raw: str) -> str:
    s = (raw or "").strip()
    if not s.startswith("/"):
        s = "/" + s
    return s.rstrip("/") or "/"


def _path_segments(norm: str) -> list[str]:
    return [s for s in _normalize_list_path(norm).split("/") if s]


def _is_skipped_collection(norm: str) -> bool:
    segs = [s.lower() for s in _path_segments(norm)]
    if not segs:
        return True
    if segs[-1] in _SKIP_LAST:
        return True
    if segs[0] in _SKIP_SEGMENTS and len(segs) <= 2:
        return True
    if any(s in {"auth", "login", "token"} for s in segs):
        return True
    return False


def _entity_id_from_path(norm: str, strip_prefix: str = "") -> str:
    segs = _path_segments(norm)
    prefix_segs = _path_segments(strip_prefix) if strip_prefix else []
    if prefix_segs and segs[: len(prefix_segs)] == prefix_segs:
        segs = segs[len(prefix_segs) :]
    while segs and segs[0].lower() in {"api", "v1", "v2", "v3"}:
        segs = segs[1:]
    if not segs:
        segs = _path_segments(norm)[-1:]
    slug = "-".join(s.replace("_", "-").lower() for s in segs)
    return slug or "resource"


def _label_from_op(fallback: str, ops: dict[str, dict[str, Any]]) -> str:
    for method in ("get", "post"):
        op = ops.get(method) or {}
        summary = str(op.get("summary") or "").strip()
        if summary:
            for prefix in ("查询", "获取", "列出", "列表", "分页查询", "检索"):
                if summary.startswith(prefix):
                    summary = summary[len(prefix) :].lstrip(" ：:")
                    break
            if summary:
                return summary[:40]
        tags = op.get("tags")
        if isinstance(tags, list) and tags:
            tag = str(tags[0]).strip()
            if tag:
                return tag[:40]
    return fallback.replace("-", " ").replace("_", " ")


def _aliases_for(label: str, entity_id: str, last_seg: str) -> list[str]:
    aliases: list[str] = []
    for a in (label, entity_id, last_seg, last_seg.replace("-", ""), last_seg.replace("_", "-")):
        s = str(a).strip()
        if s and s not in aliases:
            aliases.append(s)
    return aliases[:12]


def _path_derived_aliases(norm: str, label: str, ops: dict[str, dict[str, Any]]) -> list[str]:
    """从路径片段与 OpenAPI 摘要推导通用别名（不写死某套 MES 实体 id）。"""
    import re

    out: list[str] = []
    segs = _path_segments(norm)
    while segs and segs[0].lower() in {"api", "v1", "v2", "v3"}:
        segs = segs[1:]
    for seg in segs:
        seg_l = seg.lower()
        if seg_l and seg_l not in out:
            out.append(seg_l)
        for part in re.split(r"[-_]", seg):
            p = part.strip().lower()
            if len(p) >= 2 and p not in out:
                out.append(p)
        compact = seg_l.replace("-", "").replace("_", "")
        if compact and compact not in out:
            out.append(compact)
    get_op = ops.get("get") or {}
    summary = str(get_op.get("summary") or "").strip()
    if summary and summary not in out:
        out.append(summary)
    tags = get_op.get("tags")
    if isinstance(tags, list):
        for tag in tags:
            t = str(tag or "").strip()
            if t and t not in out:
                out.append(t)
    if label:
        lbl = str(label).strip()
        if lbl and lbl not in out:
            out.append(lbl)
        if lbl and "列表" not in lbl and "清单" not in lbl:
            for suffix in ("列表", "清单"):
                cand = lbl + suffix
                if cand not in out:
                    out.append(cand)
    # 路径含 inventory/stock 等通用 token 时，补中文检索词（按 token，非写死 entity id）
    _token_zh: dict[str, tuple[str, ...]] = {
        "inventory": ("库存",),
        "stock": ("库存", "存货"),
        "warehouse": ("仓储", "仓库"),
        "material": ("物料",),
        "item": ("物料",),
        "location": ("库位", "货位"),
        "bin": ("库位", "货位"),
    }
    blob = " ".join(segs).lower()
    for token, zh_words in _token_zh.items():
        if token in blob or any(token in s for s in segs):
            for w in zh_words:
                if w not in out:
                    out.append(w)
                for suffix in ("列表", "清单", "明细"):
                    cand = w + suffix
                    if cand not in out:
                        out.append(cand)
    return out[:20]


def enrich_entity_aliases(entity: dict[str, Any]) -> dict[str, Any]:
    """合并 label/id/path 与 OpenAPI 摘要别名，便于自然语言命中。"""
    out = dict(entity)
    path = str(out.get("path") or "")
    last = _path_segments(path)[-1] if path else str(out.get("id") or "")
    label = str(out.get("label") or out.get("id") or "")
    derived = _path_derived_aliases(path, label, {"get": {}})
    existing = {
        str(a).strip()
        for a in (out.get("aliases") or [])
        if str(a).strip()
    }
    merged: list[str] = []
    for a in list(existing) + derived + [label, str(out.get("id") or "")]:
        s = str(a or "").strip()
        if s and s not in merged:
            merged.append(s)
    out["aliases"] = merged[:24]
    return out


def origin_from_url(url: str) -> str:
    raw = (url or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def _api_base_from_doc(doc: dict[str, Any]) -> str:
    servers = doc.get("servers")
    if isinstance(servers, list):
        for s in servers:
            if not isinstance(s, dict):
                continue
            origin = origin_from_url(str(s.get("url") or ""))
            if origin:
                try:
                    from safe_http import assert_http_url_allowed

                    return assert_http_url_allowed(origin, what="接口文档主机")
                except ValueError:
                    continue
    host = str(doc.get("host") or "").strip()
    if host:
        schemes = doc.get("schemes")
        scheme = "http"
        if isinstance(schemes, list) and schemes:
            scheme = str(schemes[0] or "http")
        origin = origin_from_url(f"{scheme}://{host}")
        if origin:
            try:
                from safe_http import assert_http_url_allowed

                return assert_http_url_allowed(origin, what="接口文档主机")
            except ValueError:
                return ""
    return ""


def swagger_base_path(doc: dict[str, Any]) -> str:
    """OpenAPI 2.0 basePath，例如 /api/v1。"""
    bp = str(doc.get("basePath") or "").strip()
    if not bp or bp == "/":
        return ""
    if not bp.startswith("/"):
        bp = "/" + bp
    return bp.rstrip("/") or ""


def _query_param_names(*sources: dict[str, Any] | None) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for src in sources:
        if not isinstance(src, dict):
            continue
        params = src.get("parameters")
        if not isinstance(params, list):
            continue
        for p in params:
            if not isinstance(p, dict):
                continue
            if str(p.get("in") or "") != "query":
                continue
            name = str(p.get("name") or "").strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _paging_from_names(names: list[str]) -> dict[str, str]:
    paging: dict[str, str] = {}
    for orig in names:
        key = orig.lower().replace("-", "_")
        compact = key.replace("_", "")
        if key == "limit":
            paging["limit"] = orig
        elif key in _PAGING_SIZE or compact in {"pagesize", "perpage"}:
            paging["page_size"] = orig
        elif key in _PAGING_PAGE or compact in {"pagenum", "pageno"}:
            paging["page"] = orig
        elif key in _PAGING_OFFSET:
            paging["offset"] = orig
    return paging


def _fields_from_op(*sources: dict[str, Any] | None) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    paging_names = set(_paging_from_names(_query_param_names(*sources)).values())
    seen: set[str] = set()
    for src in sources:
        if not isinstance(src, dict):
            continue
        params = src.get("parameters")
        if not isinstance(params, list):
            continue
        for p in params:
            if not isinstance(p, dict):
                continue
            if str(p.get("in") or "") != "query":
                continue
            name = str(p.get("name") or "").strip()
            if not name or name in paging_names or name in seen:
                continue
            seen.add(name)
            desc = str(p.get("description") or name).strip()
            fields.append({"name": name, "label": desc[:40] or name})
            if len(fields) >= 12:
                return fields
    return fields


def _resolve_ref(doc: dict[str, Any], ref: str) -> dict[str, Any] | None:
    if not ref.startswith("#/"):
        return None
    cur: Any = doc
    for part in ref[2:].split("/"):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur if isinstance(cur, dict) else None


def _list_keys_from_op(op: dict[str, Any], doc: dict[str, Any]) -> list[str]:
    """从 200 响应 schema 推断列表字段名（items/records/data 等）。"""
    resp = (op.get("responses") or {}).get("200") or (op.get("responses") or {}).get("201")
    if not isinstance(resp, dict):
        return []
    content = resp.get("content")
    if not isinstance(content, dict):
        return []
    schema: Any = None
    for body in content.values():
        if isinstance(body, dict) and isinstance(body.get("schema"), dict):
            schema = body["schema"]
            break
    if not isinstance(schema, dict):
        return []
    if "$ref" in schema:
        schema = _resolve_ref(doc, str(schema.get("$ref") or "")) or {}
    if schema.get("type") == "array":
        return []  # 响应本身就是数组
    props = schema.get("properties")
    if not isinstance(props, dict):
        return []
    keys: list[str] = []
    for name, spec in props.items():
        if not isinstance(spec, dict):
            continue
        resolved = spec
        if "$ref" in spec:
            resolved = _resolve_ref(doc, str(spec.get("$ref") or "")) or spec
        if resolved.get("type") == "array" or isinstance(resolved.get("items"), dict):
            keys.append(str(name))
    return keys[:6]


def _schema_object(doc: dict[str, Any], schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    if "$ref" in schema:
        return _resolve_ref(doc, str(schema.get("$ref") or "")) or {}
    return schema


def _item_schema_from_op(op: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any]:
    """从 200 响应推断列表元素 object schema，用于中文列名。"""
    resp = (op.get("responses") or {}).get("200") or (op.get("responses") or {}).get("201")
    if not isinstance(resp, dict):
        return {}
    content = resp.get("content")
    schema: Any = None
    if isinstance(content, dict):
        for body in content.values():
            if isinstance(body, dict) and isinstance(body.get("schema"), dict):
                schema = body["schema"]
                break
    if schema is None and isinstance(resp.get("schema"), dict):
        schema = resp["schema"]
    schema = _schema_object(doc, schema)
    if not schema:
        return {}
    if schema.get("type") == "array" or isinstance(schema.get("items"), dict):
        return _schema_object(doc, schema.get("items"))
    props = schema.get("properties")
    if not isinstance(props, dict):
        return {}
    for key in ("items", "records", "data", "results", "list", "rows"):
        if key not in props:
            continue
        spec = _schema_object(doc, props[key])
        if spec.get("type") == "array" or isinstance(spec.get("items"), dict):
            return _schema_object(doc, spec.get("items"))
        nested = spec.get("properties")
        if isinstance(nested, dict):
            for nk in ("items", "records", "list", "rows"):
                if nk not in nested:
                    continue
                inner = _schema_object(doc, nested[nk])
                if inner.get("type") == "array" or isinstance(inner.get("items"), dict):
                    return _schema_object(doc, inner.get("items"))
    return {}


def _response_fields_from_op(op: dict[str, Any], doc: dict[str, Any]) -> list[dict[str, str]]:
    item = _item_schema_from_op(op, doc)
    props = item.get("properties")
    if not isinstance(props, dict):
        return []
    fields: list[dict[str, str]] = []
    for name, spec in props.items():
        key = str(name or "").strip()
        if not key:
            continue
        resolved = spec if isinstance(spec, dict) else {}
        if "$ref" in resolved:
            resolved = _resolve_ref(doc, str(resolved.get("$ref") or "")) or resolved
        label = str(
            resolved.get("title")
            or resolved.get("description")
            or (spec.get("description") if isinstance(spec, dict) else "")
            or key
        ).strip()
        fields.append({"name": key, "label": (label[:40] or key)})
        if len(fields) >= 16:
            break
    return fields


def _looks_like_login(path: str, ops: dict[str, dict[str, Any]]) -> bool:
    if "post" not in ops:
        return False
    segs = [s.lower() for s in _path_segments(path)]
    last = segs[-1] if segs else ""
    if last in _LOGIN_LAST:
        return True
    summary = str((ops.get("post") or {}).get("summary") or "")
    op_id = str((ops.get("post") or {}).get("operationId") or "")
    blob = f"{summary} {op_id}"
    return bool(re.search(r"登录|登陆|sign[-_ ]?in|log[-_ ]?in", blob, re.I))


def login_paths_from_openapi(doc: dict[str, Any]) -> list[str]:
    paths = doc.get("paths")
    if not isinstance(paths, dict):
        return []
    out: list[str] = []
    base = swagger_base_path(doc)
    for raw_path, item in paths.items():
        if not isinstance(raw_path, str):
            continue
        ops = _operations(item if isinstance(item, dict) else {})
        norm = _normalize_list_path(raw_path)
        if base and not norm.startswith(base + "/") and norm != base:
            norm = (base.rstrip("/") + norm) if norm != "/" else base
        if _looks_like_login(norm, ops) and norm not in out:
            out.append(norm)
    return out


def login_body_spec_from_openapi(doc: dict[str, Any]) -> dict[str, Any]:
    """从登录 POST 的 requestBody 推断字段（username/password/enterprise_code 等）。"""
    paths = doc.get("paths")
    if not isinstance(paths, dict):
        return {"fields": ["username", "password"], "required": ["username", "password"]}
    base = swagger_base_path(doc)
    for raw_path, item in paths.items():
        if not isinstance(raw_path, str):
            continue
        path_item = item if isinstance(item, dict) else {}
        ops = _operations(path_item)
        norm = _normalize_list_path(raw_path)
        if base and not norm.startswith(base + "/") and norm != base:
            norm = (base.rstrip("/") + norm) if norm != "/" else base
        if not _looks_like_login(norm, ops):
            continue
        post = ops.get("post") or {}
        rb = post.get("requestBody")
        if not isinstance(rb, dict):
            break
        content = rb.get("content")
        schema: Any = None
        if isinstance(content, dict):
            for body in content.values():
                if isinstance(body, dict) and isinstance(body.get("schema"), dict):
                    schema = body["schema"]
                    break
        if isinstance(schema, dict) and "$ref" in schema:
            schema = _resolve_ref(doc, str(schema.get("$ref") or "")) or {}
        if not isinstance(schema, dict):
            break
        props = schema.get("properties")
        fields = [str(k) for k in props.keys()] if isinstance(props, dict) else []
        required = [str(x) for x in (schema.get("required") or []) if str(x)]
        if not fields:
            fields = ["username", "password"]
        if not required:
            required = ["username", "password"]
        return {"fields": fields, "required": required}
    return {"fields": ["username", "password"], "required": ["username", "password"]}


def openapi_to_entities(doc: dict[str, Any]) -> dict[str, Any]:
    """
    返回 {"entities": [...], "meta": {...}}。
    path / paging / login_paths / api_base 均来自当前文档。
    """
    paths = doc.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise ValueError("OpenAPI 中缺少 paths，无法生成可查实体")

    by_id: dict[str, dict[str, Any]] = {}
    swagger_base = swagger_base_path(doc)

    for raw_path, item in paths.items():
        if not isinstance(raw_path, str):
            continue
        path_item = item if isinstance(item, dict) else {}
        ops = _operations(path_item)
        norm = _normalize_list_path(raw_path)
        if swagger_base and not norm.startswith(swagger_base + "/") and norm != swagger_base:
            norm = swagger_base + (norm if norm != "/" else "")
        if _PATH_PARAM.search(raw_path):
            continue
        if _is_skipped_collection(norm):
            continue
        if "get" not in ops:
            continue

        last = _path_segments(norm)[-1]
        entity_id = _entity_id_from_path(norm, swagger_base)
        base_id = entity_id
        n = 2
        while entity_id in by_id and by_id[entity_id].get("path") != norm:
            entity_id = f"{base_id}-{n}"
            n += 1

        if entity_id in by_id:
            existing = by_id[entity_id]
            op_set = set(existing.get("ops") or [])
            op_set.add("query")
            if "post" in ops:
                op_set.add("import")
            existing["ops"] = sorted(op_set)
            continue

        op_list = ["query"]
        if "post" in ops:
            op_list.append("import")
        op_list.append("export")

        get_op = ops.get("get") or {}
        qnames = _query_param_names(path_item, get_op)
        paging = _paging_from_names(qnames)
        list_keys = _list_keys_from_op(get_op, doc)
        label = _label_from_op(last, ops)

        rec: dict[str, Any] = {
            "id": entity_id,
            "label": label,
            "aliases": _aliases_for(label, entity_id, last),
            "path": norm,
            "ops": op_list,
            "fields": _fields_from_op(path_item, get_op),
        }
        extra = _path_derived_aliases(norm, label, ops)
        rec["aliases"] = list(
            dict.fromkeys([*(rec.get("aliases") or []), *extra])
        )
        rec = enrich_entity_aliases(rec)
        columns = _response_fields_from_op(get_op, doc)
        if columns:
            rec["columns"] = columns
        if paging:
            rec["paging"] = paging
        if list_keys:
            rec["list_keys"] = list_keys
        by_id[entity_id] = rec

    login_paths = login_paths_from_openapi(doc)
    login_body = login_body_spec_from_openapi(doc)

    entities = sorted(by_id.values(), key=lambda e: e["id"])
    if not entities:
        raise ValueError(
            "未从接口文档识别到可用的列表接口。"
            "请确认文档含 GET 集合路径（可带或不带 /api、/v1）。"
        )

    title = ""
    info = doc.get("info")
    if isinstance(info, dict):
        title = str(info.get("title") or "").strip()

    prefix = swagger_base
    if not prefix:
        prefixes: list[str] = []
        for e in entities:
            segs = _path_segments(str(e.get("path") or ""))
            if segs and segs[0].lower() == "api":
                if len(segs) > 1 and segs[1].lower() in {"v1", "v2", "v3"}:
                    prefixes.append("/" + "/".join(segs[:2]))
                else:
                    prefixes.append("/api")
        prefix = max(set(prefixes), key=prefixes.count) if prefixes else ""

    meta: dict[str, Any] = {
        "generated_from": "openapi",
        "api_title": title,
        "entity_count": len(entities),
        "note": "根据当前接口文档生成；换平台请重新导入 OpenAPI，勿改代码。",
    }
    api_base = _api_base_from_doc(doc)
    if api_base:
        meta["api_base"] = api_base
    if login_paths:
        meta["login_paths"] = login_paths
    if login_body.get("required"):
        meta["login_required_fields"] = login_body["required"]
    if prefix:
        meta["path_prefix"] = prefix

    return {"entities": entities, "meta": meta}


def generate_entities_from_openapi_text(raw: str) -> dict[str, Any]:
    doc = _load_openapi_text(raw)
    return openapi_to_entities(doc)
