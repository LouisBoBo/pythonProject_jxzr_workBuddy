"""表结构 vs 可查对象对照（不写死某一套 MES）。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_AGENT = Path(__file__).resolve().parents[2]
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from tools.schema_tool.schema_diff import _score_pair, compare_schema_vs_catalog


class SchemaDiffTests(unittest.TestCase):
    def test_score_matches_label_not_unrelated(self) -> None:
        self.assertGreater(
            _score_pair(["工单主表", "TBL_MO"], ["生产工单", "work-orders", "工单"]),
            _score_pair(["工单主表", "TBL_MO"], ["设备点检", "inspection-plans"]),
        )

    def test_compare_heuristic_pairs_without_live(self) -> None:
        tables = {
            "tables": [
                {"table": "work_orders", "label": "生产工单", "domain": "生产", "meaning": "工单主表"},
                {"table": "devices", "label": "设备台账", "domain": "设备", "meaning": "设备"},
            ]
        }
        catalog = [
            {"id": "tickets", "label": "生产工单", "aliases": ["工单"], "path": "/api/tickets"},
            {"id": "machines", "label": "设备", "aliases": ["设备台账"], "path": "/api/machines"},
        ]
        with (
            patch("tools.schema_tool.schema_diff.build_index", return_value=tables),
            patch("tools.schema_tool.schema_diff.load_catalog", return_value=catalog),
            patch("tools.schema_tool.schema_diff._load_overlay_pairs", return_value=[]),
        ):
            out = compare_schema_vs_catalog(sample_live=False)
        self.assertNotIn("error", out)
        self.assertEqual(out["catalog_entity_count"], 2)
        ids = {m["entity"] for m in out["matched"]}
        self.assertIn("tickets", ids)
        self.assertFalse(out["live_samples"])
        self.assertIn("启发式", out["note"])
        self.assertIn("表结构 ↔ 接口目录对照", out.get("markdown_summary") or "")
        self.assertIn("匹配", out.get("markdown_summary") or "")

    def test_overlay_wins(self) -> None:
        tables = {"tables": [{"table": "FOO", "label": "奇怪表", "meaning": "x"}]}
        catalog = [{"id": "bar", "label": "另一个", "aliases": [], "path": "/bar"}]
        with (
            patch("tools.schema_tool.schema_diff.build_index", return_value=tables),
            patch("tools.schema_tool.schema_diff.load_catalog", return_value=catalog),
            patch(
                "tools.schema_tool.schema_diff._load_overlay_pairs",
                return_value=[{"table": "FOO", "entity": "bar"}],
            ),
        ):
            out = compare_schema_vs_catalog()
        self.assertEqual(out["matched"][0]["entity"], "bar")
        self.assertEqual(out["matched"][0]["score"], 1000)


if __name__ == "__main__":
    unittest.main()
