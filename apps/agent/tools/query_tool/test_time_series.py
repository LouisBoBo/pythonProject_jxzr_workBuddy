"""M1-4 时间序列分桶单测。"""
from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from tools.query_tool.time_series import (
    build_time_series,
    resolve_time_field,
    _parse_to_date,
)


class TestParseDate(unittest.TestCase):
    def test_iso_and_datetime(self) -> None:
        self.assertEqual(_parse_to_date("2026-08-15"), date(2026, 8, 15))
        self.assertEqual(_parse_to_date("2026-08-15T12:30:00"), date(2026, 8, 15))
        self.assertEqual(_parse_to_date("2026/08/15"), date(2026, 8, 15))

    def test_bad(self) -> None:
        self.assertIsNone(_parse_to_date(None))
        self.assertIsNone(_parse_to_date("not-a-date"))


class TestResolveTimeField(unittest.TestCase):
    def test_hints_and_heuristic(self) -> None:
        fields = ["order_no", "Status", "end_date", "actual_qty"]
        self.assertEqual(
            resolve_time_field(fields, hints=["end_date", "finished_at"]),
            "end_date",
        )
        self.assertEqual(
            resolve_time_field(["billStatus", "FinishTime"], hints=["FinishTime"]),
            "FinishTime",
        )

    def test_missing(self) -> None:
        self.assertIsNone(resolve_time_field(["status", "priority"], hints=["end_date"]))

    def test_requested_no_substring_match(self) -> None:
        fields = ["created_at", "end_date", "status"]
        self.assertEqual(resolve_time_field(fields, requested="end_date"), "end_date")
        self.assertIsNone(resolve_time_field(fields, requested="at"))
        self.assertIsNone(resolve_time_field(fields, requested="date"))


class TestBuildTimeSeries(unittest.TestCase):
    def test_day_count_with_zeros(self) -> None:
        today = date(2026, 8, 21)
        records = [
            {"end_date": "2026-08-21", "qty": 10},
            {"end_date": "2026-08-21", "qty": 5},
            {"end_date": "2026-08-19", "qty": 1},
            {"end_date": "2026-07-01", "qty": 99},
        ]
        out = build_time_series(
            records,
            grain="day",
            window=5,
            today=today,
            time_field_hints=["end_date"],
        )
        self.assertTrue(out.get("ok"))
        self.assertEqual(out["categories"][-1], "2026-08-21")
        self.assertEqual(len(out["categories"]), 5)
        by = dict(zip(out["categories"], out["values"]))
        self.assertEqual(by["2026-08-21"], 2)
        self.assertEqual(by["2026-08-19"], 1)
        self.assertEqual(by["2026-08-20"], 0)
        self.assertTrue(any("本页" in str(c) for c in out["caveats"]))

    def test_sum_value_field(self) -> None:
        today = date(2026, 8, 21)
        out = build_time_series(
            [
                {"end_date": "2026-08-21", "actual_qty": 10},
                {"end_date": "2026-08-21", "actual_qty": 5},
            ],
            value_field="actual_qty",
            window=3,
            today=today,
            time_field_hints=["end_date"],
        )
        self.assertEqual(out["mode"], "sum")
        by = dict(zip(out["categories"], out["values"]))
        self.assertEqual(by["2026-08-21"], 15)

    def test_no_time_field_errors_honestly(self) -> None:
        out = build_time_series(
            [{"status": "done"}, {"status": "pending"}],
            window=7,
            today=date(2026, 8, 21),
        )
        self.assertIn("error", out)
        self.assertTrue(any("假趋势" in str(c) for c in out.get("caveats") or []))

    def test_week_grain(self) -> None:
        today = date(2026, 8, 21)
        iso = today.isocalendar()
        label = f"{iso.year}-W{iso.week:02d}"
        out = build_time_series(
            [{"end_date": "2026-08-21"}, {"end_date": "2026-08-17"}],
            grain="week",
            window=2,
            today=today,
            time_field_hints=["end_date"],
        )
        self.assertEqual(out["grain"], "week")
        self.assertIn(label, out["categories"])
        by = dict(zip(out["categories"], out["values"]))
        self.assertEqual(by[label], 2)


class TestAnalyzeTimeTrendTool(unittest.TestCase):
    def test_wires_query_and_chart(self) -> None:
        from tools.query_tool.platform_query import analyze_time_trend

        class FakeClient:
            def query(self, entity, filters, limit):
                return {
                    "entity": "work-orders",
                    "total": 3,
                    "records": [
                        {"order_no": "1", "end_date": "2026-08-21", "actual_qty": 10},
                        {"order_no": "2", "end_date": "2026-08-20", "actual_qty": 4},
                        {"order_no": "3", "end_date": "2026-08-19", "actual_qty": 1},
                    ],
                }

        with (
            patch("tools.query_tool.platform_query.get_client", return_value=FakeClient()),
            patch(
                "tools.query_tool.platform_query.present_query_result",
                return_value={
                    "entity": "work-orders",
                    "label": "生产工单",
                    "total": 3,
                    "returned": 3,
                    "filters_applied": {},
                },
            ),
            patch(
                "tools.query_tool.analysis_config.load_analysis_config",
                return_value={"time_field_hints": ["end_date"]},
            ),
        ):
            out = analyze_time_trend(
                "work-orders",
                window=5,
                value_field="actual_qty",
                include_chart=True,
                user_intent="最近5天产量趋势",
                as_of="2026-08-21",
            )
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("mode"), "sum")
        self.assertEqual(len(out.get("categories") or []), 5)
        self.assertTrue(out.get("markdown_fence") or out.get("chart"))
        self.assertTrue(any("本页" in str(c) for c in out.get("caveats") or []))

    def test_no_date_does_not_break(self) -> None:
        from tools.query_tool.platform_query import analyze_time_trend

        class FakeClient:
            def query(self, entity, filters, limit):
                return {
                    "entity": "work-orders",
                    "total": 2,
                    "records": [{"Status": "done"}, {"Status": "pending"}],
                }

        with (
            patch("tools.query_tool.platform_query.get_client", return_value=FakeClient()),
            patch(
                "tools.query_tool.platform_query.present_query_result",
                return_value={
                    "entity": "work-orders",
                    "label": "生产工单",
                    "total": 2,
                    "returned": 2,
                    "filters_applied": {},
                },
            ),
            patch(
                "tools.query_tool.analysis_config.load_analysis_config",
                return_value={"time_field_hints": ["end_date"]},
            ),
        ):
            out = analyze_time_trend("work-orders", include_chart=True)
        self.assertIn("error", out)
        self.assertFalse(out.get("markdown_fence"))


if __name__ == "__main__":
    unittest.main()
