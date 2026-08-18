"""从表结构推断能力 / 按关键字匹配场景表，不写死 TBL_MO。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_AGENT = Path(__file__).resolve().parents[2]
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from tools.schema_tool.schema_infer import (
    infer_capabilities_from_index,
    infer_glossary_from_index,
    match_tables_for_stage,
)

_ERP_INDEX = {
    "table_count": 3,
    "domain_count": 2,
    "domains": [
        {"domain_id": "1.1", "domain": "生产管理"},
        {"domain_id": "1.2", "domain": "仓储物流"},
    ],
    "tables": [
        {
            "table": "work_orders",
            "label": "生产工单",
            "domain": "生产管理",
            "field_count": 12,
            "meaning": "工单主表",
        },
        {
            "table": "warehouses",
            "label": "仓库档案",
            "domain": "仓储物流",
            "field_count": 6,
            "meaning": "仓库",
        },
        {
            "table": "stock_balances",
            "label": "库存结存",
            "domain": "仓储物流",
            "field_count": 8,
            "meaning": "即时库存",
        },
    ],
}


class SchemaInferTests(unittest.TestCase):
    def test_capabilities_from_domains(self) -> None:
        caps = infer_capabilities_from_index(_ERP_INDEX)
        names = [c["name"] for c in caps]
        self.assertIn("生产管理", names)
        self.assertIn("仓储物流", names)
        prod = next(c for c in caps if c["name"] == "生产管理")
        self.assertIn("work_orders", prod["representative_tables"])

    def test_glossary_has_generic_and_labels(self) -> None:
        gloss = infer_glossary_from_index(_ERP_INDEX)
        terms = [g["term"] for g in gloss]
        self.assertIn("工单", terms)
        self.assertIn("生产工单", terms)

    def test_keyword_match_without_tbl_prefix(self) -> None:
        known = {t["table"]: t for t in _ERP_INDEX["tables"]}
        hits, unused = match_tables_for_stage(
            known,
            exact_names=["TBL_MO"],
            keywords=["工单", "work_order"],
            limit=8,
        )
        self.assertIn("work_orders", hits)
        self.assertIn("TBL_MO", unused)

    def test_exact_tbl_still_wins(self) -> None:
        known = {
            "TBL_MO": {"table": "TBL_MO", "label": "工单主表"},
            "work_orders": {"table": "work_orders", "label": "生产工单"},
        }
        hits, unused = match_tables_for_stage(
            known,
            exact_names=["TBL_MO"],
            keywords=["工单", "work_order"],
            limit=8,
        )
        self.assertEqual(hits[0], "TBL_MO")
        self.assertEqual(unused, [])


class CapabilityFallbackTests(unittest.TestCase):
    def test_empty_map_infers_from_schema(self) -> None:
        from tools.schema_tool.capability_map import list_platform_capabilities, reload_capability_map

        reload_capability_map()
        with (
            patch(
                "tools.schema_tool.capability_map._load_map_raw",
                return_value={"capabilities": [], "glossary": []},
            ),
            patch(
                "tools.schema_tool.capability_map.build_index",
                return_value=_ERP_INDEX,
            ),
        ):
            out = list_platform_capabilities()
        self.assertEqual(out.get("map_source"), "inferred_from_schema")
        self.assertGreater(out.get("capability_count") or 0, 0)
        names = [c["name"] for c in out.get("capabilities") or []]
        self.assertIn("生产管理", names)


class ScenarioKeywordTests(unittest.TestCase):
    def test_list_marks_bindable_on_erp_style_tables(self) -> None:
        from tools.schema_tool.business_scenarios import list_business_scenarios

        known = {t["table"]: t for t in _ERP_INDEX["tables"]}
        with patch(
            "tools.schema_tool.business_scenarios._index_lookup",
            return_value=known,
        ):
            out = list_business_scenarios()
        mo = next(s for s in out["scenarios"] if s["id"] == "mo-to-warehouse")
        self.assertTrue(mo["bindable"])
        self.assertGreater(mo["tables_found"], 0)

    def test_get_pack_finds_work_orders(self) -> None:
        from tools.schema_tool.business_scenarios import get_scenario_table_pack

        known = {t["table"]: t for t in _ERP_INDEX["tables"]}
        with patch(
            "tools.schema_tool.business_scenarios._index_lookup",
            return_value=known,
        ):
            out = get_scenario_table_pack("工单到入库")
        self.assertNotIn("error", out)
        names = {r["table"] for st in out["stages"] for r in st.get("tables") or []}
        self.assertIn("work_orders", names)
        self.assertIn("warehouses", names)
        self.assertEqual(out.get("missing_in_doc"), [])


class ProfileReadinessTests(unittest.TestCase):
    def test_unconfigured_asks_to_setup(self) -> None:
        from tools.schema_tool.profile_readiness import inspect_mes_profile

        status = {
            "active_profile_id": "",
            "configured": False,
            "schema": {},
            "ui": {},
            "runtime": {},
            "capability_map": {},
        }
        with (
            patch("mes_profile.invalidate_mes_data_caches") as inv,
            patch("mes_profile.profile_status", return_value=status),
            patch(
                "tools.schema_tool.profile_readiness._credential_flags",
                return_value={
                    "mes_api_username": False,
                    "mes_api_password": False,
                    "mes_enterprise_code": False,
                    "query_auth_ready": False,
                },
            ),
            patch(
                "tools.schema_tool.mes_schema_parser.build_index",
                side_effect=FileNotFoundError("未配置"),
            ),
            patch(
                "tools.schema_tool.capability_map.list_platform_capabilities",
                return_value={"map_source": "empty", "capability_count": 0, "summary": {"schema_backed": []}},
            ),
            patch(
                "tools.schema_tool.business_scenarios.list_business_scenarios",
                return_value={"scenarios": []},
            ),
            patch("tools.query_tool.entity_catalog.catalog_summary", return_value=[]),
            patch("tools.query_tool.platform_query.list_query_metrics", return_value={"metrics": []}),
            patch("tools.query_tool.ops_playbook.list_ops_scenes", return_value={"scenes": []}),
        ):
            out = inspect_mes_profile()
        inv.assert_called()
        self.assertFalse(out["ready"])
        self.assertTrue(out["next_steps"])
        self.assertTrue(any(m.get("item") == "平台名称" for m in out["missing"]))

    def test_layers_separated(self) -> None:
        from tools.schema_tool.profile_readiness import inspect_mes_profile

        status = {
            "active_profile_id": "demo-mes",
            "configured": True,
            "schema": {"exists": True},
            "ui": {"schema_uploaded": True, "openapi_imported": True, "entity_count": 2},
            "runtime": {"api_base": "http://127.0.0.1:8000", "path_prefix": "/api"},
            "capability_map": {"exists": False, "size": 0},
        }
        with (
            patch("mes_profile.invalidate_mes_data_caches"),
            patch("mes_profile.profile_status", return_value=status),
            patch(
                "tools.schema_tool.profile_readiness._credential_flags",
                return_value={
                    "mes_api_username": True,
                    "mes_api_password": True,
                    "mes_enterprise_code": False,
                    "query_auth_ready": True,
                },
            ),
            patch(
                "tools.schema_tool.mes_schema_parser.build_index",
                return_value=_ERP_INDEX,
            ),
            patch(
                "tools.schema_tool.capability_map.list_platform_capabilities",
                return_value={
                    "map_source": "inferred_from_schema",
                    "capability_count": 2,
                    "summary": {"schema_backed": [{"id": "a"}]},
                },
            ),
            patch(
                "tools.schema_tool.business_scenarios.list_business_scenarios",
                return_value={
                    "scenarios": [
                        {
                            "id": "mo-to-warehouse",
                            "title": "工单到入库",
                            "tables_found": 2,
                            "bindable": True,
                        }
                    ]
                },
            ),
            patch(
                "tools.query_tool.entity_catalog.catalog_summary",
                return_value=[{"entity": "tickets", "label": "生产工单"}],
            ),
            patch(
                "tools.query_tool.platform_query.list_query_metrics",
                return_value={
                    "metrics": [
                        {"id": "wip", "label": "在制", "bindable": True, "entity": "tickets"}
                    ]
                },
            ),
            patch(
                "tools.query_tool.ops_playbook.list_ops_scenes",
                return_value={
                    "scenes": [{"id": "urgent-backlog", "label": "紧急", "bindable": True}]
                },
            ),
        ):
            out = inspect_mes_profile(user_intent="查生产工单列表")
        self.assertTrue(out["ready_for_survey"])
        self.assertTrue(out["ready_for_query"])
        self.assertTrue(out["can_answer_now"])
        self.assertEqual(out["known"]["api_entities"], ["tickets"])
        self.assertNotIn("work-orders", out["known"]["api_entities"])
        self.assertEqual(out["B_query"]["entities"][0]["entity"], "tickets")

    def test_query_blocked_without_catalog(self) -> None:
        from tools.schema_tool.profile_readiness import inspect_mes_profile

        status = {
            "active_profile_id": "other-mes",
            "configured": True,
            "schema": {"exists": True},
            "ui": {"schema_uploaded": True, "openapi_imported": False, "entity_count": 0},
            "runtime": {},
            "capability_map": {},
        }
        with (
            patch("mes_profile.invalidate_mes_data_caches"),
            patch("mes_profile.profile_status", return_value=status),
            patch(
                "tools.schema_tool.profile_readiness._credential_flags",
                return_value={
                    "mes_api_username": False,
                    "mes_api_password": False,
                    "mes_enterprise_code": False,
                    "query_auth_ready": False,
                },
            ),
            patch(
                "tools.schema_tool.mes_schema_parser.build_index",
                return_value=_ERP_INDEX,
            ),
            patch(
                "tools.schema_tool.capability_map.list_platform_capabilities",
                return_value={
                    "map_source": "inferred_from_schema",
                    "capability_count": 1,
                    "summary": {"schema_backed": [{"id": "a"}]},
                },
            ),
            patch(
                "tools.schema_tool.business_scenarios.list_business_scenarios",
                return_value={"scenarios": []},
            ),
            patch("tools.query_tool.entity_catalog.catalog_summary", return_value=[]),
            patch("tools.query_tool.platform_query.list_query_metrics", return_value={"metrics": []}),
            patch("tools.query_tool.ops_playbook.list_ops_scenes", return_value={"scenes": []}),
        ):
            out = inspect_mes_profile(user_intent="查一下工单")
        self.assertFalse(out["can_answer_now"])
        self.assertTrue(any(m.get("item") == "接口文档" for m in out["missing"]))

    def test_context_block_has_no_secrets(self) -> None:
        from tools.schema_tool.profile_readiness import format_mes_context_block

        status = {
            "active_profile_id": "demo-mes",
            "configured": True,
            "ui": {"schema_uploaded": True, "openapi_imported": True, "entity_count": 3},
        }
        with (
            patch("mes_profile.profile_status", return_value=status),
            patch(
                "tools.schema_tool.profile_readiness._credential_flags",
                return_value={
                    "mes_api_username": True,
                    "mes_api_password": True,
                    "mes_enterprise_code": False,
                    "query_auth_ready": True,
                },
            ),
        ):
            text = format_mes_context_block()
        self.assertIn("demo-mes", text)
        self.assertIn("禁止编造", text)
        self.assertNotIn("enc:", text)
        self.assertNotIn("password", text.lower())

    def test_ops_not_blocked_without_catalog(self) -> None:
        from tools.schema_tool.profile_readiness import inspect_mes_profile

        status = {
            "active_profile_id": "other-mes",
            "configured": True,
            "schema": {"exists": True},
            "ui": {"schema_uploaded": True, "openapi_imported": False, "entity_count": 0},
            "runtime": {},
            "capability_map": {},
        }
        with (
            patch("mes_profile.invalidate_mes_data_caches"),
            patch("mes_profile.profile_status", return_value=status),
            patch(
                "tools.schema_tool.profile_readiness._credential_flags",
                return_value={
                    "mes_api_username": False,
                    "mes_api_password": False,
                    "mes_enterprise_code": False,
                    "query_auth_ready": False,
                },
            ),
            patch(
                "tools.schema_tool.mes_schema_parser.build_index",
                return_value=_ERP_INDEX,
            ),
            patch(
                "tools.schema_tool.capability_map.list_platform_capabilities",
                return_value={
                    "map_source": "inferred_from_schema",
                    "capability_count": 1,
                    "summary": {"schema_backed": [{"id": "a"}]},
                },
            ),
            patch(
                "tools.schema_tool.business_scenarios.list_business_scenarios",
                return_value={"scenarios": []},
            ),
            patch("tools.query_tool.entity_catalog.catalog_summary", return_value=[]),
            patch("tools.query_tool.platform_query.list_query_metrics", return_value={"metrics": []}),
            patch("tools.query_tool.ops_playbook.list_ops_scenes", return_value={"scenes": []}),
        ):
            out = inspect_mes_profile(user_intent="MES 401")
        self.assertTrue(out["can_answer_now"])
        self.assertEqual(out["intent_kind"], "ops")
        self.assertIn("run_ops_scene", out["next_tool"])

    def test_inspect_error_has_no_path(self) -> None:
        from tools.schema_tool.profile_readiness import inspect_mes_profile

        with (
            patch("mes_profile.invalidate_mes_data_caches"),
            patch(
                "mes_profile.profile_status",
                side_effect=FileNotFoundError("/Users/hebo/secret/profile.json"),
            ),
        ):
            out = inspect_mes_profile()
        self.assertIn("error", out)
        self.assertNotIn("/Users", out["error"])
        self.assertNotIn("secret", out["error"])
        self.assertNotIn("profile.json", out["error"])


if __name__ == "__main__":
    unittest.main()
