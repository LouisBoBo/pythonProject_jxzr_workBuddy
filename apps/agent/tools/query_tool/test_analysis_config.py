"""分析配置与可选行业包：换平台靠资料包，不写死实体。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_AGENT = Path(__file__).resolve().parents[2]
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))

from tools.query_tool.analysis_config import load_analysis_config
from tools.query_tool.metrics_pack import find_metric, load_metrics_pack


class AnalysisConfigTests(unittest.TestCase):
    def test_defaults_have_no_hardcoded_entity_ids(self) -> None:
        cfg = load_analysis_config()
        blob = json.dumps(cfg, ensure_ascii=False)
        self.assertNotIn("work-orders", blob)
        self.assertIn("状态", cfg["group_by_labels"])
        self.assertIn("wip", cfg["brief_metric_ids"])
        self.assertTrue(cfg.get("time_field_hints"))

    def test_time_field_hints_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pdir = Path(td)
            (pdir / "analysis.json").write_text(
                json.dumps({"time_field_hints": ["BizDate", "FinishTime"]}, ensure_ascii=False),
                encoding="utf-8",
            )
            with patch("mes_profile.profile_dir", return_value=pdir):
                cfg = load_analysis_config()
            self.assertEqual(cfg["time_field_hints"], ["BizDate", "FinishTime"])
            self.assertEqual(cfg["source"], "analysis.json")

    def test_analysis_json_overrides_group_labels(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pdir = Path(td)
            (pdir / "analysis.json").write_text(
                json.dumps(
                    {
                        "group_by_labels": ["车间", "状态"],
                        "brief_metric_ids": ["wip"],
                        "metric_packs": ["pcb"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch(
                "tools.query_tool.analysis_config.profile_dir",
                create=True,
            ):
                # patch mes_profile.profile_dir used inside load_analysis_config
                with patch("mes_profile.profile_dir", return_value=pdir):
                    cfg = load_analysis_config()
            self.assertEqual(cfg["group_by_labels"], ["车间", "状态"])
            self.assertEqual(cfg["brief_metric_ids"], ["wip"])
            self.assertEqual(cfg["metric_packs"], ["pcb"])
            self.assertEqual(cfg["source"], "analysis.json")


class MetricPackOptionalTests(unittest.TestCase):
    def test_pcb_metrics_absent_without_pack(self) -> None:
        with (
            patch("tools.query_tool.analysis_config.load_analysis_config") as m,
            patch("mes_profile.resolve_metrics_path", return_value=(None, "none")),
        ):
            m.return_value = {
                "group_by_labels": ["状态"],
                "brief_metric_ids": ["wip"],
                "metric_packs": [],
                "brief_metric_limit": 4,
                "source": "defaults",
            }
            pack = load_metrics_pack()
        ids = {str(x.get("id")) for x in pack.get("metrics") or []}
        self.assertIn("wip", ids)
        self.assertNotIn("aoi-fail-topn", ids)

    def test_pcb_metrics_present_when_pack_enabled(self) -> None:
        with patch("tools.query_tool.analysis_config.load_analysis_config") as m:
            m.return_value = {
                "group_by_labels": ["状态"],
                "brief_metric_ids": ["wip"],
                "metric_packs": ["pcb"],
                "brief_metric_limit": 4,
                "source": "test",
            }
            # still need resolve_metrics_path empty
            with patch("mes_profile.resolve_metrics_path", return_value=(None, "none")):
                pack = load_metrics_pack()
        ids = {str(x.get("id")) for x in pack.get("metrics") or []}
        self.assertIn("aoi-fail-topn", ids)
        self.assertIn("scrap-rate", ids)
        self.assertIn("daily-output", ids)
        self.assertIsNotNone(find_metric("AOI不良", pack))
        self.assertIsNotNone(find_metric("日产出", pack))
        scrap = find_metric("报废率", pack)
        self.assertIsNotNone(scrap)
        assert scrap is not None
        self.assertTrue(scrap.get("numerator_field_hints"))
        self.assertTrue(scrap.get("denominator_field_hints"))
        aoi = find_metric("缺陷码 Top", pack)
        self.assertIsNotNone(aoi)
        assert aoi is not None
        self.assertTrue(aoi.get("category_field_hints"))


if __name__ == "__main__":
    unittest.main()
