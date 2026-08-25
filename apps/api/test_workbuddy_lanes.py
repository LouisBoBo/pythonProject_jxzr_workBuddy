"""车道路由单测（无 LLM）。"""
from __future__ import annotations

import unittest

from workbuddy_lanes import (
    LANE_CODE_DEV,
    LANE_CODE_REVIEW,
    LANE_PASTE_CODE,
    drop_leading_english_aside,
    is_cursor_dev_coding_lane,
    resolve_workbuddy_lane,
    should_attach_shot_images_for_discuss,
)


class WorkbuddyLanesTests(unittest.TestCase):
    def test_explicit_lane(self) -> None:
        self.assertEqual(
            resolve_workbuddy_lane("随便", {"workbuddy_lane": "code_dev"}),
            LANE_CODE_DEV,
        )
        self.assertEqual(
            resolve_workbuddy_lane("", {"workbuddy_lane": "paste_code"}),
            LANE_PASTE_CODE,
        )

    def test_explicit_source(self) -> None:
        from workbuddy_lanes import resolve_workbuddy_lane_detail

        d = resolve_workbuddy_lane_detail("【写码需求讨论】x", {"workbuddy_lane": "code_review"})
        self.assertEqual(d.lane, LANE_CODE_REVIEW)
        self.assertEqual(d.source, "explicit")

    def test_marker_fallback_source(self) -> None:
        from workbuddy_lanes import resolve_workbuddy_lane_detail

        d = resolve_workbuddy_lane_detail("【写码需求讨论】加登录", {}, log_marker_fallback=False)
        self.assertEqual(d.lane, LANE_CODE_DEV)
        self.assertEqual(d.source, "marker")

    def test_unknown_lane_ignored(self) -> None:
        from workbuddy_lanes import normalize_workbuddy_lane, sanitize_page_context_lanes

        self.assertIsNone(normalize_workbuddy_lane("hack_me"))
        cleaned = sanitize_page_context_lanes({"workbuddy_lane": "nope", "x": 1})
        self.assertNotIn("workbuddy_lane", cleaned)
        self.assertEqual(cleaned.get("x"), 1)

    def test_dev_marker(self) -> None:
        self.assertEqual(
            resolve_workbuddy_lane("【写码需求讨论】加登录页"),
            LANE_CODE_DEV,
        )
        self.assertTrue(is_cursor_dev_coding_lane("【写码仓库已确认】"))

    def test_review_marker(self) -> None:
        self.assertEqual(
            resolve_workbuddy_lane("【Git仓库已确认】https://github.com/a/b"),
            LANE_CODE_REVIEW,
        )

    def test_conflict_prefers_explicit_confirm(self) -> None:
        msg = "【写码需求讨论】【Git仓库已确认】"
        self.assertEqual(resolve_workbuddy_lane(msg), LANE_CODE_REVIEW)

    def test_drop_english_keeps_report(self) -> None:
        buf = "Now I will compile.\n\n## 🔍 代码审核报告\n- ok\n"
        out = drop_leading_english_aside(buf)
        self.assertTrue(out.startswith("## 🔍 代码审核报告"))

    def test_vision_keep_on_1to1(self) -> None:
        self.assertTrue(should_attach_shot_images_for_discuss("按截图 1:1 复刻登录页"))

    def test_vision_not_skipped_by_injected_design_sense(self) -> None:
        from workbuddy_lanes import should_attach_shot_images_for_discuss

        # 模拟 buildCodingDiscussPrompt：注入块含「设计感」，用户原话是红框改动
        msg = (
            "【写码需求讨论 · 远程 Cursor Cloud】…\n"
            "【产品设计 · Skill ui-product-design】做/改业务页时必须有设计感：一页一身份。\n"
            "【交互铁律】能勾选就不输入。\n"
            "用户说：登录页红框内容右移到登录卡顶部\n"
        )
        self.assertTrue(should_attach_shot_images_for_discuss(msg))

    def test_vision_skip_real_redesign_utterance(self) -> None:
        from workbuddy_lanes import should_attach_shot_images_for_discuss

        self.assertFalse(
            should_attach_shot_images_for_discuss("用户说：这个页面重做一下更有设计感\n")
        )

    def test_paste_only_via_explicit(self) -> None:
        self.assertEqual(
            resolve_workbuddy_lane("看下这段", {"workbuddy_lane": "paste_code"}),
            LANE_PASTE_CODE,
        )
        self.assertIsNone(resolve_workbuddy_lane("看下这段", {}))

    def test_ctx_cursor_dev_lane_flag(self) -> None:
        self.assertEqual(
            resolve_workbuddy_lane("随便", {"cursor_dev_lane": True}),
            LANE_CODE_DEV,
        )


if __name__ == "__main__":
    unittest.main()
