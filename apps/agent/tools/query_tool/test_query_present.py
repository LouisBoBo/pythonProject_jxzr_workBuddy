"""查数结果展示与轻量汇总。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_AGENT = Path(__file__).resolve().parents[2]
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from tools.query_tool.query_present import (
    compact_cell,
    field_label_map,
    markdown_table,
    pick_display_columns,
    present_query_result,
    resolve_group_by,
    summarize_records,
)

_META = {
    "id": "work-orders",
    "label": "生产工单",
    "fields": [{"name": "status", "label": "状态"}],
    "columns": [
        {"name": "order_no", "label": "工单号"},
        {"name": "status", "label": "状态"},
        {"name": "product_name", "label": "产品"},
    ],
}


class QueryPresentTests(unittest.TestCase):
    def test_field_label_map_prefers_columns(self) -> None:
        labels = field_label_map("work-orders", _META)
        self.assertEqual(labels["order_no"], "工单号")
        self.assertEqual(labels["status"], "状态")

    def test_fallback_label_when_catalog_echoes_english(self) -> None:
        meta = {
            "id": "work-orders",
            "label": "生产工单",
            "fields": [
                {"name": "status", "label": "status"},
                {"name": "order_no", "label": "order_no"},
            ],
        }
        labels = field_label_map("work-orders", meta)
        self.assertEqual(labels["status"], "状态")
        self.assertEqual(labels["order_no"], "工单号")

    def test_pick_display_columns_prefers_business_keys(self) -> None:
        records = [
            {
                "id": 1,
                "order_no": "WO-1",
                "status": "pending",
                "token": "secret",
                "product_name": "板A",
            }
        ]
        cols = pick_display_columns(records, {"order_no": "工单号", "status": "状态"})
        self.assertIn("order_no", cols)
        self.assertIn("status", cols)
        self.assertNotIn("id", cols)
        self.assertNotIn("token", cols)

    def test_pick_display_columns_skips_secret_like_names(self) -> None:
        records = [
            {
                "order_no": "WO-1",
                "user_password": "x",
                "api_key": "k",
                "Refresh_Token": "t",
            }
        ]
        cols = pick_display_columns(records)
        self.assertEqual(cols, ["order_no"])

    def test_present_query_result_chinese_table_and_filters(self) -> None:
        raw = {
            "entity": "work-orders",
            "total": 9,
            "records": [
                {"order_no": "WO-1", "status": "pending", "product_name": "板A"},
                {"order_no": "WO-2", "status": "done", "product_name": "板B"},
            ],
        }
        with patch("tools.query_tool.query_present.get_entity", return_value=_META):
            out = present_query_result(raw, filters={"status": "pending"}, limit=20)
        self.assertEqual(out["label"], "生产工单")
        self.assertEqual(out["total"], 9)
        self.assertEqual(out["returned"], 2)
        self.assertEqual(out["filters_applied"], {"status": "pending"})
        headers = [c["label"] for c in out["columns"]]
        self.assertIn("工单号", headers)
        self.assertIn("状态", headers)
        self.assertIn("工单号", out["markdown_table"])
        self.assertIn("WO-1", out["markdown_table"])
        self.assertIn("API query", out["reply_hint"])

    def test_present_warns_when_only_priority_urgent(self) -> None:
        raw = {
            "entity": "work-orders",
            "total": 1,
            "records": [{"order_no": "WO-1", "priority": "urgent", "status": "in_progress"}],
        }
        with patch("tools.query_tool.query_present.get_entity", return_value=_META):
            out = present_query_result(raw, filters={"priority": "urgent"}, limit=20)
        self.assertIn("followup_hint", out)
        self.assertIn("urgent-backlog", out["followup_hint"])
        self.assertIn("query_metric", out["reply_hint"])

    def test_present_passes_through_error(self) -> None:
        err = {"error": "实体不存在"}
        self.assertEqual(present_query_result(err), err)

    def test_resolve_group_by_platform_specific_status_field(self) -> None:
        keys = ["ticketNo", "billStatus", "qty"]
        self.assertEqual(resolve_group_by("状态", keys, {}), "billStatus")
        self.assertEqual(resolve_group_by(None, keys, {}), "billStatus")
        std = ["order_no", "status", "qty"]
        self.assertEqual(resolve_group_by("状态", std, {"status": "状态"}), "status")
        self.assertIsNone(resolve_group_by("车间", std, {"status": "状态"}))

    def test_pick_display_columns_prefers_catalog_order(self) -> None:
        records = [{"ticketNo": "T-1", "billStatus": "open", "id": 9}]
        cols = pick_display_columns(
            records,
            labels={"ticketNo": "单号", "billStatus": "单据状态"},
            preferred=["ticketNo", "billStatus"],
        )
        self.assertEqual(cols[0], "ticketNo")
        self.assertIn("billStatus", cols)
        self.assertNotIn("id", cols)

    def test_summarize_records_counts(self) -> None:
        records = [
            {"status": "pending"},
            {"status": "pending"},
            {"status": "done"},
            {"status": None},
        ]
        groups = summarize_records(records, "status")
        by_val = {g["value"]: g for g in groups}
        self.assertEqual(by_val["pending"]["count"], 2)
        self.assertEqual(by_val["done"]["count"], 1)
        self.assertEqual(by_val["(空)"]["count"], 1)
        self.assertEqual(sum(g["count"] for g in groups), 4)

    def test_markdown_table_and_compact(self) -> None:
        self.assertEqual(compact_cell(True), "是")
        table = markdown_table([{"工单号": "WO-1", "状态": "pending"}])
        self.assertIn("| 工单号 | 状态 |", table)
        self.assertIn("WO-1", table)

    def test_summarize_platform_data_groups_by_alias(self) -> None:
        from tools.query_tool.platform_query import summarize_platform_data

        class FakeClient:
            def query(self, entity, filters, limit):
                return {
                    "entity": "work-orders",
                    "total": 3,
                    "records": [
                        {"status": "pending"},
                        {"status": "pending"},
                        {"status": "done"},
                    ],
                }

        with (
            patch("tools.query_tool.platform_query.get_client", return_value=FakeClient()),
            patch("tools.query_tool.query_present.get_entity", return_value=_META),
        ):
            out = summarize_platform_data("work-orders", group_by="状态")
        self.assertEqual(out["group_by"], "status")
        self.assertEqual(out["group_by_label"], "状态")
        by_val = {g["value"]: g["count"] for g in out["groups"]}
        self.assertEqual(by_val["pending"], 2)
        self.assertEqual(by_val["done"], 1)


if __name__ == "__main__":
    unittest.main()
