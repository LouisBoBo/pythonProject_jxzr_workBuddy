"""自动化执行指令 AI 改写单测（不连外网）。"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from automations.prompt_rewrite import rewrite_automation_prompt


class PromptRewriteTests(unittest.TestCase):
    def test_empty_draft_raises(self) -> None:
        with self.assertRaises(ValueError):
            rewrite_automation_prompt("  ")

    def test_rewrite_strips_fence_and_returns(self) -> None:
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "```\n【目标】汇总昨日工单\n【数据来源】当前 MES\n【输出格式】早报式\n```"
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        with patch("automations.prompt_rewrite._load_llm_client", return_value=(mock_client, "m")):
            out = rewrite_automation_prompt("查昨日工单", task_name="日报")
        self.assertIn("【目标】", out)
        self.assertNotIn("```", out)
        mock_client.chat.completions.create.assert_called_once()
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["temperature"], 0.2)
        user = kwargs["messages"][1]["content"]
        self.assertIn("查昨日工单", user)
        self.assertIn("日报", user)


if __name__ == "__main__":
    unittest.main()
