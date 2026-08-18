"""自检：视觉意图分类 + 上传路径穿越防护。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cursor_dev.prompts import (
    build_first_turn_prompt,
    classify_ui_visual_intent,
    should_attach_shot_images,
)
from tools.upload_paths import resolve_under_uploads, sanitize_client_file_paths


class VisualIntentTests(unittest.TestCase):
    def test_full_match_phrases(self):
        for text in (
            "根据此界面1:1复刻",
            "做成跟截图一样的登录页",
            "按这个效果改登录页",
            "【用户意图·视觉对齐】做成跟截图一样",
        ):
            self.assertEqual(
                classify_ui_visual_intent(text, has_images=True),
                "full_match",
                text,
            )

    def test_guided_edit(self):
        for text in (
            "按截图把登录按钮改大一点",
            "截图里顶栏颜色按图调一下",
            "【用户意图·按图修改】改顶栏",
        ):
            self.assertEqual(
                classify_ui_visual_intent(text, has_images=True),
                "guided_edit",
                text,
            )

    def test_redesign_and_none(self):
        self.assertEqual(
            classify_ui_visual_intent("这个页面重做一下更有设计感", has_images=True),
            "redesign",
        )
        self.assertEqual(
            classify_ui_visual_intent("这个报错是什么意思", has_images=True),
            "none",
        )

    def test_negated_replica_not_full_match(self):
        self.assertNotEqual(
            classify_ui_visual_intent("不要复刻旧截图，重新设计", has_images=True),
            "full_match",
        )
        self.assertEqual(
            classify_ui_visual_intent("不要复刻旧截图，重新设计", has_images=True),
            "redesign",
        )

    def test_attach_images_policy(self):
        self.assertFalse(should_attach_shot_images("重新设计这个页面更有设计感"))
        self.assertTrue(should_attach_shot_images("做成跟截图一样"))
        self.assertTrue(should_attach_shot_images("按截图改一下按钮"))

    def test_quality_first_prompt_for_full_match(self):
        p = build_first_turn_prompt(
            user_message="做成跟截图一样的登录页",
            repo="org/demo",
            work_branch="hebo",
            has_images=True,
        )
        self.assertIn("质量优先", p)
        self.assertNotIn("加速探索", p)

    def test_guided_prompt_not_rush_ban(self):
        p = build_first_turn_prompt(
            user_message="按截图把登录按钮改大一点",
            repo="org/demo",
            work_branch="hebo",
            has_images=True,
        )
        self.assertIn("按截图修改", p)
        self.assertNotIn("禁止赶工", p)

    def test_add_column_requires_data_stack_chain(self):
        p = build_first_turn_prompt(
            user_message="给工单列表加一列实际开始时间",
            repo="org/demo",
            work_branch="hebo",
        )
        self.assertIn("完整链路", p)
        self.assertIn("库表", p)

    def test_css_layout_skips_data_stack_chain(self):
        p = build_first_turn_prompt(
            user_message="【任务档位：css_layout】去掉横向滚动",
            repo="org/demo",
            work_branch="hebo",
        )
        self.assertNotIn("完整链路", p)


class UploadPathSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        self.uploads = self.data / "uploads"
        self.uploads.mkdir()
        self.outside = self.data / "secret.txt"
        self.outside.write_text("top-secret", encoding="utf-8")
        self.safe = self.uploads / "shot_1.png"
        self.safe.write_bytes(b"\x89PNG\r\n\x1a\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_allows_uploads_file(self):
        hit = resolve_under_uploads(str(self.safe), data_dir=self.data)
        self.assertEqual(hit, self.safe.resolve())

    def test_blocks_path_traversal(self):
        self.assertIsNone(
            resolve_under_uploads("../secret.txt", data_dir=self.data)
        )
        self.assertIsNone(
            resolve_under_uploads(str(self.outside), data_dir=self.data)
        )

    def test_blocks_symlink_escape(self):
        link = self.uploads / "escape.png"
        try:
            link.symlink_to(self.outside)
        except OSError:
            self.skipTest("symlink not permitted")
        self.assertIsNone(resolve_under_uploads(str(link), data_dir=self.data))

    def test_sanitize_filters_bad_paths(self):
        out = sanitize_client_file_paths(
            [str(self.safe), str(self.outside), "../../etc/passwd"],
            data_dir=self.data,
        )
        self.assertEqual(out, [str(self.safe.resolve())])

    def test_glob_metachar_in_name_does_not_crash(self):
        weird = self.uploads / "a[b]_1.png"
        weird.write_bytes(b"x")
        hit = resolve_under_uploads("a[b].png", data_dir=self.data)
        self.assertEqual(hit, weird.resolve())


if __name__ == "__main__":
    unittest.main()
