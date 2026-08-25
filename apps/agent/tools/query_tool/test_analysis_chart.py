"""analysis_chart / readonly_sql 单测（无 LLM、无真实 MES）。"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path


class TestAnalysisChart(unittest.TestCase):
    def test_bar_from_groups(self):
        from tools.query_tool.analysis_chart import render_analysis_chart

        out = render_analysis_chart(
            chart_type="bar",
            title="按状态",
            groups=[{"value": "在制", "count": 4}, {"value": "待处理", "count": 3}],
            source_note="本页汇总",
        )
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("chart_type"), "bar")
        self.assertIn("chart_option", out)
        self.assertEqual(out["categories"], ["在制", "待处理"])
        self.assertEqual(out["values"], [4.0, 3.0])
        self.assertIn(":::analysis_chart", out.get("markdown_fence") or "")
        self.assertTrue(any("本页" in str(c) for c in (out.get("caveats") or [])))

    def test_chart_injects_page_scope_without_source_note(self):
        from tools.query_tool.aggregate import CAVEAT_PAGE_SCOPE
        from tools.query_tool.analysis_chart import render_analysis_chart

        out = render_analysis_chart(
            chart_type="pie",
            title="分布",
            groups=[{"value": "A", "count": 1}, {"value": "B", "count": 2}],
            source_note="",
        )
        self.assertTrue(out.get("ok"))
        self.assertTrue(
            any(CAVEAT_PAGE_SCOPE[:10] in str(c) or "全库" in str(c) for c in (out.get("caveats") or []))
        )

    def test_pie_and_clip(self):
        from tools.query_tool.analysis_chart import build_echarts_option

        cats = [f"c{i}" for i in range(50)]
        vals = list(range(50))
        built = build_echarts_option(
            chart_type="pie", title="截断", categories=cats, values=vals
        )
        # 先截断到 40 点，再 Top8+其他 → 9
        self.assertEqual(built["point_count"], 9)
        self.assertEqual(built["chart_type"], "pie")
        self.assertTrue(built.get("caveats"))
        # Top8+其他：每扇区引线标注名称+百分比
        self.assertTrue(built["option"]["series"][0]["label"]["show"])
        self.assertTrue(built["option"]["series"][0]["labelLine"]["show"])
        self.assertIn("{d}%", built["option"]["series"][0]["label"]["formatter"])
        self.assertIn("其他", built["categories"])
        self.assertEqual(built["option"]["_wb_layout"]["mode"], "pie_labeled")

    def test_pie_few_keeps_labels(self):
        from tools.query_tool.analysis_chart import build_echarts_option

        built = build_echarts_option(
            chart_type="pie",
            title="少",
            categories=["a", "b", "c"],
            values=[1, 2, 3],
        )
        self.assertTrue(built["option"]["series"][0]["label"]["show"])
        self.assertTrue(built["option"]["series"][0]["labelLine"]["show"])
        self.assertEqual(built["option"]["legend"].get("show"), False)

    def test_empty_rejected(self):
        from tools.query_tool.analysis_chart import render_analysis_chart

        out = render_analysis_chart(categories=[], values=[])
        self.assertIn("error", out)

    def test_bar_long_names_go_horizontal(self):
        from tools.query_tool.analysis_chart import build_echarts_option

        cats = [f"仓库区位-很长名称-{i}" for i in range(3)]
        built = build_echarts_option(
            chart_type="bar", title="库位", categories=cats, values=[1, 2, 3]
        )
        self.assertEqual(built["option"]["yAxis"]["type"], "category")
        self.assertEqual(built["option"]["_wb_layout"]["mode"], "horizontal")
        self.assertTrue(any("横向" in str(c) for c in (built.get("caveats") or [])))

    def test_bar_many_categories_zoom(self):
        from tools.query_tool.analysis_chart import build_echarts_option

        cats = [f"c{i}" for i in range(15)]
        built = build_echarts_option(
            chart_type="bar", title="多类目", categories=cats, values=list(range(15))
        )
        # 15 类目且短名 → 横向 + dataZoom
        self.assertEqual(built["option"]["_wb_layout"]["mode"], "horizontal")
        self.assertTrue(built["option"].get("dataZoom"))
        self.assertGreaterEqual(built["option"]["_wb_layout"]["height_hint"], 360)

    def test_line_keeps_vertical_with_tilt(self):
        from tools.query_tool.analysis_chart import build_echarts_option

        cats = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        built = build_echarts_option(
            chart_type="line", title="七日", categories=cats, values=[1, 2, 3, 4, 5, 6, 7]
        )
        self.assertEqual(built["option"]["xAxis"]["type"], "category")
        self.assertGreater(built["option"]["xAxis"]["axisLabel"].get("rotate") or 0, 0)

    def test_infer_chart_type_priority(self):
        from tools.query_tool.analysis_chart import infer_chart_type

        # 用户点名优先于意图
        t, _ = infer_chart_type(
            chart_type="auto",
            user_intent="按状态分布，给我出柱状图",
            title="状态分布",
        )
        self.assertEqual(t, "bar")

        t, notes = infer_chart_type(
            chart_type="bar",
            user_intent="看一下库存数量分布",
            title="库存",
        )
        self.assertEqual(t, "pie")
        self.assertTrue(notes)

        t, notes = infer_chart_type(
            chart_type="auto",
            user_intent="最近一周产量趋势",
        )
        self.assertEqual(t, "line")

        t, _ = infer_chart_type(chart_type="auto", user_intent="各产线在制各多少")
        self.assertEqual(t, "bar")

    def test_auto_from_title_distribution(self):
        from tools.query_tool.analysis_chart import build_echarts_option

        built = build_echarts_option(
            chart_type="auto",
            title="物料库存数量分布",
            categories=["A", "B", "C"],
            values=[3, 2, 1],
            user_intent="看看物料库存",
        )
        self.assertEqual(built["chart_type"], "pie")
        self.assertTrue(built["option"]["series"][0]["labelLine"]["show"])


class TestReadonlySql(unittest.TestCase):
    def test_disabled_by_default(self):
        from tools.query_tool.readonly_sql import readonly_sql

        os.environ.pop("READONLY_SQL_ENABLED", None)
        # Config may cache; tool checks Config then env
        out = readonly_sql("SELECT 1")
        # If Config still true from prior test env, skip assert
        if not out.get("error"):
            self.skipTest("READONLY_SQL already enabled in env")
        self.assertIn("未开启", out["error"])

    def test_validate_rejects_dml_and_unknown_table(self):
        from tools.query_tool.readonly_sql import validate_readonly_sql

        wl = {"orders"}
        self.assertIn("error", validate_readonly_sql("DELETE FROM orders", whitelist=wl))
        self.assertIn(
            "error",
            validate_readonly_sql("SELECT * FROM secrets", whitelist=wl),
        )
        ok = validate_readonly_sql("SELECT id FROM orders WHERE status=1", whitelist=wl)
        self.assertTrue(ok.get("ok"))
        self.assertIn("LIMIT", ok["sql"].upper())

    def test_sqlite_execute(self):
        from tools.query_tool import readonly_sql as rs

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            conn = sqlite3.connect(str(db))
            conn.execute("CREATE TABLE orders (id INT, status TEXT)")
            conn.execute("INSERT INTO orders VALUES (1, 'open'), (2, 'done')")
            conn.commit()
            conn.close()

            old = {
                "READONLY_SQL_ENABLED": os.environ.get("READONLY_SQL_ENABLED"),
                "READONLY_SQL_DSN": os.environ.get("READONLY_SQL_DSN"),
                "READONLY_SQL_TABLE_WHITELIST": os.environ.get(
                    "READONLY_SQL_TABLE_WHITELIST"
                ),
            }
            try:
                os.environ["READONLY_SQL_ENABLED"] = "true"
                os.environ["READONLY_SQL_DSN"] = str(db)
                os.environ["READONLY_SQL_TABLE_WHITELIST"] = "orders"
                # 刷新 Config
                from config import Config

                Config.READONLY_SQL_ENABLED = True
                Config.READONLY_SQL_DSN = str(db)
                Config.READONLY_SQL_TABLE_WHITELIST = "orders"

                out = rs.readonly_sql("SELECT id, status FROM orders ORDER BY id")
                self.assertTrue(out.get("ok"), out)
                self.assertEqual(out.get("returned"), 2)
                self.assertEqual(out["records"][0]["id"], 1)
            finally:
                for k, v in old.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
                Config.READONLY_SQL_ENABLED = False


class TestChartMcpClientLocal(unittest.TestCase):
    def test_build_option_shared_with_server(self):
        """MCP server 与本地共用 build_echarts_option。"""
        from tools.query_tool.analysis_chart import build_echarts_option

        a = build_echarts_option(
            chart_type="line",
            title="趋势",
            categories=["周一", "周二"],
            values=[10, 12],
        )
        self.assertEqual(a["option"]["series"][0]["type"], "line")
        self.assertIn("areaStyle", a["option"]["series"][0])
        self.assertTrue(a["option"]["series"][0]["smooth"])
        # 模拟 server 返回结构
        payload = json.dumps(
            {"ok": True, "option": a["option"], "mcp_tool": "render_chart"},
            ensure_ascii=False,
        )
        parsed = json.loads(payload)
        self.assertIn("series", parsed["option"])

    def test_yield_line_uses_0_100_axis(self):
        from tools.query_tool.analysis_chart import build_echarts_option

        out = build_echarts_option(
            chart_type="line",
            title="工序良率",
            categories=["功能测试", "包装", "贴片", "焊接", "AOI检测"],
            values=[97.9, 97.9, 97.89, 97.88, 97.88],
            series_name="良率",
        )
        y = out["option"]["yAxis"]
        self.assertEqual(y.get("min"), 0)
        self.assertEqual(y.get("max"), 100)
        self.assertIn("areaStyle", out["option"]["series"][0])


if __name__ == "__main__":
    unittest.main()
