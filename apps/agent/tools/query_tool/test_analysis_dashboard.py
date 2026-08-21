"""analysis_dashboard 单测：不依赖真实 MES。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_AGENT = Path(__file__).resolve().parents[2]
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from tools.query_tool.analysis_dashboard import (
    load_dashboard_template,
    render_analysis_dashboard,
    series_from_records,
)
from tools.query_tool.metrics_pack import bind_metric


_CATALOG = [
    {
        "id": "quality-top-defects",
        "label": "Top 不良项",
        "aliases": ["Top 不良项", "不良", "top-defects"],
        "columns": [
            {"name": "defect_type", "label": "缺陷"},
            {"name": "quantity", "label": "数量"},
        ],
        "fields": [],
    },
    {
        "id": "tickets",
        "label": "生产工单",
        "aliases": ["生产工单", "工单"],
        "fields": [
            {"name": "billStatus", "label": "单据状态"},
            {"name": "pri", "label": "优先级"},
        ],
        "columns": [{"name": "ticketNo", "label": "单号"}],
    },
]


class TestSeriesFromRecords(unittest.TestCase):
    def test_merge_and_pick_fields(self) -> None:
        cats, vals, note = series_from_records(
            [
                {"defect_type": "开路", "quantity": 3},
                {"defect_type": "短路", "quantity": 5},
                {"defect_type": "开路", "quantity": 2},
            ],
            category_fields=["defect_type", "name"],
            value_fields=["quantity", "value"],
        )
        self.assertEqual(cats[0], "开路")
        self.assertEqual(vals[0], 5.0)
        self.assertEqual(cats[1], "短路")
        self.assertTrue(note)

    def test_today_output_fallback(self) -> None:
        cats, vals, note = series_from_records(
            [
                {"code": "D1", "name": "贴片线1", "today_output": 120, "week_output": 800},
                {"code": "D2", "name": "贴片线2", "today_output": 90, "week_output": 600},
            ],
            category_fields=["name"],
            value_fields=["value", "output"],  # 故意不含 today_output，走回退
        )
        self.assertEqual(cats[0], "贴片线1")
        self.assertEqual(vals[0], 120.0)
        self.assertIn("today_output", note or "")

    def test_prefer_week_when_today_zero(self) -> None:
        cats, vals, note = series_from_records(
            [
                {"name": "测试设备", "today_output": 0, "week_output": 3375},
                {"name": "精密磨床", "today_output": 0, "week_output": 3675},
            ],
            category_fields=["name"],
            value_fields=["today_output", "week_output"],
        )
        self.assertEqual(vals[0], 3675.0)
        self.assertIn("week_output", note or "")
        self.assertIn("今日产量为 0", note or "")


class TestAllowUnfiltered(unittest.TestCase):
    def test_bind_allow_unfiltered(self) -> None:
        bound = bind_metric(
            {
                "id": "aoi-fail-topn",
                "label": "检测不良 Top",
                "entity_hints": ["Top 不良项"],
                "allow_unfiltered": True,
                "clauses": [],
            },
            catalog=_CATALOG,
            observed={},
        )
        self.assertNotIn("error", bound)
        self.assertEqual(bound["entity"], "quality-top-defects")
        self.assertEqual(bound["filter_sets"], [{}])


class TestDashboard(unittest.TestCase):
    def test_load_builtin_template(self) -> None:
        with patch("mes_profile.profile_dir", return_value=None):
            tmpl = load_dashboard_template("pcb_ops")
        self.assertTrue(tmpl.get("cards"))
        self.assertIn("builtin", tmpl.get("_source") or "")
        k1 = next(c for c in tmpl["cards"] if c.get("id") == "K1")
        self.assertEqual(k1.get("kind"), "entity_series")

    def test_dashboard_partial_ok_and_gaps(self) -> None:
        client = MagicMock()

        catalog = _CATALOG + [
            {
                "id": "device-output",
                "label": "设备产量排行",
                "aliases": ["设备产量排行", "device-output"],
                "columns": [
                    {"name": "name", "label": "Name"},
                    {"name": "today_output", "label": "Today"},
                    {"name": "week_output", "label": "Week"},
                ],
            },
            {
                "id": "production-overview-v2",
                "label": "生产概览（联动版）",
                "aliases": ["生产概览（联动版）", "production-overview-v2"],
                "columns": [],
            },
            {
                "id": "reports-wip",
                "label": "在制品报表",
                "aliases": ["在制品报表", "reports-wip"],
                "columns": [
                    {"name": "current_process", "label": "工序"},
                    {"name": "wip_quantity", "label": "在制数"},
                ],
            },
        ]

        def fake_query(entity, filters, limit):
            if entity == "quality-top-defects":
                return {
                    "entity": entity,
                    "total": 2,
                    "records": [
                        {"defect_type": "开路", "quantity": 4},
                        {"defect_type": "短路", "quantity": 1},
                    ],
                }
            if entity == "production-overview-v2":
                return {"entity": entity, "total": 0, "records": []}
            if entity == "device-output":
                return {
                    "entity": entity,
                    "total": 2,
                    "records": [
                        {"name": "贴片A", "today_output": 0, "week_output": 200},
                        {"name": "贴片B", "today_output": 0, "week_output": 100},
                    ],
                }
            if entity == "reports-wip":
                return {
                    "entity": entity,
                    "total": 3,
                    "records": [
                        {"current_process": "AOI检测", "wip_quantity": 100},
                        {"current_process": "AOI检测", "wip_quantity": 50},
                        {"current_process": "焊接", "wip_quantity": 80},
                    ],
                }
            return {"entity": entity, "total": 0, "records": []}

        client.query.side_effect = fake_query

        def fake_query_metric(name, limit=20, extra_filters=None):
            if "urgent" in str(name) or name == "urgent-unfinished":
                return {"error": "当前资料包没有与该口径匹配的可查对象。"}
            return {"error": "unknown"}

        with (
            patch(
                "tools.query_tool.analysis_dashboard.load_catalog",
                return_value=catalog,
            ),
            patch("tools.platform_api.get_client", return_value=client),
            patch(
                "tools.query_tool.platform_query.query_metric",
                side_effect=fake_query_metric,
            ),
        ):
            out = render_analysis_dashboard(
                template_id="pcb_ops",
                user_intent="打开 PCB 运营看板",
                max_cards=6,
            )
        self.assertTrue(out.get("ok"))
        self.assertGreaterEqual(out.get("chart_count") or 0, 3)
        k1 = next(c for c in out["cards"] if c.get("id") == "K1")
        self.assertEqual(k1.get("status"), "ok", k1)
        self.assertEqual(k1.get("entity"), "reports-wip")
        k3 = next(c for c in out["cards"] if c.get("id") == "K3")
        self.assertEqual(k3.get("status"), "ok", k3)
        self.assertEqual(k3.get("entity"), "device-output")
        k4 = next(c for c in out["cards"] if c.get("id") == "K4")
        self.assertEqual(k4.get("status"), "ok")
        self.assertEqual(k4.get("chart_type"), "pie")
        self.assertTrue(any(c.get("id") == "K_LOT" and c.get("status") == "gap" for c in out["cards"]))

    def test_k1_gap_without_wip_entity(self) -> None:
        client = MagicMock()
        client.query.return_value = {"entity": "x", "total": 0, "records": []}
        with (
            patch("mes_profile.profile_dir", return_value=None),
            patch(
                "tools.query_tool.analysis_dashboard.load_catalog",
                return_value=_CATALOG,
            ),
            patch("tools.platform_api.get_client", return_value=client),
            patch(
                "tools.query_tool.platform_query.query_metric",
                return_value={"error": "skip"},
            ),
        ):
            out = render_analysis_dashboard(template_id="pcb_ops", max_cards=6)
        k1_out = next(c for c in out["cards"] if c.get("id") == "K1")
        self.assertEqual(k1_out.get("status"), "gap")
        reason = str(k1_out.get("reason") or "")
        self.assertTrue("在制" in reason or "匹配" in reason or "可查对象" in reason)


if __name__ == "__main__":
    unittest.main()
