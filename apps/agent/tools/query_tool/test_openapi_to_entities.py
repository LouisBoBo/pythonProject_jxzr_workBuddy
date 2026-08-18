"""OpenAPI → entities 草稿生成（不绑定某一套 MES 前缀）。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_AGENT = Path(__file__).resolve().parents[2]
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from tools.query_tool.openapi_to_entities import login_paths_from_openapi, openapi_to_entities


class OpenApiToEntitiesTests(unittest.TestCase):
    def test_extracts_v1_list_gets(self) -> None:
        doc = {
            "info": {"title": "Demo MES"},
            "paths": {
                "/api/v1/auth/login": {"post": {"summary": "登录"}},
                "/api/v1/work-orders/": {
                    "get": {
                        "summary": "查询工单列表",
                        "tags": ["工单"],
                        "parameters": [
                            {"in": "query", "name": "status", "description": "状态"},
                            {"in": "query", "name": "limit"},
                        ],
                    },
                    "post": {"summary": "创建工单"},
                },
                "/api/v1/work-orders/{id}": {
                    "get": {"summary": "工单详情"},
                },
                "/api/v1/production-plans": {
                    "get": {"summary": "生产计划", "tags": ["计划"]},
                },
                "/health": {"get": {"summary": "健康"}},
            },
        }
        out = openapi_to_entities(doc)
        ids = {e["id"] for e in out["entities"]}
        self.assertEqual(ids, {"work-orders", "production-plans"})
        wo = next(e for e in out["entities"] if e["id"] == "work-orders")
        self.assertEqual(wo["path"], "/api/v1/work-orders")
        self.assertIn("query", wo["ops"])
        self.assertIn("import", wo["ops"])
        self.assertTrue(any(f["name"] == "status" for f in wo["fields"]))
        self.assertEqual(wo.get("paging"), {"limit": "limit"})
        self.assertEqual(out["meta"].get("login_paths"), ["/api/v1/auth/login"])
        self.assertEqual(out["meta"].get("path_prefix"), "/api/v1")

    def test_plain_api_prefix_without_v1(self) -> None:
        doc = {
            "info": {"title": "ERP"},
            "servers": [{"url": "http://127.0.0.1:8009"}],
            "paths": {
                "/api/auth/login": {"post": {"summary": "登录"}},
                "/api/work-orders": {
                    "get": {
                        "summary": "查询生产工单列表",
                        "parameters": [
                            {"in": "query", "name": "page"},
                            {"in": "query", "name": "page_size"},
                        ],
                    }
                },
            },
        }
        out = openapi_to_entities(doc)
        wo = out["entities"][0]
        self.assertEqual(wo["id"], "work-orders")
        self.assertEqual(wo["path"], "/api/work-orders")
        self.assertEqual(wo.get("paging"), {"page": "page", "page_size": "page_size"})
        self.assertEqual(out["meta"].get("api_base"), "http://127.0.0.1:8009")
        self.assertEqual(out["meta"].get("login_paths"), ["/api/auth/login"])
        self.assertEqual(out["meta"].get("path_prefix"), "/api")
        self.assertEqual(
            out["meta"].get("login_required_fields"),
            ["username", "password"],
        )

    def test_nested_collection_paths(self) -> None:
        doc = {
            "paths": {
                "/api/inspection/plans": {"get": {"summary": "点检计划列表"}},
                "/api/kanban/production": {"get": {"summary": "生产看板"}},
                "/api/inspection/plans/{plan_id}": {"get": {"summary": "详情"}},
            }
        }
        out = openapi_to_entities(doc)
        by_id = {e["id"]: e for e in out["entities"]}
        self.assertEqual(by_id["inspection-plans"]["path"], "/api/inspection/plans")
        self.assertEqual(by_id["kanban-production"]["path"], "/api/kanban/production")

    def test_swagger2_host_and_base_path(self) -> None:
        doc = {
            "swagger": "2.0",
            "host": "10.0.0.8:8080",
            "basePath": "/erp",
            "schemes": ["http"],
            "paths": {
                "/auth/login": {"post": {"summary": "登陆"}},
                "/mo/list": {"get": {"summary": "工单列表"}},
            },
        }
        out = openapi_to_entities(doc)
        self.assertEqual(out["entities"][0]["id"], "mo-list")
        self.assertEqual(out["entities"][0]["path"], "/erp/mo/list")
        self.assertEqual(out["meta"].get("api_base"), "http://10.0.0.8:8080")
        self.assertEqual(out["meta"].get("path_prefix"), "/erp")
        self.assertEqual(login_paths_from_openapi(doc), ["/erp/auth/login"])

    def test_login_body_required_enterprise_code(self) -> None:
        doc = {
            "paths": {
                "/api/auth/login": {
                    "post": {
                        "summary": "登录",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": [
                                            "username",
                                            "password",
                                            "enterprise_code",
                                        ],
                                        "properties": {
                                            "username": {"type": "string"},
                                            "password": {"type": "string"},
                                            "enterprise_code": {"type": "string"},
                                        },
                                    }
                                }
                            }
                        },
                    }
                },
                "/api/items": {"get": {"summary": "列表"}},
            }
        }
        out = openapi_to_entities(doc)
        self.assertEqual(
            out["meta"].get("login_required_fields"),
            ["username", "password", "enterprise_code"],
        )

    def test_empty_paths_raises(self) -> None:
        with self.assertRaises(ValueError):
            openapi_to_entities({"paths": {}})


if __name__ == "__main__":
    unittest.main()
