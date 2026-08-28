"""飞书多维表格写数单测（不连外网）。"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from automations.bitable_sync import sanitize_bitable_sync, sync_automation_run_to_bitable
from automations.bitable_writer import extract_bitable_payload, map_rows_to_records
from automations.feishu_bitable import normalize_app_token


SAMPLE_SUMMARY = """**1. 工单概况**
要点：昨日在制 28。

```bitable_json
{"rows":[{"date":"2026-08-27","wip_count":28,"open_count":46,"urgent_open":23,"utilization_avg":83.5,"output_total":7930,"yield_min":97.86,"yield_max":97.88,"note":"急单跟进"}]}
```
"""


class BitableWriterTests(unittest.TestCase):
    def test_extract_fence(self) -> None:
        payload = extract_bitable_payload(SAMPLE_SUMMARY)
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["rows"]), 1)
        self.assertEqual(payload["rows"][0]["wip_count"], 28)

    def test_map_rows(self) -> None:
        records = map_rows_to_records(
            [{"date": "2026-08-27", "wip_count": 28, "note": "x"}],
            {"date": "日期", "wip_count": "在制工单", "note": "需关注摘要"},
        )
        self.assertEqual(len(records), 1)
        fields = records[0]["fields"]
        self.assertIn("日期", fields)
        self.assertEqual(fields["在制工单"], 28)
        self.assertIsInstance(fields["日期"], int)

    def test_map_rows_passthrough_chinese_keys(self) -> None:
        """列表任务：中文键原样成列，不被日报 field_map 吃掉。"""
        records = map_rows_to_records(
            [
                {"工单号": "WO-1", "产品": "主板", "良率": 97.8, "计划量": 100},
                {"工单号": "WO-2", "产品": "插件", "良率": 98.1, "计划量": 50},
            ],
            None,
        )
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["fields"]["工单号"], "WO-1")
        self.assertEqual(records[0]["fields"]["良率"], 97.8)
        self.assertNotIn("在制工单", records[0]["fields"])
        self.assertNotIn("需关注摘要", records[0]["fields"])

    def test_normalize_app_token_from_url(self) -> None:
        url = "https://xxx.feishu.cn/base/bascnABCDEFG?table=tblxxx"
        self.assertEqual(normalize_app_token(url), "bascnABCDEFG")

    def test_normalize_app_token_from_wiki_url(self) -> None:
        url = (
            "https://qcnc74ovqz7e.feishu.cn/wiki/LknbwgsTSiw5mrk9mp7cZlK5ned"
            "?table=tbl1SjAIDTqg0G1k&view=vewH5f1mGG"
        )
        self.assertEqual(normalize_app_token(url), "LknbwgsTSiw5mrk9mp7cZlK5ned")

    def test_normalize_table_id_from_url(self) -> None:
        from automations.feishu_bitable import normalize_table_id

        url = (
            "https://qcnc74ovqz7e.feishu.cn/wiki/LknbwgsTSiw5mrk9mp7cZlK5ned"
            "?table=tbl1SjAIDTqg0G1k&view=vewH5f1mGG"
        )
        self.assertEqual(normalize_table_id(url), "tbl1SjAIDTqg0G1k")

    def test_friendly_forbidden(self) -> None:
        from automations.feishu_bitable import _friendly_bitable_error

        msg = _friendly_bitable_error(91403, "Forbidden")
        self.assertIn("添加文档应用", msg)

    def test_soft_match_field_names(self) -> None:
        from automations.bitable_writer import (
            normalize_field_label,
            remap_records_to_table_fields,
            resolve_column_name,
        )

        self.assertEqual(normalize_field_label("平均稼动率%"), "平均稼动率")
        self.assertEqual(
            resolve_column_name("平均稼动率%", ["日期", "平均稼动率", "良率下限"]),
            "平均稼动率",
        )
        self.assertEqual(
            resolve_column_name("良率下限", ["良率下限％", "日期"]),
            "良率下限％",
        )
        records, matched, missing = remap_records_to_table_fields(
            [{"fields": {"平均稼动率%": 83.5, "不存在列": 1, "日期": 1}}],
            [
                {"field_name": "日期", "type": 5},
                {"field_name": "平均稼动率", "type": 2},
                {"field_name": "未完工", "type": 2},
            ],
        )
        self.assertEqual(len(records), 1)
        self.assertIn("平均稼动率", records[0]["fields"])
        self.assertIn("日期", records[0]["fields"])
        self.assertNotIn("不存在列", records[0]["fields"])
        self.assertTrue(any("平均稼动率" in m for m in matched))
        self.assertIn("不存在列", missing)

    def test_coerce_text_date(self) -> None:
        from automations.bitable_writer import coerce_value_for_field_type

        self.assertEqual(coerce_value_for_field_type(83.5, 2), 83.5)
        ts = coerce_value_for_field_type("2026-08-27", 5)
        self.assertIsInstance(ts, int)
        self.assertEqual(coerce_value_for_field_type(83.5, 1), "83.5")

    def test_extract_truncated_rows(self) -> None:
        """4000 字截断砍断 JSON 时，应回收已完整的行。"""
        from automations.bitable_writer import truncate_summary_keep_bitable

        rows = [{"工单号": f"WO-{i}", "产品": "主板", "料号": "PCB-001"} for i in range(20)]
        body = "业务日：当日\n\n```bitable_json\n" + json.dumps(
            {"rows": rows}, ensure_ascii=False
        )
        # 模拟旧逻辑：整段砍到 4000，且未闭合 fence
        cut = (body + '\n,"料号":"PCB')[:4000]
        payload = extract_bitable_payload(cut)
        self.assertIsNotNone(payload)
        self.assertGreaterEqual(len(payload["rows"]), 1)
        self.assertEqual(payload["rows"][0]["工单号"], "WO-0")

        kept = truncate_summary_keep_bitable(body + "\n```\n", 500)
        self.assertIn("bitable_json", kept)
        self.assertIn("WO-0", kept)

    def test_extract_unclosed_fence(self) -> None:
        text = '前文\n```bitable_json\n{"rows":[{"工单号":"A1","产品":"X"}]}\n'
        payload = extract_bitable_payload(text)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["rows"][0]["工单号"], "A1")

    def test_enrich_skips_non_wo_rows(self) -> None:
        from automations.bitable_writer import enrich_work_order_rows

        with patch("automations.bitable_writer.fetch_work_order_lookup") as mocked:
            out = enrich_work_order_rows(
                [{"工单号": "WO-X"}, {"date": "2026-08-28", "wip_count": 1}]
            )
            mocked.assert_not_called()
            self.assertEqual(out[0]["工单号"], "WO-X")

    def test_enrich_work_order_rows_fills_process_and_end(self) -> None:
        from automations.bitable_writer import enrich_work_order_rows

        rows = [
            {
                "工单号": "WO-AN-061",
                "产品": "主板A100",
                "计划量": 240,
                "完工量": 225,
                "状态": "已完成",
            }
        ]
        fake = {
            "WO-AN-061": {
                "order_no": "WO-AN-061",
                "current_process": "包装",
                "actual_end_time": "2026-08-28T10:00:00",
            }
        }
        with patch(
            "automations.bitable_writer.fetch_work_order_lookup",
            return_value=fake,
        ):
            out = enrich_work_order_rows(rows)
        self.assertEqual(out[0]["工序"], "包装")
        self.assertEqual(out[0]["完工时间"], "2026-08-28 10:00:00")

    def test_order_no_length_capped(self) -> None:
        from automations.bitable_writer import _wo_order_no

        long_no = "WO-" + ("A" * 200)
        self.assertEqual(len(_wo_order_no({"工单号": long_no})), 64)

    def test_clean_control_chars(self) -> None:
        records = map_rows_to_records(
            [{"工单号": "WO-1", "工序": "贴\x00片", "备注": "ok"}],
            None,
        )
        self.assertEqual(records[0]["fields"]["工序"], "贴片")

    def test_map_english_wo_aliases(self) -> None:
        records = map_rows_to_records(
            [
                {
                    "order_no": "WO-1",
                    "current_process": "贴片",
                    "actual_end_time": "2026-08-28T12:00:00",
                    "plan_quantity": 10,
                }
            ],
            None,
        )
        fields = records[0]["fields"]
        self.assertEqual(fields["工单号"], "WO-1")
        self.assertEqual(fields["工序"], "贴片")
        self.assertEqual(fields["完工时间"], "2026-08-28 12:00:00")
        self.assertEqual(fields["计划量"], 10)


class BitableSyncTests(unittest.TestCase):
    def test_sanitize_disabled(self) -> None:
        out = sanitize_bitable_sync({"enabled": False, "app_token": "basc1", "table_id": "tbl1"})
        self.assertIsNotNone(out)
        self.assertFalse(out["enabled"])

    @patch("automations.bitable_sync.batch_create_records")
    @patch("automations.bitable_sync.app_secret", return_value="sec")
    @patch("automations.bitable_sync.app_id", return_value="cli_x")
    @patch("automations.bitable_sync.bitable_enabled", return_value=True)
    def test_sync_success(self, _e, _a, _s, mock_create) -> None:
        mock_create.return_value = {"ok": True, "record_ids": ["rec1"]}
        out = sync_automation_run_to_bitable(
            Path("data"),
            {
                "id": "auto-x",
                "bitable_sync": {
                    "enabled": True,
                    "app_token": "basc1",
                    "table_id": "tbl1",
                    "field_map": {"date": "日期", "wip_count": "在制工单"},
                },
            },
            "run-1",
            SAMPLE_SUMMARY,
        )
        self.assertEqual(out["bitable_status"], "sent")
        self.assertEqual(out["bitable_record_ids"], ["rec1"])
        mock_create.assert_called_once()

    @patch("automations.bitable_sync.bitable_enabled", return_value=False)
    def test_sync_skipped_global_off(self, _e) -> None:
        out = sync_automation_run_to_bitable(
            Path("data"),
            {"bitable_sync": {"enabled": True, "app_token": "basc1", "table_id": "tbl1"}},
            "run-1",
            SAMPLE_SUMMARY,
        )
        self.assertEqual(out["bitable_status"], "skipped")

    def test_sync_skipped_task_off(self) -> None:
        out = sync_automation_run_to_bitable(
            Path("data"),
            {"push_to_wecom": True},
            "run-1",
            SAMPLE_SUMMARY,
        )
        self.assertEqual(out["bitable_status"], "skipped")


if __name__ == "__main__":
    unittest.main()
