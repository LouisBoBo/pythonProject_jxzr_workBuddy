"""对话模型黑名单硬闸单测。"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from llm_model_guard import (
    assert_llm_model_allowed,
    assert_models_in_mapping,
    is_llm_model_blocked,
)


class LlmModelGuardTests(unittest.TestCase):
    def test_blocks_v4_pro(self) -> None:
        self.assertTrue(is_llm_model_blocked("deepseek-v4-pro"))
        self.assertTrue(is_llm_model_blocked("DeepSeek-V4-Pro"))
        with self.assertRaises(ValueError) as ctx:
            assert_llm_model_allowed("deepseek-v4-pro")
        self.assertIn("deepseek-v4-pro", str(ctx.exception))
        self.assertIn("禁止", str(ctx.exception))

    def test_allows_flash_and_chat(self) -> None:
        self.assertFalse(is_llm_model_blocked("deepseek-v4-flash"))
        self.assertFalse(is_llm_model_blocked("deepseek-chat"))
        self.assertEqual(assert_llm_model_allowed("deepseek-v4-flash"), "deepseek-v4-flash")

    def test_settings_mapping_rejected(self) -> None:
        with self.assertRaises(ValueError):
            assert_models_in_mapping({"MAIN_MODEL": "deepseek-v4-pro"})

    def test_allow_env_override(self) -> None:
        with patch.dict(os.environ, {"LLM_ALLOW_BLOCKED_MODELS": "1"}, clear=False):
            self.assertEqual(
                assert_llm_model_allowed("deepseek-v4-pro"),
                "deepseek-v4-pro",
            )


if __name__ == "__main__":
    unittest.main()
