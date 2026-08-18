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

from tools.query_tool.metrics_pack import bind_metric, find_metric, load_metrics_pack

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


def _wip() -> dict:
    pack = load_metrics_pack()
    m = find_metric("在制", pack)
    assert m is not None
    return m


class MetricsPackTests(unittest.TestCase):
    def test_find_metric_by_alias(self) -> None:
        self.assertEqual(find_metric("在制")["id"], "wip")
        self.assertEqual(find_metric("紧急未完工")["id"], "urgent-unfinished")
        self.assertEqual(find_metric("紧急工单有哪些")["id"], "urgent-unfinished")
        self.assertEqual(find_metric("当日完工")["id"], "completed-today")

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
        m = find_metric("紧急未完工")
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
        m = find_metric("当日完工")
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


if __name__ == "__main__":
    unittest.main()
