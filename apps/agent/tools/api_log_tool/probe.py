"""
接口目录批量探活。

模式：
- live：只打 PLATFORM_BASE_URL，默认仅 GET/HEAD（防误改生产）
- sandbox：不碰生产平台；可测全部方法
  - 未配置 API_PROBE_SANDBOX_URL → 进程内本地模拟（内存态，不改平台、不改业务落盘）
  - 已配置 → 真实 HTTP 打到沙箱 URL（须过 host 白名单）
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from config import Config
from tools.api_log_tool.call_store import append_api_call, path_pattern_key, query_api_calls
from tools.api_log_tool.catalog import load_index

_SAFE_METHODS = frozenset({"GET", "HEAD"})
_ALL_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"})
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_TEMPLATE_SEG = re.compile(r"\{([^{}]+)\}")
# 路径中的动作段（Spring 风格 /api/customers/create|get|delete）
_ACTION_SEGS = frozenset(
    {
        "create",
        "add",
        "save",
        "insert",
        "get",
        "getbyid",
        "query",
        "list",
        "detail",
        "details",
        "info",
        "find",
        "update",
        "edit",
        "modify",
        "put",
        "patch",
        "delete",
        "remove",
        "del",
    }
)


def _resource_family(path: str) -> str:
    """资源族：取第一个路径参数之前的前缀，并去掉动作段。

    /api/parts/{id}/alternates → /api/parts
    /api/parts/get/{id} → /api/parts
    /api/customers/update-discount/{id} → /api/customers
    /api/parts/alternates/{alternateId} → /api/parts/alternates
    """
    p = (path or "").split("?", 1)[0]
    m = _TEMPLATE_SEG.search(p)
    if m:
        p = p[: m.start()]
    p = p.rstrip("/") or "/"
    parts = [x for x in p.split("/") if x]
    if not parts:
        return "/"

    def _is_action(seg: str) -> bool:
        s = seg.lower()
        if s in _ACTION_SEGS:
            return True
        return s.startswith(("update-", "get-", "delete-", "set-", "change-", "modify-"))

    while parts and _is_action(parts[-1]):
        parts.pop()
    if parts and (
        parts[-1].isdigit()
        or parts[-1].startswith("sandbox")
        or parts[-1].startswith("seed-")
        or re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            parts[-1],
        )
    ):
        parts.pop()
    return "/" + "/".join(parts) if parts else "/"


def _param_family_hint(param_name: str) -> str | None:
    """根据参数名推断应使用的资源族 id。"""
    n = (param_name or "").lower()
    if "supplier" in n:
        return "/api/suppliers"
    if "customer" in n:
        return "/api/customers"
    if "order" in n:
        return "/api/orders"
    if "alternate" in n:
        return "/api/parts/alternates"
    if "part" in n:
        return "/api/parts"
    if "logistic" in n or "shipment" in n:
        return "/api/logistics"
    if "inventory" in n or "lot" in n:
        return "/api/inventory"
    return None


def _fill_path_with_ids(path: str, family_ids: dict[str, str], family: str, fallback: str) -> str | None:
    """按参数名选择 id 填充模板；保证全部可测。"""
    if not _TEMPLATE_SEG.search(path):
        return path

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        hint = _param_family_hint(name)
        if hint and family_ids.get(hint):
            return str(family_ids[hint])
        if family_ids.get(family):
            return str(family_ids[family])
        # 父级回退：/api/parts/alternates → /api/parts
        parts = [x for x in family.split("/") if x]
        while len(parts) >= 2:
            parts.pop()
            parent = "/" + "/".join(parts)
            if family_ids.get(parent):
                return str(family_ids[parent])
        return str(fallback)

    return _TEMPLATE_SEG.sub(repl, path)


def _required_families_for_path(path: str, family: str) -> list[str]:
    """该路径探测前需要预置 id 的资源族（含跨资源参数）。"""
    needed: list[str] = []
    for m in _TEMPLATE_SEG.finditer(path or ""):
        hint = _param_family_hint(m.group(1))
        if hint and hint not in needed:
            needed.append(hint)
    if family and family not in needed:
        needed.append(family)
    # 嵌套子资源：/api/parts/alternates 依赖父 /api/parts
    parts = [x for x in (family or "").split("/") if x]
    while len(parts) >= 3:
        parts.pop()
        parent = "/" + "/".join(parts)
        if parent not in needed:
            needed.insert(0, parent)
    return needed


def _ensure_id_in_family_store(family: str, item_id: str) -> None:
    """local_mock：保证 path 所属桶里也有该 id（跨资源参数填充后防 404）。"""
    coll = (family or "/").rstrip("/") or "/"
    items = _SANDBOX_STORE.setdefault(coll, [])
    if not any(str(x.get("id")) == str(item_id) for x in items):
        items.append(
            {
                "id": str(item_id),
                "name": f"sandbox-{item_id}",
                "sandbox": True,
                "seeded": True,
            }
        )


def _is_create_endpoint(method: str, path: str) -> bool:
    if str(method).upper() != "POST":
        return False
    lower = path.lower()
    if _TEMPLATE_SEG.search(path):
        return False
    segs = [x for x in lower.split("/") if x]
    if segs and segs[-1] in {"create", "add", "save", "insert"}:
        return True
    # REST：POST /api/v1/work-orders
    if segs and segs[-1] not in _ACTION_SEGS:
        return True
    return False


def _extract_created_id(payload: Any) -> str | None:
    """从创建响应里取资源 id（通用字段名）。"""
    if payload is None:
        return None
    if isinstance(payload, (int, float)):
        return str(int(payload)) if float(payload).is_integer() else str(payload)
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    if not isinstance(payload, dict):
        return None
    for key in (
        "id",
        "Id",
        "ID",
        "orderId",
        "order_id",
        "customerId",
        "customer_id",
        "partId",
        "part_id",
        "supplierId",
        "planId",
        "dataId",
    ):
        v = payload.get(key)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    data = payload.get("data")
    if isinstance(data, dict):
        return _extract_created_id(data)
    if isinstance(data, (str, int, float)):
        return _extract_created_id(data)
    result = payload.get("result")
    if isinstance(result, dict):
        return _extract_created_id(result)
    return None

# 进程内沙箱内存（仅 sandbox/local_mock；不落业务库、不写平台）
_SANDBOX_STORE: dict[str, list[dict[str, Any]]] = {}


def _sandbox_url() -> str | None:
    raw = (os.getenv("API_PROBE_SANDBOX_URL") or "").strip()
    return raw.rstrip("/") if raw else None


def _host_allowed_for_sandbox(url: str) -> bool:
    """与目录 URL 白名单同构：localhost / PLATFORM host / API_DOCS_URL_ALLOWLIST。"""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    allowed = {"127.0.0.1", "localhost"}
    try:
        base_host = (urlparse(Config.PLATFORM_BASE_URL).hostname or "").lower()
        if base_host:
            allowed.add(base_host)
    except Exception:
        pass
    extra = os.getenv("API_DOCS_URL_ALLOWLIST", "")
    for part in extra.split(","):
        h = part.strip().lower()
        if h:
            allowed.add(h)
    # 沙箱专用扩展
    extra_sb = os.getenv("API_PROBE_SANDBOX_URL_ALLOWLIST", "")
    for part in extra_sb.split(","):
        h = part.strip().lower()
        if h:
            allowed.add(h)
    return host in allowed


def _log_and_result(
    *,
    method: str,
    path: str,
    status: int | None,
    ok: bool,
    latency_ms: float,
    source: str,
    error: str | None = None,
    sandbox_kind: str | None = None,
    path_key: str | None = None,
) -> dict[str, Any]:
    key = path_key or path_pattern_key(path)
    row: dict[str, Any] = {
        "method": method,
        "path": path,
        "path_key": key,
        "status": status,
        "ok": ok,
        "latency_ms": latency_ms,
        "source": source,
        "error": (error[:200] if error else None),
    }
    if sandbox_kind:
        row["sandbox_kind"] = sandbox_kind
    append_api_call(row)
    out = {
        "method": method,
        "path": path,
        "path_key": key,
        "status": status,
        "ok": ok,
        "latency_ms": round(latency_ms, 1),
        "source": source,
    }
    if error:
        out["error"] = error
    if sandbox_kind:
        out["sandbox_kind"] = sandbox_kind
    return out


def _login_service_token(base: str, source: str) -> str | None:
    if not Config.ERP_USERNAME or not Config.ERP_PASSWORD:
        return None
    body: dict[str, Any] = {
        "username": Config.ERP_USERNAME,
        "password": Config.ERP_PASSWORD,
    }
    if Config.ERP_ENTERPRISE_CODE:
        body["enterprise_code"] = Config.ERP_ENTERPRISE_CODE
    path = "/api/v1/auth/login"
    data = json.dumps(body).encode()
    req = Request(
        f"{base}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode() or "{}")
            token = result.get("access_token") or None
        _log_and_result(
            method="POST",
            path=path,
            status=200,
            ok=True,
            latency_ms=(time.perf_counter() - t0) * 1000,
            source=source,
        )
        return token
    except Exception as e:
        _log_and_result(
            method="POST",
            path=path,
            status=None,
            ok=False,
            latency_ms=(time.perf_counter() - t0) * 1000,
            source=source,
            error=f"login_failed: {e}",
        )
        return None


def _build_headers(base: str, source: str) -> dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    token = None
    try:
        from tools.platform_api import get_request_erp_token

        token = get_request_erp_token()
    except Exception:
        token = None
    if not token:
        token = _login_service_token(base, source)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fill_path_templates(path: str, sample_id: str | None) -> str | None:
    if not _TEMPLATE_SEG.search(path):
        return path
    if not sample_id:
        return None
    return _TEMPLATE_SEG.sub(str(sample_id), path)


def _seen_keys(lookback_days: int) -> set[tuple[str, str]]:
    since_ts = time.time() - max(1, int(lookback_days or 7)) * 86400
    keys: set[tuple[str, str]] = set()
    offset = 0
    while True:
        page = query_api_calls(since_ts=since_ts, offset=offset, limit=200)
        items = page.get("items") or []
        for row in items:
            method = str(row.get("method") or "GET").upper()
            key = str(row.get("path_key") or path_pattern_key(str(row.get("path") or "")))
            keys.add((method, key))
        if not page.get("has_more") or not items:
            break
        offset += len(items)
        if offset > 20000:
            break
    return keys


def _stub_body(
    method: str,
    path: str,
    sample_id: str | None = None,
    *,
    for_create: bool = False,
) -> bytes | None:
    if method in ("GET", "HEAD", "OPTIONS", "DELETE"):
        return None
    payload: dict[str, Any] = {
        "sandbox": True,
        "name": f"sandbox-{method.lower()}",
        "code": f"SB-{int(time.time()) % 100000}",
    }
    sid = (sample_id or "").strip()
    if sid:
        payload["id"] = sid
        payload["name"] = f"sandbox-{method.lower()}-{sid}"
        payload["code"] = f"SB-{sid}"
    elif not for_create:
        # 非创建且无 id 时给占位，避免部分框架拒空 body
        sid = f"sandbox-{int(time.time()) % 100000}"
        payload["id"] = sid
    return json.dumps(payload).encode()


def _http_probe_one(
    method: str,
    path: str,
    timeout: float,
    headers: dict[str, str],
    base: str,
    source: str,
    sandbox_kind: str | None = None,
    catalog_path: str | None = None,
    sample_id: str | None = None,
) -> dict[str, Any]:
    url = f"{base}{path}"
    body = _stub_body(
        method,
        path,
        sample_id=sample_id,
        for_create=bool(sample_id is None and method.upper() == "POST"),
    )
    req = Request(url, data=body, headers=headers, method=method)
    t0 = time.perf_counter()
    key = path_pattern_key(catalog_path or path)

    def _finish(
        *,
        status: int | None,
        ok: bool,
        error: str | None = None,
        created_id: str | None = None,
        latency_ms: float | None = None,
    ) -> dict[str, Any]:
        lat = latency_ms if latency_ms is not None else (time.perf_counter() - t0) * 1000
        out = _log_and_result(
            method=method,
            path=path,
            status=status,
            ok=ok,
            latency_ms=lat,
            source=source,
            error=error,
            sandbox_kind=sandbox_kind,
            path_key=key,
        )
        if created_id:
            out["created_id"] = created_id
        return out

    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read(65536)
            status = getattr(resp, "status", None) or 200
            latency_ms = (time.perf_counter() - t0) * 1000
            ok = 200 <= int(status) < 400
            created_id = None
            if ok and raw:
                try:
                    parsed = json.loads(raw.decode("utf-8", errors="replace") or "{}")
                    created_id = _extract_created_id(parsed)
                except Exception:
                    created_id = None
            return _finish(
                status=status,
                ok=ok,
                error=None if ok else f"HTTP {status}",
                created_id=created_id,
                latency_ms=latency_ms,
            )
    except HTTPError as e:
        err_body = b""
        try:
            err_body = e.read(65536)
        except Exception:
            pass
        created_id = None
        # 少数框架用 200 外状态仍回 id；一般不取
        err = f"HTTP {e.code}: {e.reason}"
        return _finish(status=e.code, ok=False, error=err, created_id=created_id)
    except URLError as e:
        return _finish(status=None, ok=False, error=f"连接失败: {e.reason}")
    except Exception as e:
        return _finish(status=None, ok=False, error=str(e)[:200])


def _local_mock_probe_one(
    method: str,
    path: str,
    sample_id: str | None,
    *,
    is_item: bool,
    catalog_path: str,
    family: str | None = None,
) -> dict[str, Any]:
    """进程内模拟 REST：内存读写，零网络、不改平台。同资源族共用一个桶。"""
    t0 = time.perf_counter()
    method = method.upper()
    path_norm = path.split("?", 1)[0].rstrip("/") or "/"
    # 与 remote 沙箱一致：剥中间父 id，归到资源族桶
    parts = [x for x in path_norm.split("/") if x]
    item_id: str | None = None
    if parts:
        last = parts[-1]
        if (
            last.isdigit()
            or last.startswith(("sandbox", "seed-", "alt-"))
            or re.fullmatch(
                r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                last,
            )
        ):
            item_id = last
            parts = parts[:-1]
        while parts and (
            parts[-1].lower() in _ACTION_SEGS
            or parts[-1].lower().startswith(("update-", "get-", "delete-"))
        ):
            parts.pop()
        parts = [
            x
            for x in parts
            if not (
                x.isdigit()
                or x.startswith(("sandbox", "seed-", "alt-"))
                or re.fullmatch(
                    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                    x,
                )
            )
        ]
    coll = ("/" + "/".join(parts)) if parts else ((family or _resource_family(catalog_path or path)).rstrip("/") or "/")
    # 末段非 id 的模板路径（如 /parts/{id}/alternates）按集合处理
    effective_item = bool(is_item and item_id)
    items = _SANDBOX_STORE.setdefault(coll, [])
    status = 200
    ok = True
    error = None
    created_id: str | None = None

    try:
        if method == "OPTIONS":
            status = 204
        elif method == "HEAD":
            status = 200
        elif method == "GET":
            if effective_item and item_id:
                found = next((x for x in items if str(x.get("id")) == str(item_id)), None)
                if not found:
                    status, ok, error = 404, False, "sandbox: not found"
            else:
                status = 200
        elif method == "POST":
            # 创建（含 /create、嵌套集合）：写入资源族桶并返回 id
            new_id = sample_id or f"sandbox-{len(items) + 1}"
            if not any(str(x.get("id")) == str(new_id) for x in items):
                items.append({"id": new_id, "name": f"sandbox-{new_id}", "sandbox": True})
            status = 201
            created_id = str(new_id)
        elif method in ("PUT", "PATCH"):
            if not item_id:
                status, ok, error = 405, False, "sandbox: write needs id"
            else:
                found = next((x for x in items if str(x.get("id")) == str(item_id)), None)
                if found:
                    found["name"] = f"updated-{item_id}"
                    found["sandbox"] = True
                    status = 200
                else:
                    items.append({"id": item_id, "name": f"upsert-{item_id}", "sandbox": True})
                    status = 201
        elif method == "DELETE":
            if not item_id:
                status, ok, error = 405, False, "sandbox: DELETE needs id"
            else:
                before = len(items)
                _SANDBOX_STORE[coll] = [x for x in items if str(x.get("id")) != str(item_id)]
                status = 204 if len(_SANDBOX_STORE[coll]) < before else 404
                ok = status == 204
                if not ok:
                    error = "sandbox: not found"
        else:
            status, ok, error = 405, False, f"sandbox: method {method} unsupported"
    except Exception as e:
        status, ok, error = 500, False, f"sandbox_internal: {e}"

    latency_ms = (time.perf_counter() - t0) * 1000
    out = _log_and_result(
        method=method,
        path=path,
        status=status,
        ok=ok,
        latency_ms=latency_ms,
        source="sandbox",
        error=error,
        sandbox_kind="local_mock",
        path_key=path_pattern_key(catalog_path),
    )
    if created_id:
        out["created_id"] = created_id
    return out


def _seed_family_record(
    *,
    family: str,
    preferred_id: str | None,
    create_item: dict[str, Any] | None,
    item_write: dict[str, Any] | None,
    nested_create: dict[str, Any] | None,
    mode_l: str,
    sandbox_kind: str | None,
    headers: dict[str, str],
    base: str,
    source: str,
    timeout: float,
    family_ids: dict[str, str],
) -> str:
    """确保资源族已有可测 id：优先创建接口，否则 PUT 预置，本地则直接写入内存桶。"""
    new_id = (preferred_id or "").strip() or f"seed-{abs(hash(family)) % 100000}"

    if mode_l == "sandbox" and sandbox_kind == "local_mock":
        # 嵌套创建：如 POST /api/parts/{id}/alternates
        if nested_create and family.endswith("/alternates"):
            parent = family.rsplit("/", 1)[0]
            parent_id = family_ids.get(parent) or new_id
            _ensure_id_in_family_store(parent, str(parent_id))
            family_ids.setdefault(parent, str(parent_id))
            alt_id = f"alt-{parent_id}"
            _ensure_id_in_family_store(family, alt_id)
            return alt_id
        _ensure_id_in_family_store(family, new_id)
        return new_id

    # remote / live：尽量走真实创建或 upsert
    if nested_create and family.endswith("/alternates"):
        parent = family.rsplit("/", 1)[0]
        parent_id = family_ids.get(parent) or new_id
        filled = _fill_path_templates(nested_create["path"], str(parent_id))
        if filled:
            r = _http_probe_one(
                "POST",
                filled,
                timeout,
                headers,
                base,
                source,
                sandbox_kind=sandbox_kind,
                catalog_path=nested_create["path"],
                sample_id=new_id,
            )
            if r.get("ok"):
                return str(r.get("created_id") or new_id)

    if create_item:
        path = create_item.get("probe_path") or create_item["path"]
        r = _http_probe_one(
            "POST",
            path,
            timeout,
            headers,
            base,
            source,
            sandbox_kind=sandbox_kind,
            catalog_path=create_item["path"],
            sample_id=new_id,
        )
        if r.get("ok"):
            return str(r.get("created_id") or new_id)

    if item_write:
        filled = _fill_path_templates(item_write["path"], new_id)
        if filled:
            r = _http_probe_one(
                str(item_write.get("method") or "PUT"),
                filled,
                timeout,
                headers,
                base,
                source,
                sandbox_kind=sandbox_kind,
                catalog_path=item_write["path"],
                sample_id=new_id,
            )
            if r.get("ok"):
                return new_id

    # 推断 create 路径再试一次（Spring 风格）
    for guess in (f"{family.rstrip('/')}/create", family.rstrip("/") or "/"):
        r = _http_probe_one(
            "POST",
            guess,
            timeout,
            headers,
            base,
            source,
            sandbox_kind=sandbox_kind,
            catalog_path=guess,
            sample_id=new_id,
        )
        if r.get("ok"):
            return str(r.get("created_id") or new_id)

    # 最后：直接 PUT 到 {family}/{id}，保证桶里有记录
    put_path = f"{family.rstrip('/')}/{new_id}"
    r = _http_probe_one(
        "PUT",
        put_path,
        timeout,
        headers,
        base,
        source,
        sandbox_kind=sandbox_kind,
        catalog_path=put_path,
        sample_id=new_id,
    )
    return new_id


def _ensure_remote_id(
    *,
    family: str,
    item_id: str,
    headers: dict[str, str],
    base: str,
    source: str,
    sandbox_kind: str | None,
    timeout: float,
) -> None:
    """remote 沙箱：把 id 写入目标 path 所属桶，避免跨资源参数 404。"""
    put_path = f"{(family or '/').rstrip('/')}/{item_id}"
    _http_probe_one(
        "PUT",
        put_path,
        timeout,
        headers,
        base,
        source,
        sandbox_kind=sandbox_kind,
        catalog_path=put_path,
        sample_id=item_id,
    )

def reset_local_sandbox_store() -> None:
    """测试或用户显式清空本地沙箱内存。"""
    _SANDBOX_STORE.clear()


def run_catalog_probe(
    *,
    mode: str = "sandbox",
    methods: list[str] | None = None,
    only_unseen: bool = False,
    lookback_days: int = 7,
    sample_id: str | None = None,
    keyword: str | None = None,
    tag: str | None = None,
    limit: int = 0,
    timeout_sec: float = 10.0,
    include_writes: bool | None = None,
    reset_sandbox: bool = True,
) -> dict[str, Any]:
    """批量探活。文档接口测试默认 sandbox；live 仅只读生产且须显式指定。"""
    index = load_index()
    if not index:
        return {
            "error": "尚未构建接口目录",
            "hint": "先 build_api_catalog(docs_url=...) 或 file_path=...",
        }

    mode_l = (mode or "live").strip().lower()
    if mode_l not in ("live", "sandbox"):
        return {"error": f"不支持的 mode: {mode}", "hint": "使用 live 或 sandbox"}

    # 沙箱探活前清掉历史 sandbox/probe 日志，避免旧 404 污染 summarize
    log_cleared: dict[str, Any] | None = None
    if mode_l == "sandbox":
        from tools.api_log_tool.call_store import clear_call_logs

        log_cleared = clear_call_logs(keep_sources={"erp"})

    sandbox_url = _sandbox_url()
    if mode_l == "sandbox":
        if sandbox_url:
            if not _host_allowed_for_sandbox(sandbox_url):
                return {
                    "error": f"沙箱 URL host 不在白名单: {urlparse(sandbox_url).hostname}",
                    "hint": "配置 API_PROBE_SANDBOX_URL_ALLOWLIST 或使用 localhost / PLATFORM 同 host",
                }
            sandbox_kind = "remote_url"
            base = sandbox_url
            source = "sandbox"
            # remote：尽量重置内存，避免上次 DELETE 残留导致本轮 404
            try:
                urlopen(Request(f"{base}/__reset", method="POST"), timeout=3)
            except Exception:
                pass
        else:
            sandbox_kind = "local_mock"
            base = "sandbox://local"
            source = "sandbox"
            if reset_sandbox:
                reset_local_sandbox_store()
        # 沙箱默认允许写
        if include_writes is None:
            include_writes = True
    else:
        sandbox_kind = None
        base = Config.PLATFORM_BASE_URL.rstrip("/")
        source = "probe"
        if include_writes is None:
            include_writes = False
        if include_writes:
            return {
                "error": "live 模式禁止写探活",
                "hint": (
                    "请改用 probe_api_catalog(mode='sandbox')："
                    "本地模拟不改平台；或设置 API_PROBE_SANDBOX_URL 打真实沙箱环境。"
                ),
            }

    if include_writes:
        allowed = set(_ALL_METHODS)
    else:
        allowed = set(_SAFE_METHODS)
    if methods:
        allowed &= {m.upper() for m in methods}
    if not allowed:
        return {"error": "无可用探活方法"}

    # 每轮唯一 sample，避免 remote 沙箱残留 DELETE 状态
    sample = (sample_id or "").strip() or None
    if mode_l == "sandbox" and not sample:
        sample = f"seed-{int(time.time()) % 1000000}"

    seen = _seen_keys(lookback_days) if only_unseen else set()
    kw = (keyword or "").strip().lower() or None
    tg = (tag or "").strip().lower() or None
    # limit<=0：测目录全部（上限 200）；默认由工具层传 0 表示全量
    raw_limit = int(limit if limit is not None else 0)
    if raw_limit <= 0:
        limit = 200
    else:
        limit = max(1, min(raw_limit, 200))
    timeout = max(2.0, min(float(timeout_sec or 10), 30.0))
    probe_started_ts = time.time()

    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for ep in index.get("endpoints") or []:
        method = str(ep.get("method") or "GET").upper()
        path = str(ep.get("path") or "")
        if not path:
            continue
        if kw and kw not in path.lower() and kw not in str(ep.get("summary") or "").lower():
            continue
        if tg and not any(tg in str(t).lower() for t in (ep.get("tags") or [])):
            continue

        if method not in allowed:
            reason = "write_skipped" if method in _WRITE_METHODS else "method_not_allowed"
            skipped.append(
                {
                    "method": method,
                    "path": path,
                    "reason": reason,
                    "note": (
                        "live 模式跳过写接口；改用 mode=sandbox 可测全部方法"
                        if reason == "write_skipped"
                        else None
                    ),
                }
            )
            continue

        key = path_pattern_key(path)
        if only_unseen and (method, key) in seen:
            skipped.append(
                {"method": method, "path": path, "path_key": key, "reason": "already_seen"}
            )
            continue

        filled = None
        if not _TEMPLATE_SEG.search(path):
            filled = path
        # 含模板的路径延后到执行时用「创建返回的 id」填充

        family = _resource_family(path)
        # 仅「末段是路径参数」才算单资源；/api/parts/{id}/alternates 是集合
        is_item = bool(re.search(r"/\{[^{}]+\}/?$", path.split("?", 1)[0]))
        is_nested_create = (
            method == "POST"
            and bool(_TEMPLATE_SEG.search(path))
            and not is_item
            and not path.rstrip("/").lower().endswith(
                ("/create", "/add", "/save", "/insert", "/update", "/delete", "/get")
            )
        )

        candidates.append(
            {
                "method": method,
                "path": path,
                "probe_path": filled,  # 无模板时已定；有模板时执行前再填
                "path_key": key,
                "summary": ep.get("summary") or "",
                "is_item": is_item,
                "is_create": _is_create_endpoint(method, path),
                "is_nested_create": is_nested_create,
                "family": family,
                "needs_id": bool(_TEMPLATE_SEG.search(path)),
            }
        )

    # 沙箱：先创建(POST)，再列表/改，再按 id 查，最后删
    if mode_l == "sandbox":
        def _sort_key(it: dict[str, Any]) -> tuple[int, str, str]:
            m = it["method"]
            if it.get("is_create"):
                phase = 0
            elif it.get("is_nested_create"):
                phase = 1
            elif m == "POST":
                phase = 2
            elif m in ("GET", "HEAD", "OPTIONS") and not it.get("is_item"):
                phase = 3
            elif m in ("PUT", "PATCH"):
                phase = 4
            elif m in ("GET", "HEAD") and it.get("is_item"):
                phase = 5
            elif m == "DELETE":
                phase = 6
            else:
                phase = 7
            return (phase, str(it.get("family") or ""), it["path"])

        candidates.sort(key=_sort_key)

    # 全量优先：先纳入全部创建，再补其余，避免 limit 截断导致无 id
    creates = [c for c in candidates if c.get("is_create")]
    rest = [c for c in candidates if not c.get("is_create")]
    ordered = creates + rest
    to_run = ordered[:limit]

    headers: dict[str, str] = {}
    if not (mode_l == "sandbox" and sandbox_kind == "local_mock"):
        headers = _build_headers(base, source)

    create_by_family = {
        str(c.get("family")): c for c in candidates if c.get("is_create") and c.get("family")
    }
    write_by_family: dict[str, dict[str, Any]] = {}
    for c in candidates:
        if not c.get("needs_id"):
            continue
        if str(c.get("method") or "").upper() not in ("PUT", "PATCH"):
            continue
        fam = str(c.get("family") or "")
        if fam and fam not in write_by_family:
            write_by_family[fam] = c

    nested_create_by_child: dict[str, dict[str, Any]] = {}
    for c in candidates:
        if not c.get("is_nested_create"):
            continue
        # POST /api/parts/{id}/alternates → 子资源族 /api/parts/alternates
        path = str(c.get("path") or "")
        segs = [x for x in path.split("/") if x and not x.startswith("{")]
        if segs:
            child_fam = "/" + "/".join(segs)
            nested_create_by_child.setdefault(child_fam, c)

    # 资源族 → 创建/预置后的真实 id
    family_ids: dict[str, str] = {}
    results = []
    for item in to_run:
        family = str(item.get("family") or _resource_family(item["path"]))
        use_id = family_ids.get(family)

        if item.get("needs_id") or item.get("is_nested_create"):
            for need_fam in _required_families_for_path(item["path"], family):
                if family_ids.get(need_fam):
                    continue
                # 子资源 /api/parts/alternates：若有嵌套创建接口，先确保父 id
                nested = nested_create_by_child.get(need_fam)
                sid = _seed_family_record(
                    family=need_fam,
                    preferred_id=sample if need_fam == family else f"{sample}-{abs(hash(need_fam)) % 10000}",
                    create_item=create_by_family.get(need_fam),
                    item_write=write_by_family.get(need_fam),
                    nested_create=nested,
                    mode_l=mode_l,
                    sandbox_kind=sandbox_kind,
                    headers=headers,
                    base=base,
                    source=source,
                    timeout=timeout,
                    family_ids=family_ids,
                )
                family_ids[need_fam] = str(sid)
            use_id = family_ids.get(family) or sample
            probe_path = _fill_path_with_ids(item["path"], family_ids, family, str(use_id))
            if probe_path is None:
                skipped.append(
                    {
                        "method": item["method"],
                        "path": item["path"],
                        "reason": "bad_template",
                        "note": "路径模板无法填充",
                    }
                )
                continue
            # 跨资源参数：保证 path 所属桶也有填充后的 id
            for seg in probe_path.split("/"):
                if not seg:
                    continue
                if seg.isdigit() or seg.startswith(("sandbox", "seed-", "alt-")) or re.fullmatch(
                    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                    seg,
                ):
                    if mode_l == "sandbox" and sandbox_kind == "local_mock":
                        _ensure_id_in_family_store(family, seg)
                    elif mode_l == "sandbox" and sandbox_kind == "remote_url":
                        _ensure_remote_id(
                            family=family,
                            item_id=seg,
                            headers=headers,
                            base=base,
                            source=source,
                            sandbox_kind=sandbox_kind,
                            timeout=timeout,
                        )
        else:
            probe_path = item.get("probe_path") or item["path"]

        if item.get("is_create"):
            body_id = family_ids.get(family)
        else:
            body_id = family_ids.get(family) or use_id

        if mode_l == "sandbox" and sandbox_kind == "local_mock":
            r = _local_mock_probe_one(
                item["method"],
                probe_path,
                None if item.get("is_create") and not body_id else body_id,
                is_item=bool(item.get("is_item")),
                catalog_path=item["path"],
                family=family,
            )
        else:
            r = _http_probe_one(
                item["method"],
                probe_path,
                timeout,
                headers,
                base,
                source,
                sandbox_kind=sandbox_kind,
                catalog_path=item["path"],
                sample_id=None if item.get("is_create") and not body_id else body_id,
            )
        r["catalog_path"] = item["path"]
        r["summary"] = item["summary"]
        r["resource_family"] = family
        if use_id and item.get("needs_id"):
            r["used_id"] = use_id

        # 创建成功 → 记下 id，供同族后续增删改查
        if r.get("ok") and item.get("is_create"):
            cid = r.get("created_id") or body_id or use_id or sample
            if cid:
                family_ids[family] = str(cid)
                r["created_id"] = str(cid)
        # 嵌套创建成功 → 记到子资源族
        if r.get("ok") and item.get("is_nested_create"):
            cid = r.get("created_id")
            segs = [x for x in str(item.get("path") or "").split("/") if x and not x.startswith("{")]
            if cid and segs:
                child_fam = "/" + "/".join(segs)
                family_ids[child_fam] = str(cid)
                r["created_id"] = str(cid)

        results.append(r)

    ok_n = sum(1 for r in results if r.get("ok"))
    fail_n = len(results) - ok_n

    notes = []
    if mode_l == "sandbox" and sandbox_kind == "local_mock":
        notes.append(
            "sandbox/local_mock：进程内模拟，不请求平台、不改平台数据；"
            "仅写入 api_calls 分析日志（source=sandbox）。"
            "结论表示「目录可覆盖/工具链」，不代表生产接口真实健康。"
        )
    elif mode_l == "sandbox" and sandbox_kind == "remote_url":
        notes.append(
            f"sandbox/remote_url：请求打到 {base}，不碰 PLATFORM_BASE_URL 生产配置；"
            "请确认该环境可接受写操作。"
        )
    else:
        notes.append("live：仅只读探活生产 PLATFORM_BASE_URL；写接口已跳过。")
    if family_ids:
        notes.append(
            "已按「先创建/预置 id，再查改删」联动（不跳过依赖 id 的接口）："
            + ", ".join(f"{k}→{v}" for k, v in list(family_ids.items())[:8])
        )
    notes.append("请接着 summarize_api_doc_vs_logs；回复须区分 sandbox 与生产证据。")
    notes.append("依赖 id 的接口会自动创建或预置后再测，默认不因缺 id 跳过。")
    if log_cleared:
        notes.append(
            f"已清理历史探活日志（removed={log_cleared.get('removed')}，kept_erp={log_cleared.get('kept')}），"
            "避免旧失败污染本次健康汇总。"
        )

    return {
        "status": "ok",
        "mode": mode_l,
        "sandbox_kind": sandbox_kind,
        "base_url": base,
        "probe_started_at": datetime.fromtimestamp(probe_started_ts).strftime("%Y-%m-%d %H:%M:%S"),
        "policy": {
            "methods": sorted(allowed),
            "only_unseen": only_unseen,
            "lookback_days": lookback_days,
            "include_writes": bool(include_writes),
            "sample_id": sample,
            "limit": limit,
            "created_ids": family_ids,
            "cleared_prior_probe_logs": log_cleared,
        },
        "planned": len(to_run),
        "probed": len(results),
        "ok": ok_n,
        "failed": fail_n,
        "remaining_candidates": max(0, len(candidates) - len(to_run)),
        "skipped_count": len(skipped),
        "skipped_sample": skipped[:15],
        "created_ids": family_ids,
        "results": results,
        "note": " ".join(notes),
        "next": "summarize_api_doc_vs_logs(lookback_days=7)",
    }
