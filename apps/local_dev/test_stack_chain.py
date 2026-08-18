"""列表加字段须走完整数据链路。"""
from __future__ import annotations

import unittest

from local_dev.prompts import SYSTEM_PROMPT, build_user_prompt
from local_dev.stack_chain import looks_like_data_ui_change


class StackChainTests(unittest.TestCase):
    def test_detects_add_column(self) -> None:
        self.assertTrue(looks_like_data_ui_change("给工单列表加一列实际开始时间"))
        self.assertFalse(looks_like_data_ui_change("【任务档位：css_layout】去掉横向滚动"))
        self.assertFalse(looks_like_data_ui_change("做成跟截图一样的登录页"))

    def test_user_prompt_includes_chain_for_new_column(self) -> None:
        p = build_user_prompt(
            requirement="给列表加一列实际开始时间",
            workspace_hint="/tmp/demo",
            empty_target=False,
        )
        self.assertIn("完整链路", p)
        self.assertIn("禁止只展示空列", p)
        self.assertIn("旧数据必须回填", p)

    def test_css_layout_skips_chain(self) -> None:
        p = build_user_prompt(
            requirement="【任务档位：css_layout】侧栏内部滚动",
            workspace_hint="/tmp/demo",
            empty_target=False,
        )
        self.assertNotIn("完整链路", p)

    def test_system_prompt_mentions_chain(self) -> None:
        self.assertIn("完整链路", SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
