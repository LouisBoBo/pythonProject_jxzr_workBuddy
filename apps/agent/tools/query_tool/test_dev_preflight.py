"""改功能前置清单：只读当前目录，不写死 work-orders。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_AGENT = Path(__file__).resolve().parents[2]
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from tools.query_tool.dev_preflight import mes_change_preflight


class DevPreflightTests(unittest.TestCase):
    def test_lists_current_catalog(self) -> None:
        catalog = [
            {
                "entity": "tickets",
                "label": "生产工单",
                "aliases": ["工单"],
            }
        ]
        with (
            patch("tools.query_tool.dev_preflight.catalog_summary", return_value=catalog),
            patch("tools.query_tool.dev_preflight.resolve_entity_id", return_value="tickets"),
            patch(
                "tools.query_tool.dev_preflight.list_query_metrics",
                return_value={"metrics": [{"id": "wip", "label": "在制", "bindable": True}]},
            ),
            patch(
                "tools.query_tool.dev_preflight.list_ops_scenes",
                return_value={"scenes": [{"id": "urgent-backlog", "label": "紧急"}]},
            ),
            patch(
                "tools.schema_tool.mes_schema_parser.build_index",
                return_value={"tables": [1], "table_count": 1, "domain_count": 1},
            ),
        ):
            out = mes_change_preflight("改工单列表页")
        self.assertEqual(out["catalog_count"], 1)
        self.assertEqual(out["entities"][0]["entity"], "tickets")
        self.assertTrue(out["intent_hits"])
        self.assertTrue(out["acceptance_hints"])
        blob = " ".join(out["acceptance_hints"])
        self.assertNotIn("work-orders", blob)
        self.assertIn("tickets", blob)
        self.assertTrue(out.get("stack_chain"))
        self.assertTrue(any("库表" in x for x in out["stack_chain"]))


if __name__ == "__main__":
    unittest.main()
