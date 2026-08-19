"""Token 优化：工具返回与系统提示词瘦身（功能不变）。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_AGENT = Path(__file__).resolve().parents[2]
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from tools.query_tool.entity_catalog import build_system_prompt, catalog_summary
from tools.query_tool.platform_query import get_platform_summary, list_platform_entities
from tools.query_tool.query_present import present_query_result


_META = {
    "id": "work-orders",
    "label": "生产工单",
    "fields": [{"name": "status", "label": "状态"}],
    "columns": [
        {"name": "order_no", "label": "工单号"},
        {"name": "status", "label": "状态"},
    ],
}


class TokenOptimizationTests(unittest.TestCase):
    def test_list_platform_entities_skips_live_describe(self) -> None:
        catalog = [
            {
                "id": "work-orders",
                "label": "生产工单",
                "aliases": ["工单"],
                "ops": ["query"],
                "fields": [{"name": "status", "label": "状态"}],
                "columns": [{"name": "order_no", "label": "工单号"}],
            },
            {
                "id": "devices",
                "label": "设备",
                "aliases": [],
                "ops": ["query"],
                "fields": [],
                "columns": [],
            },
        ]
        mock_client = MagicMock()
        mock_client.describe_entity = MagicMock(side_effect=AssertionError("should not call"))

        with (
            patch("tools.query_tool.platform_query.catalog_summary", return_value=catalog_summary_from(catalog)),
            patch("tools.query_tool.platform_query.get_client", return_value=mock_client),
        ):
            out = list_platform_entities()

        mock_client.describe_entity.assert_not_called()
        self.assertEqual(out["count"], 2)
        self.assertEqual(out["details"][0]["entity"], "work-orders")
        self.assertEqual(out["details"][0]["filter_fields"], ["status"])
        self.assertIn("describe_entity", out["hint"])

    def test_get_platform_summary_default_no_live_counts(self) -> None:
        catalog = [
            {
                "id": "work-orders",
                "label": "生产工单",
                "aliases": ["工单"],
                "ops": ["query"],
                "fields": [],
                "columns": [],
            },
        ]
        mock_client = MagicMock()
        mock_client.describe_entity = MagicMock(side_effect=AssertionError("should not call"))

        with (
            patch("tools.query_tool.platform_query.catalog_summary", return_value=catalog_summary_from(catalog)),
            patch("tools.query_tool.platform_query.get_client", return_value=mock_client),
        ):
            out = get_platform_summary()

        mock_client.describe_entity.assert_not_called()
        self.assertEqual(out["entity_count"], 1)
        self.assertNotIn("total_records", out)
        self.assertNotIn("record_count", out["breakdown"]["work-orders"])

    def test_present_query_result_omits_raw_records_when_table_present(self) -> None:
        raw = {
            "entity": "work-orders",
            "total": 2,
            "records": [
                {"order_no": "WO-1", "status": "pending"},
                {"order_no": "WO-2", "status": "done"},
            ],
        }
        with patch("tools.query_tool.query_present.get_entity", return_value=_META):
            out = present_query_result(raw, limit=20)
        self.assertIn("markdown_table", out)
        self.assertIn("display_rows", out)
        self.assertNotIn("records", out)

    def test_compact_system_prompt_shorter_than_verbose(self) -> None:
        catalog = [
            {
                "id": f"entity-{i}",
                "label": f"实体{i}",
                "aliases": [f"别名{i}a", f"别名{i}b"],
                "ops": ["query", "import"],
                "fields": [{"name": f"f{j}", "label": f"字段{j}"} for j in range(8)],
                "columns": [{"name": f"c{j}", "label": f"列{j}"} for j in range(6)],
            }
            for i in range(29)
        ]

        with (
            patch("tools.query_tool.entity_catalog.load_catalog", return_value=catalog),
            patch("config.Config.SYSTEM_PROMPT_COMPACT_CATALOG", True),
        ):
            compact = build_system_prompt()
        with (
            patch("tools.query_tool.entity_catalog.load_catalog", return_value=catalog),
            patch("config.Config.SYSTEM_PROMPT_COMPACT_CATALOG", False),
        ):
            verbose = build_system_prompt()
        self.assertLess(len(compact), len(verbose))
        self.assertIn("entity-0", compact)
        self.assertIn("describe_entity", compact)


def catalog_summary_from(catalog: list[dict]) -> list[dict]:
    rows = []
    for e in catalog:
        fields = e.get("fields") or []
        columns = e.get("columns") or []
        rows.append(
            {
                "entity": e["id"],
                "label": e.get("label", e["id"]),
                "aliases": e.get("aliases") or [],
                "ops": e.get("ops") or ["query"],
                "fields": [f["name"] if isinstance(f, dict) else f for f in fields],
                "columns": [f["name"] if isinstance(f, dict) else f for f in columns],
                "field_labels": {},
            }
        )
    return rows


if __name__ == "__main__":
    unittest.main()
