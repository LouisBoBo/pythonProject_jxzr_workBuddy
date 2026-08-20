"""写码后自动查数（D→B）单元测试。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "apps") not in sys.path:
    sys.path.insert(0, str(ROOT / "apps"))

from local_dev.post_dev_query import (  # noqa: E402
    format_post_dev_query_summary,
    run_post_dev_query,
    should_run_post_dev_query,
)


class ShouldRunTests(unittest.TestCase):
    def test_data_change_triggers(self) -> None:
        want, reason = should_run_post_dev_query("给工单列表加一列结束时间", [])
        self.assertTrue(want)
        self.assertIn("数据", reason)

    def test_css_layout_skips(self) -> None:
        want, reason = should_run_post_dev_query(
            "【任务档位：css_layout】\n- 改动点：侧栏滚动",
            ["frontend/App.vue"],
        )
        self.assertFalse(want)
        self.assertIn("非数据侧", reason)

    def test_api_file_triggers_even_without_data_phrase(self) -> None:
        want, reason = should_run_post_dev_query(
            "小改路由注释",
            ["backend/app/api/routes/work_orders.py"],
        )
        self.assertTrue(want)
        self.assertIn("API", reason)

    def test_pure_ui_skips(self) -> None:
        want, _ = should_run_post_dev_query(
            "把按钮颜色改成蓝色",
            ["frontend/src/views/Home.vue"],
        )
        self.assertFalse(want)


class RunPostDevQueryTests(unittest.TestCase):
    def test_disabled(self) -> None:
        out = run_post_dev_query(
            requirement="给工单列表加一列",
            synced_files=[],
            enabled=False,
        )
        self.assertTrue(out["skipped"])
        self.assertIn("关闭", out.get("reason") or "")

    def test_non_data_skips_quietly_in_summary(self) -> None:
        out = run_post_dev_query(
            requirement="改一下按钮颜色",
            synced_files=["frontend/Button.vue"],
            enabled=True,
        )
        self.assertTrue(out["skipped"])
        self.assertEqual(format_post_dev_query_summary(out), "")

    @patch("local_dev.post_dev_query.resolve_query_target")
    @patch("local_dev.post_dev_query._ensure_agent_path", return_value=True)
    def test_query_success(self, _path: object, resolve: object) -> None:
        resolve.return_value = {"id": "work-orders", "label": "工单"}
        with patch(
            "tools.query_tool.platform_query.query_platform_data",
            return_value={
                "entity": "work-orders",
                "label": "工单",
                "returned": 2,
                "total": 12,
                "markdown_table": "| 工单号 |\n| --- |\n| WO-1 |",
                "display_rows": [{"工单号": "WO-1"}],
            },
        ):
            out = run_post_dev_query(
                requirement="给工单列表加一列实际结束时间",
                synced_files=["backend/models/work_order.py"],
                enabled=True,
            )
        self.assertFalse(out["skipped"])
        self.assertTrue(out["ok"])
        self.assertEqual(out["entity"], "work-orders")
        self.assertEqual(out["returned"], 2)
        md = format_post_dev_query_summary(out)
        self.assertIn("改后自动查数", md)
        self.assertIn("WO-1", md)
        self.assertNotIn("不影响本次写码结果", md)

    @patch("local_dev.post_dev_query.resolve_query_target")
    @patch("local_dev.post_dev_query._ensure_agent_path", return_value=True)
    def test_query_error_soft(self, _path: object, resolve: object) -> None:
        resolve.return_value = {"id": "work-orders", "label": "工单"}
        with patch(
            "tools.query_tool.platform_query.query_platform_data",
            return_value={"error": "401 Unauthorized"},
        ):
            out = run_post_dev_query(
                requirement="给工单列表加一列",
                synced_files=[],
                enabled=True,
            )
        self.assertFalse(out["skipped"])
        self.assertFalse(out["ok"])
        md = format_post_dev_query_summary(out)
        self.assertIn("不影响本次写码结果", md)
        self.assertIn("401", md)

    @patch("local_dev.post_dev_query.resolve_query_target", return_value=None)
    @patch("local_dev.post_dev_query._ensure_agent_path", return_value=True)
    def test_no_entity_skip(self, _path: object, _resolve: object) -> None:
        out = run_post_dev_query(
            requirement="给某某列表加一列神秘字段",
            synced_files=[],
            enabled=True,
        )
        self.assertTrue(out["skipped"])
        self.assertIn("未能从需求匹配", out.get("reason") or "")
        md = format_post_dev_query_summary(out)
        self.assertIn("已跳过", md)

    def test_exception_in_query_soft(self) -> None:
        with (
            patch("local_dev.post_dev_query._ensure_agent_path", return_value=True),
            patch(
                "local_dev.post_dev_query.resolve_query_target",
                return_value={"id": "work-orders", "label": "工单"},
            ),
            patch(
                "tools.query_tool.platform_query.query_platform_data",
                side_effect=RuntimeError("boom"),
            ),
        ):
            out = run_post_dev_query(
                requirement="给工单列表加一列",
                synced_files=[],
                enabled=True,
            )
        self.assertFalse(out["ok"])
        self.assertIn("boom", out.get("error") or "")


if __name__ == "__main__":
    unittest.main()
