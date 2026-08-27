"""企微推送 P0 单测。"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from automations.delivery import deliver_automation_run
from automations.run_summary_text import (
    format_plain_text,
    format_wecom_markdown,
    format_wecom_push,
    format_wecom_text,
    parse_run_summary,
)
from automations.wecom_bot import normalize_webhook_key, send_markdown, send_push_with_retry, send_text


SAMPLE_NEWS = """今日 PCB+AI 领域要闻如下：

**1. 某厂发布 AI 辅助布线工具**
要点：提升高密度板设计效率。
来源：https://example.com/news/1

**2. 行业峰会聚焦智能制造**
要点：AI 与 PCB 检测结合。
来源：行业媒体
"""


SAMPLE_PLAIN_NEWS = """已完成检索（智谱 Web Search）。

1. 沪电股份半年报：AI 驱动业绩高增
要点：营收同比 +61%。
来源：沪电股份 2026 年半年度报告。无原文链接。

2. 特创科技：AI 服务器级 PCB 量产
要点：进入全线规模化量产。
来源：特创科技（转载自 PCB 行业媒体）。
"""


class RunSummaryTextTests(unittest.TestCase):
    def test_parse_plain_numbered_news(self):
        parsed = parse_run_summary(SAMPLE_PLAIN_NEWS)
        self.assertEqual(parsed["kind"], "news")
        self.assertEqual(len(parsed["items"]), 2)
        self.assertIn("沪电股份", parsed["items"][0]["title"])
        self.assertIn("检索", parsed.get("intro") or "")

    def test_format_wecom_text_has_separators(self):
        text = format_wecom_text(SAMPLE_PLAIN_NEWS, "每日PCB+AI新闻推送", started_at=1787878800)
        self.assertIn("- - - -", text)
        self.assertIn("\n\n1. 沪电股份", text)
        self.assertNotIn("无原文链接", text)

    def test_format_wecom_push_single_message(self):
        msgtype, content = format_wecom_push(SAMPLE_PLAIN_NEWS, started_at=1787878800)
        self.assertIn(msgtype, ("text", "markdown"))
        self.assertIn("📰", content)
        self.assertIn("1. 沪电股份", content)
        self.assertIn("- - - -", content)
        self.assertNotIn("【1/2】", content)

    def test_parse_news_items(self):
        parsed = parse_run_summary(SAMPLE_NEWS)
        self.assertEqual(parsed["kind"], "news")
        self.assertEqual(len(parsed["items"]), 2)
        self.assertIn("AI 辅助布线", parsed["items"][0]["title"])

    def test_format_wecom_markdown_has_header(self):
        md = format_wecom_markdown(SAMPLE_NEWS, "每日PCB+AI新闻推送", started_at=1787878800)
        self.assertIn("## 📰", md)
        self.assertIn("**1.", md)
        self.assertIn("[来源](https://example.com/news/1)", md)
        # 企微 Markdown 须双换行分段
        self.assertIn("要点：提升高密度板设计效率。\n\n[来源]", md)
        self.assertIn("- - - -", md)

    def test_format_wecom_markdown_strips_meta_source(self):
        raw = """**1. 测试标题**
要点：内容
来源：2026-08-26 行业报道（检索结果未附可点击链接）
"""
        md = format_wecom_markdown(raw, "测试")
        self.assertNotIn("检索结果未附", md)
        self.assertIn("2026-08-26 行业报道", md)

    def test_parse_news_with_trailing_date_in_points(self):
        raw = """**1. AI 算力驱动高端 PCB 板块景气延续**
要点：Prismark 预计未来 5 年服务器需求增长。（2026-08-26）

**2. PCB 钻针产业量价齐升**
要点：AI 服务器 PCB 层数持续升高。（2026-08-27）
"""
        parsed = parse_run_summary(raw)
        self.assertEqual(parsed["items"][0]["source"], "2026-08-26")
        self.assertNotIn("2026-08-26", parsed["items"][0]["points"])
        self.assertEqual(parsed["items"][1]["source"], "2026-08-27")

    def test_parse_news_bullet_body_with_source_line(self):
        raw = """**1. 鹏鼎控股董事长：AI 服务器 PCB 业务正处快速追赶阶段**
- 鹏鼎控股正式将 AI 服务器 PCB 确立为第二成长曲线。
- 高阶 HDI 已通过主流客户认证并批量供货。
- 来源：中国银河证券研究报告/业绩说明会报道（检索结果未返回可点击链接）
"""
        parsed = parse_run_summary(raw)
        self.assertIn("鹏鼎控股", parsed["items"][0]["points"])
        self.assertIn("中国银河证券", parsed["items"][0]["source"])
        self.assertNotIn("检索结果未返回", parsed["items"][0]["source"])

    def test_parse_news_strips_trend_footer(self):
        raw = """**5. 特创科技：AI 服务器级二次电源 PCB 进入全线规模化量产**
要点：产品覆盖 14-24 层 HDI。（2026-08-27）

---
**趋势小结**：今日信息集中在三条主线。
"""
        parsed = parse_run_summary(raw)
        self.assertEqual(parsed["items"][0]["source"], "2026-08-27")
        self.assertNotIn("趋势小结", parsed["items"][0]["points"])

    def test_parse_news_title_date_fallback(self):
        raw = """**2. AI 算力驱动高端 PCB 板块景气延续**（2026-08-26）
- 高盛上调全球 AI 服务器 PCB 市场预测。
- 行业整体产能仍非常紧张。
"""
        parsed = parse_run_summary(raw)
        self.assertEqual(parsed["items"][0]["source"], "2026-08-26")
        self.assertIn("高盛", parsed["items"][0]["points"])

    def test_format_plain_text_numbered_report(self):
        report = """一、已完成工作
1、落地自动化调度
2、接入联网搜索

二、下周计划
1、企微推送
"""
        parsed = parse_run_summary(report)
        self.assertEqual(parsed["kind"], "report")
        plain = format_plain_text(report, "周报")
        self.assertIn("1、落地自动化调度", plain)


class WecomDeliveryTests(unittest.TestCase):
    def test_normalize_webhook_key_from_url(self):
        url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc-123-def"
        self.assertEqual(normalize_webhook_key(url), "abc-123-def")

    def test_normalize_webhook_key_raw(self):
        self.assertEqual(normalize_webhook_key("abc-123-def"), "abc-123-def")

    def test_normalize_webhook_key_rejects_foreign_host(self):
        with self.assertRaises(ValueError):
            normalize_webhook_key("https://evil.example.com/cgi-bin/webhook/send?key=abc")

    @patch("automations.delivery.send_push_with_retry")
    @patch("automations.delivery.push_enabled", return_value=True)
    @patch("automations.delivery.webhook_key", return_value="test-key")
    def test_deliver_success(self, _k, _e, mock_send):
        from pathlib import Path

        mock_send.return_value = {"ok": True, "errcode": 0, "errmsg": "ok"}
        out = deliver_automation_run(
            Path("data"),
            {"id": "auto-x", "name": "每日PCB+AI新闻推送", "push_to_wecom": True},
            "run-1",
            SAMPLE_NEWS,
            started_at=1787878800,
        )
        self.assertEqual(out["delivery_status"], "sent")
        self.assertIsNotNone(out["delivered_at"])
        mock_send.assert_called_once()

    @patch("automations.delivery.webhook_key", return_value="")
    def test_deliver_skipped_no_key(self, _k):
        from pathlib import Path

        out = deliver_automation_run(
            Path("data"),
            {"push_to_wecom": True},
            "run-1",
            SAMPLE_NEWS,
        )
        self.assertEqual(out["delivery_status"], "skipped")

    def test_deliver_skipped_flag_off(self):
        from pathlib import Path

        out = deliver_automation_run(
            Path("data"),
            {"push_to_wecom": False},
            "run-1",
            SAMPLE_NEWS,
        )
        self.assertEqual(out["delivery_status"], "skipped")

    @patch("automations.wecom_bot.push_dry_run", return_value=True)
    def test_send_text_dry_run(self, _d):
        out = send_text("hello\n\nworld")
        self.assertTrue(out["ok"])
        self.assertTrue(out.get("dry_run"))

    @patch("automations.wecom_bot.push_dry_run", return_value=True)
    def test_send_markdown_dry_run(self, _d):
        out = send_markdown("## hello")
        self.assertTrue(out["ok"])
        self.assertTrue(out.get("dry_run"))


if __name__ == "__main__":
    unittest.main()
