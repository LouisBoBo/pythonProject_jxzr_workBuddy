"""分析看板编排单测：不依赖真实 MES。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_AGENT = Path(__file__).resolve().parents[2]
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from tools.query_tool.analysis_demo import (
    find_demo_playbook,
    list_analysis_demos,
    load_demo_playbooks,
    run_analysis_demo,
)


class TestDemoPlaybookLoad(unittest.TestCase):
    def test_builtin_pcb_ops_board_loaded(self) -> None:
        pack = load_demo_playbooks()
        self.assertIn("pcb-ops-board", pack)
        spec = pack["pcb-ops-board"]
        self.assertTrue(spec.get("enabled", True))
        self.assertEqual(spec.get("label"), "PCB 运营看板")
        self.assertGreaterEqual(len(spec.get("steps") or []), 2)

    def test_find_open_board_alias(self) -> None:
        self.assertIsNotNone(find_demo_playbook("打开PCB运营看板"))
        self.assertIsNotNone(find_demo_playbook("pcb-ops-board"))
        # 旧演示说法仍兼容
        self.assertIsNotNone(find_demo_playbook("演示·PCB早会"))
        # 普通日报不得误命中
        self.assertIsNone(find_demo_playbook("值班简报"))
        self.assertIsNone(find_demo_playbook("产线日报"))

    def test_list_shape(self) -> None:
        out = list_analysis_demos()
        self.assertGreaterEqual(out.get("count") or 0, 1)
        self.assertTrue(any(d.get("id") == "pcb-ops-board" for d in out.get("demos") or []))


class TestRunAnalysisDemo(unittest.TestCase):
    def test_orchestrates_and_uses_board_title(self) -> None:
        brief = {
            "scene": "ops-daily-brief",
            "markdown_report": "## 简报\n- 在制 3",
        }
        board = {
            "ok": True,
            "template_id": "pcb_ops",
            "label": "PCB / 品质运营看板",
            "presentation": True,
            "skin": "ops_dark",
            "kpis": [
                {"id": "urgent", "label": "急单", "value": "23", "unit": ""},
            ],
            "charts": [
                {
                    "id": "K2",
                    "title": "急单堆积",
                    "chart_type": "pie",
                    "chart_option": {"series": [{"type": "pie", "data": []}]},
                    "drill": {"enabled": True, "rows": []},
                },
                {
                    "id": "K4",
                    "title": "不良 Top",
                    "chart_type": "bar",
                    "chart_option": {"series": [{"type": "bar", "data": []}]},
                },
            ],
            "gaps": [
                {
                    "id": "K1",
                    "title": "工序在制",
                    "status": "gap",
                    "reason": "无实体",
                }
            ],
            "chart_count": 2,
            "gap_count": 1,
            "markdown_report": "## board",
        }
        urgent = {
            "scene": "urgent-backlog",
            "definition": "急单",
            "result": {
                "total": 2,
                "returned": 2,
                "display_rows": [{"工单号": "WO-1", "状态": "进行中"}],
                "markdown_table": "| 工单号 |\n| --- |\n| WO-1 |",
            },
            "summary": {"groups": [{"value": "进行中", "count": 1}]},
        }

        with (
            patch(
                "tools.query_tool.ops_playbook.run_ops_scene",
                side_effect=lambda **kw: (
                    brief if kw.get("scene") == "ops-daily-brief" else urgent
                ),
            ),
            patch(
                "tools.query_tool.analysis_dashboard.render_analysis_dashboard",
                return_value=board,
            ),
        ):
            out = run_analysis_demo("打开PCB运营看板", user_intent="打开PCB运营看板")

        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("playbook_id"), "pcb-ops-board")
        self.assertEqual(out.get("label"), "PCB / 品质运营看板")
        self.assertEqual(len(out.get("charts") or []), 2)
        self.assertTrue(out.get("presentation"))
        self.assertEqual(out.get("skin"), "ops_dark")
        self.assertTrue(out.get("kpis"))
        self.assertNotIn("早会", str(out.get("label") or ""))

    def test_unknown_playbook(self) -> None:
        out = run_analysis_demo("not-a-real-demo")
        self.assertIn("error", out)

    def test_disabled_via_analysis_overlay(self) -> None:
        with patch(
            "tools.query_tool.analysis_demo._demo_overlays_from_analysis",
            return_value={"pcb-ops-board": {"enabled": False}},
        ):
            self.assertIsNone(find_demo_playbook("pcb-ops-board"))
            out = run_analysis_demo("pcb-ops-board")
            self.assertIn("error", out)


if __name__ == "__main__":
    unittest.main()
