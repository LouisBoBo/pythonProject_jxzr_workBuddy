"""
平台 API 连接器：封装与 PCB 业务平台的交互。

两层设计：
- MockClient：本地模拟，无需真实平台即可测试 Agent 全流程。
- ERPClient：通过 HTTP 连接真实 ERP（自动登录、自动 token 管理）。

可操作实体由当前 MES 资料包 entities.json（entity_catalog）统一配置。
"""
from __future__ import annotations

import contextvars
import json
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request
from urllib.error import URLError, HTTPError

from config import Config
from safe_http import (
    assert_http_url_allowed,
    safe_query_name,
    safe_request_path,
    urlopen_limited,
)
from tools.query_tool.entity_catalog import (
    get_entity,
    get_entity_map,
    list_entity_ids,
    load_catalog_meta,
    resolve_entity_id,
)


_GENERIC_LOGIN_FALLBACKS = (
    "/api/auth/login",
    "/api/v1/auth/login",
    "/login",
    "/api/login",
)
_GENERIC_LIST_KEYS = ("items", "records", "data", "results", "list", "rows")


def _safe_log_call(**kwargs) -> None:
    """写 API 调用日志；任何异常吞掉，保证不影响业务返回。"""
    try:
        from tools.api_log_tool.call_store import append_api_call
        from middleware.request_context import get_thread_id, get_username

        row = dict(kwargs)
        row.setdefault("source", "erp")
        try:
            row.setdefault("thread_id", get_thread_id())
            row.setdefault("username", get_username())
        except Exception:
            pass
        append_api_call(row)
    except Exception:
        pass

# 请求级用户 ERP token（登录后传入，优先于服务账号 Config.ERP_*）
_erp_token_override: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "erp_token_override", default=None
)


def set_request_erp_token(token: str | None):
    """在单次请求上下文中使用用户的 ERP Bearer token。"""
    return _erp_token_override.set(token or None)


def reset_request_erp_token(token) -> None:
    _erp_token_override.reset(token)


def get_request_erp_token() -> str | None:
    return _erp_token_override.get()


# Mock：不再内置工单/排产样例；按当前资料包实体目录建空表，ERP 不通时回落空结果
_MOCK_SEED: dict[str, list[dict]] = {}


def _path_prefix() -> str:
    try:
        from mes_profile import resolve_path_prefix

        return (resolve_path_prefix() or "").rstrip("/")
    except Exception:
        meta = load_catalog_meta()
        raw = str(meta.get("path_prefix") or "").strip()
        if raw and not raw.startswith("/"):
            raw = "/" + raw
        return raw.rstrip("/")


def _login_paths() -> list[str]:
    discovered: list[str] = []
    try:
        from mes_profile import resolve_login_paths

        discovered = list(resolve_login_paths() or [])
    except Exception:
        meta = load_catalog_meta()
        raw = meta.get("login_paths")
        if isinstance(raw, list):
            discovered = [str(p).strip() for p in raw if str(p).strip()]
    out: list[str] = []
    for p in discovered:
        s = safe_request_path(p)
        if s and s not in out:
            out.append(s)
    if out:
        return out
    for p in _GENERIC_LOGIN_FALLBACKS:
        s = safe_request_path(p)
        if s and s not in out:
            out.append(s)
    return out or ["/api/auth/login"]


def _collection_path(resource: str, prefix: str | None = None) -> str:
    """实体 path 已是绝对路径则原样用；相对路径拼资料包前缀，不写死 /api/v1。"""
    r = (resource or "").strip()
    if r.startswith("/"):
        return safe_request_path(r) or "/"
    pref = prefix if prefix is not None else _path_prefix()
    pref_s = safe_request_path(pref) if pref else ""
    seg = r.strip("/")
    joined = f"{pref_s}/{seg}" if pref_s else f"/{seg}"
    return safe_request_path(joined) or "/"


def _list_query_string(
    paging: dict | None,
    filters: dict | None,
    limit: int,
) -> str:
    """分页参数名来自 OpenAPI；文档未声明时同时带常见几种，兼容不同平台。"""
    pairs: list[tuple[str, str]] = []

    def add(name: object, value: object) -> bool:
        n = safe_query_name(str(name or ""))
        if not n:
            return False
        pairs.append((n, str(value)))
        return True

    cap = max(1, min(int(limit or 20), 100))
    paging = paging if isinstance(paging, dict) else {}
    sent_size = False
    if paging.get("limit"):
        sent_size = add(paging["limit"], cap) or sent_size
    if paging.get("page_size"):
        sent_size = add(paging["page_size"], cap) or sent_size
    if paging.get("page"):
        add(paging["page"], 1)
    if paging.get("offset"):
        add(paging["offset"], 0)
    if not sent_size:
        add("limit", cap)
        add("page", 1)
        add("page_size", cap)
    if filters:
        for k, v in filters.items():
            if v is None or v == "":
                continue
            add(k, v)
    return urlencode(pairs)


def _records_from_payload(
    result: dict | list,
    list_keys: list[str] | None = None,
) -> tuple[list, int]:
    if isinstance(result, list):
        return result, len(result)
    if not isinstance(result, dict):
        return [], 0
    keys: list[str] = []
    for k in list(list_keys or []) + list(_GENERIC_LIST_KEYS):
        if k and k not in keys:
            keys.append(k)
    for key in keys:
        val = result.get(key)
        if isinstance(val, list):
            total = result.get("total", result.get("count", len(val)))
            try:
                n = int(total)
            except (TypeError, ValueError):
                n = len(val)
            return val, n
        if isinstance(val, dict):
            for nk in _GENERIC_LIST_KEYS:
                inner = val.get(nk)
                if isinstance(inner, list):
                    total = val.get("total", val.get("count", result.get("total", len(inner))))
                    try:
                        n = int(total)
                    except (TypeError, ValueError):
                        n = len(inner)
                    return inner, n
    return [], 0


def _token_from_login_payload(result: dict | list | None) -> str:
    if not isinstance(result, dict):
        return ""
    for key in ("access_token", "token", "accessToken"):
        val = result.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    data = result.get("data")
    if isinstance(data, dict):
        return _token_from_login_payload(data)
    return ""


def _mes_query_credentials() -> tuple[str, str, str]:
    """MES 业务接口账号。与 WorkBuddy 登录无关。"""
    user = pwd = ent = ""
    try:
        from settings_store import resolve_setting

        user = (resolve_setting("MES_API_USERNAME", "") or "").strip()
        pwd = (resolve_setting("MES_API_PASSWORD", "") or "").strip()
        ent = (resolve_setting("MES_API_ENTERPRISE_CODE", "") or "").strip()
    except Exception:
        pass
    if not user:
        user = (Config.ERP_USERNAME or "").strip()
    if not pwd:
        pwd = (Config.ERP_PASSWORD or "").strip()
    if not ent:
        ent = (Config.ERP_ENTERPRISE_CODE or "").strip()
    return user, pwd, ent


def _mes_auth_missing_message(missing: list[str]) -> str:
    hint = "、".join(missing) if missing else "MES 接口账号、密码"
    return (
        "MES 接口需要单独鉴权（与 WorkBuddy 登录无关）。"
        f"请在「系统配置 → MES 接入」填写{hint}，保存后再查。"
    )


def _normalize_entity(entity: str) -> str | None:
    """接受英文 id 或中文别名，返回标准实体 id。"""
    return resolve_entity_id(entity)


# ═══════════════════════════════════════════════════════════════════════════
# MockClient — 本地模拟
# ═══════════════════════════════════════════════════════════════════════════
class MockClient:
    """本地模拟客户端 —— 无需真实平台后端即可测试 Agent 全流程。"""

    def __init__(self):
        # 以实体目录为准初始化存储；有样例则填入，否则空列表
        self._storage: dict[str, list[dict]] = {
            eid: [dict(r) for r in _MOCK_SEED.get(eid, [])]
            for eid in list_entity_ids()
        }

    def list_entities(self) -> list[str]:
        return list(self._storage.keys())

    def describe_entity(self, entity: str) -> dict:
        eid = _normalize_entity(entity)
        if not eid or eid not in self._storage:
            return {"error": f"实体 '{entity}' 不存在，可用: {list(self._storage.keys())}"}
        data = self._storage[eid]
        sample = next((r for r in data if isinstance(r, dict)), None)
        fields = list(sample.keys()) if sample else []
        sample_out = [r for r in data[:5] if isinstance(r, dict)] or data[:2]
        return {
            "entity": eid,
            "fields": fields,
            "record_count": len(data),
            "sample": sample_out,
        }

    def import_data(self, entity: str, records: list[dict]) -> dict:
        eid = _normalize_entity(entity)
        if not eid:
            return {"error": f"实体 '{entity}' 不存在"}
        if eid not in self._storage:
            self._storage[eid] = []
        for r in records:
            r.setdefault("id", len(self._storage[eid]) + 1)
            self._storage[eid].append(r)
        return {"status": "ok", "imported": len(records), "entity": eid,
                "total": len(self._storage[eid])}

    def export_data(self, entity: str, filters: dict | None = None) -> list[dict]:
        eid = _normalize_entity(entity)
        if not eid or eid not in self._storage:
            return []
        data = self._storage[eid]
        if filters:
            data = [r for r in data if all(r.get(k) == v for k, v in filters.items())]
        return data

    def query(self, entity: str, filters: dict | None = None, limit: int = 100) -> dict:
        eid = _normalize_entity(entity)
        if not eid or eid not in self._storage:
            return {"error": f"实体 '{entity}' 不存在，可用: {list(self._storage.keys())}"}
        data = self._storage[eid]
        if filters:
            data = [r for r in data if all(r.get(k) == v for k, v in filters.items())]
        return {"entity": eid, "total": len(data), "records": data[:limit]}

    def execute_sql(self, sql: str) -> dict:
        return {"status": "mock", "message": f"Mock 模式不支持 SQL。收到: {sql[:80]}..."}


# ═══════════════════════════════════════════════════════════════════════════
# ERPClient — 连接真实 ERP 平台
# ═══════════════════════════════════════════════════════════════════════════
class ERPClient:
    """通过 HTTP API 连接真实 ERP 平台，充当 Agent 工具层与 ERP 之间的适配器。

    Agent 工具层用通用方法调用（list_entities / import_data 等），
    ERPClient 将其翻译为 ERP 的实际 REST 接口。
    实体映射来自 entities.json，不再硬编码。
    """

    def __init__(self):
        api_base = ""
        try:
            from mes_profile import resolve_mes_api_base

            api_base = (resolve_mes_api_base() or "").rstrip("/")
        except Exception:
            api_base = ""
        try:
            self.base = assert_http_url_allowed(api_base, what="MES 接口地址") if api_base else ""
        except ValueError:
            self.base = ""
        self._token: str | None = None
        self.ENTITY_MAP = get_entity_map()
        self._login_paths = _login_paths()

    # ── 内部方法 ──────────────────────────────────────────────────────

    def _ensure_auth(self) -> str | None:
        """向 MES 业务登录接口取 JWT。不用 WorkBuddy 会话 token。缺配置时返回中文说明。"""
        if self._token:
            return None
        if not self.base:
            return "未配置 MES 接口地址。请先在「系统配置 → MES 接入」导入接口文档。"
        user, password, ent = _mes_query_credentials()
        required = ["username", "password"]
        try:
            from mes_profile import resolve_mes_login_required_fields

            required = resolve_mes_login_required_fields() or required
        except Exception:
            pass
        missing: list[str] = []
        req_l = {str(r).lower() for r in required}
        if "username" in req_l and not user:
            missing.append("MES 接口账号")
        if "password" in req_l and not password:
            missing.append("MES 接口密码")
        if any("enterprise" in r for r in req_l) and not ent:
            missing.append("MES 企业编码")
        if missing:
            return _mes_auth_missing_message(missing)

        body: dict = {"username": user, "password": password}
        if ent:
            body["enterprise_code"] = ent
        data = json.dumps(body).encode()
        last_err = None
        for login_path in self._login_paths:
            try:
                req = Request(
                    f"{self.base}{login_path}",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                t0 = time.perf_counter()
                with urlopen_limited(req, timeout=10, max_bytes=1024 * 1024) as resp:
                    result = json.loads(resp.read().decode() or "{}")
                    self._token = _token_from_login_payload(result)
                _safe_log_call(
                    method="POST",
                    path=login_path,
                    status=200,
                    ok=bool(self._token),
                    latency_ms=(time.perf_counter() - t0) * 1000,
                )
                last_err = None
                if self._token:
                    break
            except Exception as e:
                last_err = e
                continue
        if not self._token:
            _safe_log_call(
                method="POST",
                path=(self._login_paths[0] if self._login_paths else "/login"),
                status=None,
                ok=False,
                latency_ms=None,
                error=f"mes_login_failed: {last_err}",
            )
            return (
                "已用 MES 接口账号登录业务系统失败（未返回 token）。"
                "请核对账号、密码、企业编码；这与 WorkBuddy 登录不是同一套。"
            )
        return None

    def _request(self, method: str, path: str, body: dict | None = None, *, _auth_retry: bool = False) -> dict | list:
        """发送 HTTP 请求到 MES，自动附带 MES token（不是 WorkBuddy 登录 token）。"""
        if not self.base:
            return {"error": "未配置 MES 接口地址。请先在「系统配置 → MES 接入」导入接口文档。"}
        missing = self._ensure_auth()
        if missing:
            return {"error": missing}
        url = f"{self.base}{path}"
        data = json.dumps(body).encode() if body else None
        headers = {"Content-Type": "application/json"}
        token = self._token
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = Request(url, data=data, headers=headers, method=method)
        t0 = time.perf_counter()
        try:
            with urlopen_limited(req, timeout=15, max_bytes=8 * 1024 * 1024) as resp:
                text = resp.read().decode()
                latency_ms = (time.perf_counter() - t0) * 1000
                status = getattr(resp, "status", None) or 200
                if not text:
                    _safe_log_call(method=method, path=path, status=status, ok=True, latency_ms=latency_ms)
                    return {}
                parsed = json.loads(text)
                # soft-fail：HTTP 200 但 body 含 error
                soft_err = isinstance(parsed, dict) and parsed.get("error")
                _safe_log_call(
                    method=method,
                    path=path,
                    status=status,
                    ok=not bool(soft_err),
                    latency_ms=latency_ms,
                    error=str(soft_err)[:200] if soft_err else None,
                )
                return parsed
        except HTTPError as e:
            latency_ms = (time.perf_counter() - t0) * 1000
            if e.code == 401 and not _auth_retry:
                self._token = None
                return self._request(method, path, body, _auth_retry=True)
            if e.code in (401, 403):
                err = (
                    f"HTTP {e.code}: MES 接口鉴权失败。"
                    "请核对「系统配置 → MES 接入」中的接口账号/密码/企业编码"
                    "（与 WorkBuddy 登录无关）。"
                )
            else:
                err = f"HTTP {e.code}"
            _safe_log_call(
                method=method, path=path, status=e.code, ok=False, latency_ms=latency_ms, error=err
            )
            return {"error": err}
        except URLError as e:
            latency_ms = (time.perf_counter() - t0) * 1000
            err = "无法连接 MES 接口，请检查接口文档主机是否可达。"
            _safe_log_call(
                method=method,
                path=path,
                status=None,
                ok=False,
                latency_ms=latency_ms,
                error=f"{err} {e.reason}",
            )
            return {"error": err}

    def _resolve_entity(self, entity: str) -> str | None:
        """将实体 id 或别名解析为 REST 资源名。未知实体返回 None。"""
        eid = _normalize_entity(entity)
        if not eid:
            return None
        return self.ENTITY_MAP.get(eid)

    def _extract_fields(self, record: Any) -> list[str]:
        """从一条记录提取字段名列表；非 dict 记录返回空列表。"""
        if not isinstance(record, dict):
            return []
        return sorted(str(k) for k in record.keys())

    # ── 对外方法（Agent 工具层调用）───────────────────────────────────

    def list_entities(self) -> list[str]:
        """列出平台中可用的数据实体。"""
        return list(self.ENTITY_MAP.keys())

    def describe_entity(self, entity: str) -> dict:
        """查看实体的字段结构。通过请求少量真实数据来提取字段名。"""
        eid = _normalize_entity(entity)
        resource = self._resolve_entity(entity)
        if not resource or not eid:
            return {"error": f"实体 '{entity}' 不存在，可用实体: {list(self.ENTITY_MAP.keys())}"}

        # 获取足够数据来提取字段并统计真实记录数
        spec = get_entity(eid) or {}
        coll = _collection_path(resource)
        qs = _list_query_string(spec.get("paging"), None, 100)
        result = self._request("GET", f"{coll}?{qs}")
        if isinstance(result, dict) and "error" in result:
            return result

        records, total = _records_from_payload(result, spec.get("list_keys"))
        # 部分接口 list 项可能是纯字符串/标量，不能对 str 调 .keys()
        dict_records = [r for r in records if isinstance(r, dict)]
        sample_rec = dict_records[0] if dict_records else None
        fields = self._extract_fields(sample_rec) if sample_rec is not None else []
        return {
            "entity": eid,
            "resource": coll,
            "fields": fields,
            "record_count": total,
            "sample": (dict_records[:5] if dict_records else records[:5]),
        }

    def import_data(self, entity: str, records: list[dict]) -> dict:
        """将记录逐条导入平台（ERP 不支持批量导入，逐条 POST）。

        自动移除 id/created_at/updated_at 等由服务端生成的字段。
        """
        eid = _normalize_entity(entity)
        resource = self._resolve_entity(entity)
        if not resource or not eid:
            return {"error": f"实体 '{entity}' 不存在"}

        # 移除服务端自动生成的字段
        server_fields = {"id", "created_at", "updated_at"}
        imported = 0
        errors = []

        for i, record in enumerate(records):
            clean = {k: v for k, v in record.items() if k not in server_fields}
            result = self._request("POST", _collection_path(resource), clean)
            if isinstance(result, dict) and "error" in result:
                errors.append({"index": i, "error": result["error"]})
            else:
                imported += 1

        status = "ok" if imported == len(records) else "partial"
        result = {"status": status, "imported": imported, "total": len(records), "entity": eid}
        if errors:
            result["errors"] = errors
        return result

    def export_data(self, entity: str, filters: dict | None = None) -> list[dict]:
        """从平台导出实体数据（当前硬编码 limit=100）。"""
        resource = self._resolve_entity(entity)
        if not resource:
            return []

        coll = _collection_path(resource)
        spec = get_entity(_normalize_entity(entity) or "") or {}
        qs = _list_query_string(spec.get("paging"), filters, 100)
        result = self._request("GET", f"{coll}?{qs}")
        if isinstance(result, dict) and "error" in result:
            # 保持可被 file_ops 识别；不再静默成 []（调用已记入 api_calls）
            return result
        records, _total = _records_from_payload(result, spec.get("list_keys"))
        return records
    def query(self, entity: str, filters: dict | None = None, limit: int = 100) -> dict:
        """条件查询实体数据。filter key 直接映射为 API query 参数。"""
        eid = _normalize_entity(entity)
        resource = self._resolve_entity(entity)
        if not resource or not eid:
            return {"error": f"实体 '{entity}' 不存在，可用: {list(self.ENTITY_MAP.keys())}"}

        coll = _collection_path(resource)
        spec = get_entity(eid) or {}
        qs = _list_query_string(spec.get("paging"), filters, limit)
        result = self._request("GET", f"{coll}?{qs}")
        if isinstance(result, dict) and "error" in result:
            return result

        records, total = _records_from_payload(result, spec.get("list_keys"))
        return {"entity": eid, "total": total, "records": records}
    def execute_sql(self, sql: str) -> dict:
        return {"error": "ERP 平台不支持 SQL 查询"}


# ═══════════════════════════════════════════════════════════════════════════
# 单例工厂
# ═══════════════════════════════════════════════════════════════════════════
_client_instance: object | None = None


def _should_use_erp_client() -> bool:
    """是否连接真实 MES/ERP。

    - 开发态可在 .env 设 USE_ERP=true 强制开启
    - 桌面安装包无 .env：已导入资料包且解析出 api_base 时自动走真实接口
    """
    if Config.USE_ERP:
        return True
    try:
        from mes_profile import active_profile_id, resolve_mes_api_base

        if active_profile_id() and resolve_mes_api_base():
            return True
    except Exception:
        pass
    return False


def get_client() -> "MockClient | ERPClient":
    """根据配置返回模拟或真实 ERP 客户端（单例）。

    判断逻辑：
    - USE_ERP=true 或已配置 MES 资料包且存在 api_base → ERPClient
    - 否则 → MockClient（本地模拟，零依赖）
    """
    global _client_instance
    if _client_instance is None:
        if _should_use_erp_client():
            _client_instance = ERPClient()
        else:
            _client_instance = MockClient()
    return _client_instance
