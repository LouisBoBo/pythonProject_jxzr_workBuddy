"""视觉提示选择：红框标注 vs 复刻。"""
from __future__ import annotations

import unittest

from tools.vision_describe import (
    _prompt_for_hint,
    is_annotation_edit_hint,
    is_ui_replica_hint,
)


class VisionHintTests(unittest.TestCase):
    def test_red_box_is_annotation(self) -> None:
        self.assertTrue(is_annotation_edit_hint("修改登录界面 红框处去掉"))
        self.assertIn("标注", _prompt_for_hint("红框处去掉"))

    def test_replica_still_works(self) -> None:
        self.assertTrue(is_ui_replica_hint("按截图 1:1 复刻登录页"))
        self.assertFalse(is_annotation_edit_hint("按截图 1:1 复刻登录页"))
        p = _prompt_for_hint("按截图 1:1 复刻登录页")
        self.assertIn("复刻", p)

    def test_annotation_beats_replica_keywords(self) -> None:
        # 同时出现时优先读标注目标
        p = _prompt_for_hint("按截图改，红框处去掉")
        self.assertIn("标注", p)


if __name__ == "__main__":
    unittest.main()
