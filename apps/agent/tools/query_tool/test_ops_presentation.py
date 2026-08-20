"""运营大屏 KPI / 下钻辅助单测。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_AGENT = Path(__file__).resolve().parents[2]
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from tools.query_tool.ops_presentation import (
    build_drill_payload,
    build_kpis_from_charts,
    series_from_chart_option,
)


class TestOpsPresentation(unittest.TestCase):
    def test_series_from_pie(self) -> None:
        cats, vals = series_from_chart_option(
            {
                "series": [
                    {
                        "type": "pie",
                        "data": [
                            {"name": "待开工", "value": 10},
                            {"name": "进行中", "value": 13},
                        ],
                    }
                ]
            }
        )
        self.assertEqual(cats, ["待开工", "进行中"])
        self.assertEqual(vals, [10.0, 13.0])

    def test_kpis_from_charts_no_invent(self) -> None:
        charts = [
            {
                "id": "K2",
                "title": "急单",
                "chart_option": {
                    "series": [
                        {
                            "type": "pie",
                            "data": [
                                {"name": "进行中", "value": 13},
                                {"name": "待开工", "value": 10},
                            ],
                        }
                    ]
                },
            },
            {
                "id": "K5",
                "title": "良率",
                "chart_option": {
                    "xAxis": {"type": "category", "data": ["A", "B"]},
                    "series": [{"type": "line", "data": [97.9, 97.8]}],
                },
            },
        ]
        kpis = build_kpis_from_charts(
            charts,
            specs=[
                {"id": "urgent", "label": "急单", "chart_id": "K2", "agg": "sum"},
                {
                    "id": "yield_avg",
                    "label": "均良率",
                    "chart_id": "K5",
                    "agg": "avg",
                    "unit": "%",
                },
                {"id": "missing", "label": "无", "chart_id": "K9", "agg": "sum"},
            ],
        )
        ids = {k["id"] for k in kpis}
        self.assertIn("urgent", ids)
        self.assertIn("yield_avg", ids)
        self.assertNotIn("missing", ids)
        urgent = next(k for k in kpis if k["id"] == "urgent")
        self.assertEqual(urgent["value"], "23")

    def test_drill_payload(self) -> None:
        d = build_drill_payload(
            card_id="K2",
            title="急单",
            group_field="status",
            categories=["待开工"],
            values=[10],
            records=[{"status": "pending", "order_no": "WO-1"}],
        )
        self.assertTrue(d["enabled"])
        self.assertTrue(d["rows"])


if __name__ == "__main__":
    unittest.main()
