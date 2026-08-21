"""M1 聚合：页内 caveat + 可选服务端聚合解析（无 LLM、无真实 MES）。"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from tools.query_tool.aggregate import (
    CAVEAT_PAGE_SCOPE,
    aggregate_by_field,
    entity_aggregate_spec,
    page_scope_caveats,
    parse_aggregate_payload,
)


class TestPageCaveats(unittest.TestCase):
    def test_always_has_page_scope(self) -> None:
        c = page_scope_caveats(total=10, returned=10)
        self.assertTrue(any(CAVEAT_PAGE_SCOPE[:8] in x for x in c))

    def test_truncated_when_total_gt_returned(self) -> None:
        c = page_scope_caveats(total=100, returned=20)
        self.assertTrue(any("total=100" in x for x in c))


class TestParseAggregate(unittest.TestCase):
    def test_groups_list(self) -> None:
        groups = parse_aggregate_payload(
            {"groups": [{"value": "a", "count": 2}, {"name": "b", "total": 1}]},
            group_field="status",
        )
        self.assertIsNotNone(groups)
        assert groups is not None
        by = {g["value"]: g["count"] for g in groups}
        self.assertEqual(by["a"], 2)
        self.assertEqual(by["b"], 1)

    def test_flat_map(self) -> None:
        groups = parse_aggregate_payload(
            {"pending": 3, "done": 1, "total": 4},
            group_field="status",
        )
        self.assertIsNotNone(groups)
        assert groups is not None
        self.assertEqual(sum(g["count"] for g in groups), 4)

    def test_error_payload(self) -> None:
        self.assertIsNone(parse_aggregate_payload({"error": "nope"}, group_field="status"))


class TestEntitySpec(unittest.TestCase):
    def test_aggregate_block(self) -> None:
        spec = entity_aggregate_spec(
            {"aggregate": {"path": "/api/wo/stats", "group_param": "by"}}
        )
        self.assertEqual(spec["path"], "/api/wo/stats")
        self.assertEqual(spec["group_param"], "by")

    def test_paths_aggregate(self) -> None:
        spec = entity_aggregate_spec(
            {"paths": {"aggregate": "/stats"}, "aggregate_param": "g"}
        )
        self.assertEqual(spec["path"], "/stats")
        self.assertEqual(spec["group_param"], "g")

    def test_missing(self) -> None:
        self.assertIsNone(entity_aggregate_spec({"id": "x"}))


class TestAggregateByField(unittest.TestCase):
    def test_page_mode_default(self) -> None:
        client = MagicMock()
        presented = {
            "entity": "work-orders",
            "label": "生产工单",
            "total": 50,
            "returned": 3,
            "filters_applied": {},
        }
        records = [
            {"status": "pending"},
            {"status": "pending"},
            {"status": "done"},
        ]
        with patch(
            "tools.query_tool.aggregate.field_label_map",
            return_value={"status": "状态"},
        ):
            out = aggregate_by_field(
                entity="work-orders",
                group_by="状态",
                filters=None,
                limit=100,
                client=client,
                entity_meta={"id": "work-orders"},
                records=records,
                presented=presented,
            )
        self.assertEqual(out.get("mode"), "page")
        self.assertIn("caveats", out)
        self.assertTrue(any("本页" in str(c) for c in out["caveats"]))
        self.assertEqual(out["group_by"], "status")
        client._request.assert_not_called()

    def test_server_mode_when_declared(self) -> None:
        client = MagicMock()
        client._request.return_value = {
            "groups": [{"value": "urgent", "count": 5}, {"value": "high", "count": 2}],
            "total": 7,
        }
        presented = {
            "entity": "work-orders",
            "label": "生产工单",
            "total": 3,
            "returned": 3,
            "filters_applied": {},
        }
        meta = {
            "id": "work-orders",
            "aggregate": {"path": "/api/wo/stats", "group_param": "groupBy"},
            "fields": [{"name": "priority", "label": "优先级"}],
            "columns": [{"name": "priority", "label": "优先级"}],
        }
        with patch(
            "tools.query_tool.aggregate.field_label_map",
            return_value={"priority": "优先级"},
        ):
            out = aggregate_by_field(
                entity="work-orders",
                group_by="优先级",
                filters=None,
                limit=100,
                client=client,
                entity_meta=meta,
                records=[{"priority": "urgent"}],
                presented=presented,
            )
        self.assertEqual(out.get("mode"), "server")
        self.assertEqual(sum(g["count"] for g in out["groups"]), 7)
        client._request.assert_called()

    def test_server_fail_falls_back_page(self) -> None:
        client = MagicMock()
        client._request.return_value = {"error": "HTTP 500"}
        presented = {
            "entity": "work-orders",
            "label": "生产工单",
            "total": 2,
            "returned": 2,
            "filters_applied": {},
        }
        meta = {
            "aggregate": {"path": "/api/wo/stats"},
            "columns": [{"name": "status", "label": "状态"}],
        }
        with patch(
            "tools.query_tool.aggregate.field_label_map",
            return_value={"status": "状态"},
        ):
            out = aggregate_by_field(
                entity="work-orders",
                group_by="状态",
                filters=None,
                limit=100,
                client=client,
                entity_meta=meta,
                records=[{"status": "a"}, {"status": "b"}],
                presented=presented,
            )
        self.assertEqual(out.get("mode"), "page")
        self.assertTrue(any("降级" in str(c) for c in out.get("caveats") or []))

    def test_server_rejects_unsafe_method_and_path(self) -> None:
        client = MagicMock()
        presented = {
            "entity": "work-orders",
            "label": "生产工单",
            "total": 1,
            "returned": 1,
            "filters_applied": {},
        }
        with patch(
            "tools.query_tool.aggregate.field_label_map",
            return_value={"status": "状态"},
        ):
            out = aggregate_by_field(
                entity="work-orders",
                group_by="状态",
                filters={"status": "x"},
                limit=100,
                client=client,
                entity_meta={
                    "aggregate": {
                        "path": "https://evil.example/stats",
                        "method": "DELETE",
                        "group_param": "groupBy",
                    },
                    "columns": [{"name": "status", "label": "状态"}],
                },
                records=[{"status": "a"}],
                presented=presented,
            )
        self.assertEqual(out.get("mode"), "page")
        client._request.assert_not_called()

    def test_server_sanitizes_query_keys(self) -> None:
        client = MagicMock()
        client._request.return_value = {
            "groups": [{"value": "a", "count": 1}],
            "total": 1,
        }
        presented = {
            "entity": "work-orders",
            "label": "生产工单",
            "total": 1,
            "returned": 1,
            "filters_applied": {},
        }
        with patch(
            "tools.query_tool.aggregate.field_label_map",
            return_value={"status": "状态"},
        ):
            out = aggregate_by_field(
                entity="work-orders",
                group_by="状态",
                filters={"status": "ok", "bad key!": "x", "": "y"},
                limit=100,
                client=client,
                entity_meta={
                    "aggregate": {"path": "/api/wo/stats", "group_param": "groupBy"},
                    "columns": [{"name": "status", "label": "状态"}],
                },
                records=[{"status": "a"}],
                presented=presented,
            )
        self.assertEqual(out.get("mode"), "server")
        called = client._request.call_args[0]
        self.assertEqual(called[0], "GET")
        self.assertIn("/api/wo/stats?", called[1])
        self.assertIn("groupBy=status", called[1])
        self.assertIn("status=ok", called[1])
        self.assertNotIn("bad", called[1])


if __name__ == "__main__":
    unittest.main()
