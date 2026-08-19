"""查数工具结果在过程区应优先展示中文表，而非仅英文 key=value。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_API = Path(__file__).resolve().parent
_APPS = _API.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))
if str(_APPS / "agent") not in sys.path:
    sys.path.insert(0, str(_APPS / "agent"))

from agent_wrapper import _result_detail  # noqa: E402


class ResultDetailQueryTests(unittest.TestCase):
    def test_prefers_chinese_display_rows(self) -> None:
        payload = {
            "entity": "work-orders",
            "label": "生产工单",
            "total": 12,
            "returned": 2,
            "filters_applied": {"status": "pending"},
            "columns": [
                {"name": "order_no", "label": "工单号"},
                {"name": "status", "label": "状态"},
            ],
            "display_rows": [
                {"工单号": "WO-1", "状态": "pending"},
                {"工单号": "WO-2", "状态": "pending"},
            ],
            "markdown_table": "| 工单号 | 状态 |\n| --- | --- |\n| WO-1 | pending |",
            "records": [{"order_no": "WO-1", "status": "pending"}],
        }
        summary, preview = _result_detail("query_platform_data", payload)
        self.assertIn("生产工单", summary)
        self.assertIn("status=pending", summary)
        self.assertTrue(any("工单号" in p for p in preview))
        self.assertTrue(any("WO-1" in p for p in preview))
        self.assertFalse(any(p.startswith("order_no=") for p in preview))

    def test_metric_caveats_in_preview(self) -> None:
        payload = {
            "entity": "work-orders",
            "label": "生产工单",
            "metric_label": "当日完工",
            "total": 3,
            "returned": 3,
            "display_rows": [{"工单号": "WO-9", "状态": "completed"}],
            "columns": [{"name": "order_no", "label": "工单号"}, {"name": "status", "label": "状态"}],
            "caveats": ["接口未声明日期筛选参数 `end_date`，未能限定当日，仅按其它条件查询。"],
            "records": [],
        }
        summary, preview = _result_detail("query_metric", payload)
        self.assertIn("当日完工", summary)
        self.assertTrue(any("未能限定当日" in p for p in preview))


if __name__ == "__main__":
    unittest.main()
