"""
平台 API 连接器：封装与 PCB 业务平台的交互。

两层设计：
- MockClient：本地模拟，无需真实平台即可测试 Agent 全流程。
- ERPClient：通过 HTTP 连接真实 ERP（自动登录、自动 token 管理）。

可操作实体由 entities.json（entity_catalog）统一配置。
"""
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from config import Config
from tools.query_tool.entity_catalog import get_entity_map, list_entity_ids, resolve_entity_id


# ═══════════════════════════════════════════════════════════════════════════
# Mock 样例数据（仅本地演示；实体集合以目录为准）
# ═══════════════════════════════════════════════════════════════════════════
_MOCK_SEED: dict[str, list[dict]] = {
    "work-orders": [
        {"id": 1, "order_no": "WO-0701", "product_name": "四层HDI板",
         "production_line": "SMT线", "plan_quantity": 500, "status": "in_progress",
         "priority": "high", "assignee": "张工"},
        {"id": 2, "order_no": "WO-0702", "product_name": "六层通孔板",
         "production_line": "蚀刻线", "plan_quantity": 200, "status": "completed",
         "priority": "normal", "assignee": "李工"},
        {"id": 3, "order_no": "WO-0703", "product_name": "柔性双面板",
         "production_line": "钻孔线", "plan_quantity": 1000, "status": "pending",
         "priority": "normal", "assignee": "王工"},
    ],
    "production-plans": [
        {"id": 1, "plan_no": "PP-0801", "product_name": "四层HDI板",
         "plan_quantity": 500, "production_line": "SMT线", "status": "draft",
         "start_date": "2026-08-01", "end_date": "2026-08-07"},
        {"id": 2, "plan_no": "PP-0802", "product_name": "六层通孔板",
         "plan_quantity": 200, "production_line": "蚀刻线", "status": "confirmed",
         "start_date": "2026-08-03", "end_date": "2026-08-10"},
    ],
}


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
        fields = list(data[0].keys()) if data else []
        return {"entity": eid, "fields": fields, "record_count": len(data), "sample": data[:2]}

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
        self.base = Config.PLATFORM_BASE_URL.rstrip("/")
        self._token: str | None = None
        self.ENTITY_MAP = get_entity_map()

    # ── 内部方法 ──────────────────────────────────────────────────────

    def _ensure_auth(self):
        """确保已登录，拿到 Bearer token。"""
        if self._token is not None:
            return
        if not Config.ERP_USERNAME or not Config.ERP_PASSWORD:
            return  # 无需认证也可以调用（当前平台未强制 auth）

        try:
            body = {
                "username": Config.ERP_USERNAME,
                "password": Config.ERP_PASSWORD,
            }
            if Config.ERP_ENTERPRISE_CODE:
                body["enterprise_code"] = Config.ERP_ENTERPRISE_CODE

            data = json.dumps(body).encode()
            req = Request(f"{self.base}/api/v1/auth/login", data=data,
                          headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                self._token = result.get("access_token", "")
        except Exception:
            pass  # 登录失败不阻塞，继续无 token 调用

    def _request(self, method: str, path: str, body: dict | None = None) -> dict | list:
        """发送 HTTP 请求到 ERP，自动附带 token。"""
        self._ensure_auth()
        url = f"{self.base}{path}"
        data = json.dumps(body).encode() if body else None
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=15) as resp:
                text = resp.read().decode()
                if not text:
                    return {}
                return json.loads(text)
        except HTTPError as e:
            return {"error": f"HTTP {e.code}: {e.reason}"}
        except URLError as e:
            return {"error": f"连接失败: {e.reason}"}

    def _resolve_entity(self, entity: str) -> str | None:
        """将实体 id 或别名解析为 REST 资源名。未知实体返回 None。"""
        eid = _normalize_entity(entity)
        if not eid:
            return None
        return self.ENTITY_MAP.get(eid)

    def _extract_fields(self, record: dict) -> list[str]:
        """从一条记录提取字段名列表。"""
        return sorted(record.keys())

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

        # 获取足够数据来提取字段并统计真实记录数（ERP 最大接受约 100）
        result = self._request("GET", f"/api/v1/{resource}/?limit=100")
        if isinstance(result, dict) and "error" in result:
            return result

        records = result if isinstance(result, list) else result.get("records", [])
        fields = self._extract_fields(records[0]) if records else []
        return {
            "entity": eid,
            "resource": resource,
            "fields": fields,
            "record_count": len(records),
            "sample": records[:5],
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
            result = self._request("POST", f"/api/v1/{resource}/", clean)
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

        params = []
        if filters:
            for k, v in filters.items():
                params.append(f"{k}={v}")
        param_str = "&".join(params)
        path = f"/api/v1/{resource}/?limit=100"
        if param_str:
            path += "&" + param_str

        result = self._request("GET", path)
        if isinstance(result, dict) and "error" in result:
            return []
        return result if isinstance(result, list) else []

    def query(self, entity: str, filters: dict | None = None, limit: int = 100) -> dict:
        """条件查询实体数据。filter key 直接映射为 API query 参数。"""
        eid = _normalize_entity(entity)
        resource = self._resolve_entity(entity)
        if not resource or not eid:
            return {"error": f"实体 '{entity}' 不存在，可用: {list(self.ENTITY_MAP.keys())}"}

        params = [f"limit={limit}"]
        if filters:
            for k, v in filters.items():
                params.append(f"{k}={v}")
        path = f"/api/v1/{resource}/?{'&'.join(params)}"

        result = self._request("GET", path)
        if isinstance(result, dict) and "error" in result:
            return result

        records = result if isinstance(result, list) else []
        return {"entity": eid, "total": len(records), "records": records}

    def execute_sql(self, sql: str) -> dict:
        return {"error": "ERP 平台不支持 SQL 查询"}


# ═══════════════════════════════════════════════════════════════════════════
# 单例工厂
# ═══════════════════════════════════════════════════════════════════════════
_client_instance: object | None = None


def get_client() -> "MockClient | ERPClient":
    """根据配置返回模拟或真实 ERP 客户端（单例）。

    判断逻辑：
    - USE_ERP=true → ERPClient（连接真实 ERP）
    - 否则 → MockClient（本地模拟模式，零依赖）
    """
    global _client_instance
    if _client_instance is None:
        if Config.USE_ERP:
            _client_instance = ERPClient()
        else:
            _client_instance = MockClient()
    return _client_instance
