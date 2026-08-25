"""指标口径绑定当前资料包，不写死 work-orders。"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_AGENT = Path(__file__).resolve().parents[2]
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from tools.query_tool.metrics_pack import (
    bind_metric,
    build_measure_contract,
    find_metric,
    load_metrics_pack,
)

_TICKETS = [
    {
        "id": "tickets",
        "label": "生产工单",
        "aliases": ["生产工单", "工单"],
        "fields": [{"name": "billStatus", "label": "单据状态"}, {"name": "pri", "label": "优先级"}],
        "columns": [{"name": "ticketNo", "label": "单号"}],
    }
]
_DEVICES = [
    {
        "id": "devices",
        "label": "设备",
        "aliases": ["设备", "机器"],
        "fields": [{"name": "status", "label": "状态"}],
    }
]


def _no_profile_overlay():
    return (
        patch("mes_profile.resolve_metrics_path", return_value=(None, "none")),
        patch(
            "tools.query_tool.analysis_config.load_analysis_config",
            return_value={
                "metric_packs": [],
                "group_by_labels": ["状态"],
                "brief_metric_ids": ["wip"],
                "brief_metric_limit": 4,
                "source": "defaults",
            },
        ),
    )


def _wip() -> dict:
    a, b = _no_profile_overlay()
    with a, b:
        pack = load_metrics_pack()
        m = find_metric("在制", pack)
    assert m is not None
    return m


class MetricsPackTests(unittest.TestCase):
    def test_find_metric_by_alias(self) -> None:
        a, b = _no_profile_overlay()
        with a, b:
            pack = load_metrics_pack()
            self.assertEqual(find_metric("在制", pack)["id"], "wip")
            self.assertEqual(find_metric("紧急未完工", pack)["id"], "urgent-unfinished")
            self.assertEqual(find_metric("紧急工单有哪些", pack)["id"], "urgent-unfinished")
            self.assertEqual(find_metric("当日完工", pack)["id"], "completed-today")

    def test_bind_uses_catalog_entity_not_work_orders(self) -> None:
        bound = bind_metric(
            _wip(),
            catalog=_TICKETS,
            available_fields=["ticketNo", "billStatus", "pri"],
            observed={"billStatus": ["open", "in_progress", "done"]},
        )
        self.assertNotIn("error", bound)
        self.assertEqual(bound["entity"], "tickets")
        self.assertNotEqual(bound["entity"], "work-orders")
        self.assertEqual(bound["filter_sets"], [{"billStatus": "in_progress"}])

    def test_no_bind_when_catalog_has_no_matching_entity(self) -> None:
        bound = bind_metric(_wip(), catalog=_DEVICES, observed={})
        self.assertIn("error", bound)
        self.assertNotIn("work-orders", json.dumps(bound, ensure_ascii=False))

    def test_urgent_cross_product_uses_observed_enums(self) -> None:
        a, b = _no_profile_overlay()
        with a, b:
            m = find_metric("紧急未完工", load_metrics_pack())
        bound = bind_metric(
            m,
            catalog=_TICKETS,
            available_fields=["billStatus", "pri"],
            observed={
                "billStatus": ["pending", "in_progress", "completed"],
                "pri": ["low", "high", "urgent"],
            },
        )
        self.assertNotIn("error", bound)
        sets = bound["filter_sets"]
        self.assertTrue(all("pri" in s and "billStatus" in s for s in sets))
        self.assertTrue(any(s["pri"] == "urgent" and s["billStatus"] == "pending" for s in sets))
        self.assertFalse(any(s.get("billStatus") == "completed" for s in sets))

    def test_completed_today_skips_unfilterable_date(self) -> None:
        a, b = _no_profile_overlay()
        with a, b:
            m = find_metric("当日完工", load_metrics_pack())
        bound = bind_metric(
            m,
            catalog=_TICKETS,
            available_fields=["billStatus", "end_date"],
            observed={"billStatus": ["completed", "pending"]},
            filter_fields=["billStatus"],
            today="2026-08-18",
        )
        self.assertNotIn("error", bound)
        self.assertEqual(bound["filter_sets"], [{"billStatus": "completed"}])
        self.assertTrue(bound["caveats"])

    def test_profile_overlay_replaces_by_id(self) -> None:
        overlay = {
            "metrics": [
                {
                    "id": "wip",
                    "label": "在制任务",
                    "aliases": ["在制"],
                    "entity_hints": ["任务"],
                    "clauses": [
                        {
                            "field_role": "status",
                            "field_hints": ["status"],
                            "include_values": ["doing"],
                        }
                    ],
                }
            ]
        }
        from tools.query_tool import metrics_pack as mp

        real_read = mp._read_json

        def fake_read(path):
            if Path(path) == mp._DEFAULT_PATH:
                return real_read(path)
            return overlay

        with (
            patch.object(mp, "_read_json", side_effect=fake_read),
            patch("mes_profile.resolve_metrics_path", return_value=(Path("/tmp/x/metrics.json"), "profile")),
        ):
            pack = load_metrics_pack()
        wip = find_metric("在制", pack)
        self.assertEqual(wip["label"], "在制任务")
        self.assertEqual(wip["entity_hints"], ["任务"])


class MeasureContractTests(unittest.TestCase):
    def test_scrap_ratio_when_both_fields(self) -> None:
        metric = {
            "id": "scrap-rate",
            "rate_field_hints": ["yield_rate"],
            "numerator_field_hints": ["scrap_count"],
            "denominator_field_hints": ["total_inspected"],
            "caveat_if_incomplete": "只报件数",
        }
        m = build_measure_contract(
            metric, ["process", "scrap_count", "total_inspected"]
        )
        self.assertEqual(m["rate_mode"], "ratio")
        self.assertEqual(m["numerator_field"], "scrap_count")
        self.assertEqual(m["denominator_field"], "total_inspected")

    def test_scrap_count_only_without_denominator(self) -> None:
        metric = {
            "id": "scrap-rate",
            "numerator_field_hints": ["scrap_count"],
            "denominator_field_hints": ["total_inspected"],
            "caveat_if_incomplete": "只报件数，禁止口算",
        }
        m = build_measure_contract(metric, ["scrap_count", "process"])
        self.assertEqual(m["rate_mode"], "count_only")
        self.assertTrue(any("禁止口算" in str(c) for c in m["caveats"]))

    def test_prefer_rate_field(self) -> None:
        metric = {
            "rate_field_hints": ["yield_rate"],
            "numerator_field_hints": ["scrap_count"],
            "denominator_field_hints": ["total_inspected"],
        }
        m = build_measure_contract(metric, ["yield_rate", "scrap_count"])
        self.assertEqual(m["rate_mode"], "rate_field")
        self.assertEqual(m["rate_field"], "yield_rate")

    def test_pcb_pack_has_no_hardcoded_work_orders(self) -> None:
        path = Path(__file__).resolve().parent / "metric_packs" / "pcb.json"
        blob = path.read_text(encoding="utf-8")
        self.assertNotIn("work-orders", blob)
        data = json.loads(blob)
        ids = {m["id"] for m in data["metrics"]}
        self.assertIn("daily-output", ids)
        self.assertIn("aoi-fail-topn", ids)
        self.assertIn("scrap-rate", ids)


class JiangxiOverlayBindTests(unittest.TestCase):
    """M2-2：试点 metrics 覆盖绑定（不依赖本机激活资料包）。"""

    def _catalog(self) -> list[dict]:
        return [
            {
                "id": "work-orders",
                "label": "生产工单列表",
                "aliases": ["生产工单", "工单"],
                "fields": [
                    {"name": "status", "label": "status"},
                    {"name": "priority", "label": "priority"},
                ],
                "columns": [
                    {"name": "status", "label": "状态"},
                    {"name": "end_date", "label": "完工日"},
                    {"name": "actual_quantity", "label": "实际产量"},
                ],
            },
            {
                "id": "device-output",
                "label": "设备产量排行",
                "aliases": ["设备产量排行", "产量排行"],
                "fields": [],
                "columns": [
                    {"name": "name", "label": "Name"},
                    {"name": "today_output", "label": "Today"},
                    {"name": "week_output", "label": "Week"},
                ],
            },
            {
                "id": "quality-defect-distribution",
                "label": "不良分布",
                "aliases": ["不良分布", "Top 不良项"],
                "fields": [{"name": "by", "label": "by"}],
                "columns": [
                    {"name": "name", "label": "Name"},
                    {"name": "value", "label": "Value"},
                ],
            },
            {
                "id": "quality-process-yield",
                "label": "工序良率",
                "aliases": ["工序良率"],
                "fields": [],
                "columns": [
                    {"name": "process", "label": "Process"},
                    {"name": "yield_rate", "label": "Yield"},
                    {"name": "total_inspected", "label": "Inspected"},
                ],
            },
            {
                "id": "reports-wip",
                "label": "在制品报表",
                "aliases": ["在制品报表"],
                "fields": [{"name": "status", "label": "工单状态筛选"}],
                "columns": [
                    {"name": "current_process", "label": "工序"},
                    {"name": "wip_quantity", "label": "在制数"},
                ],
            },
        ]

    def test_overlay_binds_daily_to_device_output(self) -> None:
        path = (
            Path(__file__).resolve().parent
            / "profile_templates"
            / "metrics.jx-zhongruan.example.json"
        )
        overlay = json.loads(path.read_text(encoding="utf-8"))
        with (
            patch("tools.query_tool.analysis_config.load_analysis_config") as ac,
            patch("mes_profile.resolve_metrics_path", return_value=(path, "profile")),
        ):
            ac.return_value = {
                "metric_packs": ["pcb"],
                "group_by_labels": ["状态"],
                "brief_metric_ids": ["wip"],
                "brief_metric_limit": 4,
                "source": "test",
            }
            pack = load_metrics_pack()
        daily = find_metric("日产出", pack)
        self.assertIsNotNone(daily)
        assert daily is not None
        bound = bind_metric(daily, catalog=self._catalog())
        self.assertNotIn("error", bound)
        self.assertEqual(bound.get("entity"), "device-output")
        self.assertTrue(bound.get("prefer_trend_tool"))

    def test_overlay_wip_by_process_reports(self) -> None:
        path = (
            Path(__file__).resolve().parent
            / "profile_templates"
            / "metrics.jx-zhongruan.example.json"
        )
        with (
            patch("tools.query_tool.analysis_config.load_analysis_config") as ac,
            patch("mes_profile.resolve_metrics_path", return_value=(path, "profile")),
        ):
            ac.return_value = {
                "metric_packs": ["pcb"],
                "group_by_labels": ["状态"],
                "brief_metric_ids": ["wip"],
                "brief_metric_limit": 4,
                "source": "test",
            }
            pack = load_metrics_pack()
        m = find_metric("工序在制", pack)
        self.assertIsNotNone(m)
        assert m is not None
        bound = bind_metric(m, catalog=self._catalog())
        self.assertEqual(bound.get("entity"), "reports-wip")
        self.assertEqual(bound.get("measure", {}).get("category_field"), "current_process")

    def test_overlay_scrap_prefers_yield_rate(self) -> None:
        path = (
            Path(__file__).resolve().parent
            / "profile_templates"
            / "metrics.jx-zhongruan.example.json"
        )
        with (
            patch("tools.query_tool.analysis_config.load_analysis_config") as ac,
            patch("mes_profile.resolve_metrics_path", return_value=(path, "profile")),
        ):
            ac.return_value = {
                "metric_packs": ["pcb"],
                "group_by_labels": ["状态"],
                "brief_metric_ids": ["wip"],
                "brief_metric_limit": 4,
                "source": "test",
            }
            pack = load_metrics_pack()
        m = find_metric("报废率", pack)
        assert m is not None
        bound = bind_metric(
            m,
            catalog=self._catalog(),
            available_fields=["process", "yield_rate", "total_inspected"],
        )
        self.assertEqual(bound.get("entity"), "quality-process-yield")
        self.assertEqual(bound.get("measure", {}).get("rate_mode"), "rate_field")

    def test_explicit_gap_lot_trace(self) -> None:
        m = {
            "id": "lot-trace",
            "label": "Lot/拼板追溯",
            "explicit_gap": True,
            "gap_reason": "无 Lot 接口",
            "entity_hints": [],
        }
        bound = bind_metric(m, catalog=self._catalog())
        self.assertEqual(bound.get("status"), "gap")
        self.assertIn("Lot", bound.get("error") or "")
        self.assertIsNone(bound.get("entity"))

    def test_always_caveats_on_wip_by_process(self) -> None:
        m = {
            "id": "wip-by-process",
            "label": "工序在制",
            "entity_hints": ["在制品报表", "reports-wip"],
            "allow_unfiltered": True,
            "always_caveats": ["报表维非过站"],
            "category_field_hints": ["current_process"],
            "value_field_hints": ["wip_quantity"],
            "clauses": [],
        }
        bound = bind_metric(m, catalog=self._catalog())
        self.assertNotIn("error", bound)
        self.assertTrue(any("报表维" in str(c) for c in (bound.get("caveats") or [])))


if __name__ == "__main__":
    unittest.main()
