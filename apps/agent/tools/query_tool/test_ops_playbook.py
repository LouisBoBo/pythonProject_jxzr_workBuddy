"""运维场景清单与标准链（不写死 work-orders）。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_AGENT = Path(__file__).resolve().parents[2]
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from tools.query_tool.ops_playbook import find_ops_scene, list_ops_scenes, load_ops_scenes, run_ops_scene


class OpsPlaybookTests(unittest.TestCase):
    def test_at_least_eight_scenes(self) -> None:
        pack = load_ops_scenes()
        self.assertGreaterEqual(len(pack.get("scenes") or []), 8)

    def test_find_scene_by_alias(self) -> None:
        self.assertEqual(find_ops_scene("紧急工单")["id"], "urgent-backlog")
        self.assertEqual(find_ops_scene("紧急工单有哪些")["id"], "urgent-backlog")
        self.assertEqual(find_ops_scene("急单")["id"], "urgent-backlog")
        self.assertEqual(find_ops_scene("谁导入了")["id"], "write-audit-who")
        self.assertEqual(find_ops_scene("接口通不通")["id"], "api-health-sandbox")
        self.assertEqual(find_ops_scene("MES 401")["id"], "login-mes-auth-help")
        self.assertEqual(find_ops_scene("查不到数据")["id"], "ops-diagnose")
        self.assertEqual(find_ops_scene("值班简报")["id"], "ops-daily-brief")

    def test_list_ops_scenes_shape(self) -> None:
        out = list_ops_scenes()
        self.assertGreaterEqual(out["count"], 8)
        ids = {s["id"] for s in out["scenes"]}
        self.assertIn("urgent-backlog", ids)
        self.assertIn("api-health-sandbox", ids)
        self.assertIn("write-audit-who", ids)

    def test_api_health_scene_defaults_sandbox_rules(self) -> None:
        out = run_ops_scene("接口通不通")
        self.assertEqual(out.get("kind"), "api_health")
        blob = " ".join(out.get("rules") or [])
        self.assertIn("sandbox", blob.lower())
        self.assertIn("live", blob.lower())
        self.assertTrue(any("probe_api_catalog" in t for t in out.get("next_tools") or []))

    def test_guidance_login_no_secrets(self) -> None:
        fake_page = {
            "items": [
                {
                    "ts": 1780000000,
                    "method": "GET",
                    "path": "/api/work-orders?page=1",
                    "status": 401,
                    "token": "should-not-leak",
                }
            ]
        }
        with patch("tools.api_log_tool.call_store.query_api_calls", return_value=fake_page):
            out = run_ops_scene("401")
        self.assertEqual(out.get("kind"), "guidance")
        text = " ".join(out.get("bullets") or [])
        self.assertIn("WorkBuddy", text)
        self.assertIn("MES", text)
        self.assertIn("401", text)
        self.assertNotIn("password=", text.lower())
        self.assertNotIn("should-not-leak", text)
        self.assertNotIn("should-not-leak", str(out.get("recent_auth_errors") or {}))
        sample = (out.get("recent_auth_errors") or {}).get("sample") or []
        self.assertTrue(sample)
        self.assertNotIn("?", sample[0].get("path", ""))

    def test_metric_chain_calls_query_metric(self) -> None:
        fake = {
            "entity": "tickets",
            "label": "生产工单",
            "total": 2,
            "returned": 2,
            "records": [
                {"status": "in_progress", "priority": "urgent"},
                {"status": "pending", "priority": "high"},
            ],
            "definition": "紧急未完工",
            "markdown_table": "| a |",
        }
        with patch("tools.query_tool.platform_query.query_metric", return_value=fake):
            out = run_ops_scene("紧急工单", export=False)
        self.assertEqual(out.get("scene"), "urgent-backlog")
        self.assertIn("summary", out)
        self.assertEqual(out["summary"]["groups"][0]["count"], 1)

    def test_write_audit_scene(self) -> None:
        fake = {"returned": 1, "records": [{"username": "admin", "file": "a.csv"}], "note": "近 30 天"}
        with patch("tools.write_audit_query.query_write_audit", return_value=fake):
            out = run_ops_scene("导入失败")
        self.assertEqual(out.get("scene"), "write-audit-failed")
        self.assertEqual(out["result"]["returned"], 1)

    def test_diagnose_does_not_query_mes(self) -> None:
        with patch("tools.query_tool.ops_playbook._mes_query_readiness", return_value={
            "has_mes_credentials": True,
            "has_api_base": True,
            "entity_count": 2,
            "catalog_ready": True,
        }), patch("tools.query_tool.ops_playbook._recent_erp_auth_errors", return_value={"count": 1, "sample": []}), patch(
            "tools.query_tool.ops_playbook._recent_erp_failures",
            return_value={"count": 0, "sample": []},
        ):
            out = run_ops_scene("故障排查")
        self.assertEqual(out.get("kind"), "diagnose")
        ids = {b["id"] for b in out.get("likely") or []}
        self.assertIn("http-401", ids)

    def test_daily_brief_skips_unbound(self) -> None:
        listed = {
            "metrics": [
                {"id": "wip", "label": "在制", "definition": "进行中", "bindable": True, "entity": "tickets"},
                {"id": "x", "label": "绑不上", "bindable": False, "reason": "无匹配实体"},
            ]
        }
        fake = {"entity": "tickets", "total": 4, "returned": 4}
        with (
            patch("tools.query_tool.platform_query.list_query_metrics", return_value=listed),
            patch("tools.query_tool.platform_query.query_metric", return_value=fake),
        ):
            out = run_ops_scene("值班简报")
        self.assertEqual(out.get("kind"), "daily_brief")
        by_id = {r["id"]: r for r in out.get("metrics") or []}
        self.assertEqual(by_id["wip"]["total"], 4)
        self.assertIn("skipped", by_id["x"])


if __name__ == "__main__":
    unittest.main()
