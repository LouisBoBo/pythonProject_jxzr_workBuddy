"""sse_flush 单测。"""
from __future__ import annotations

import os
import unittest

from sse_flush import (
    needs_process_flush,
    sse_comment_pad,
    sse_flush_sleep_sec,
    sse_pad_bytes,
)


class SseFlushTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("WORKBUDDY_SSE_PAD_BYTES", None)
        os.environ.pop("WORKBUDDY_SSE_FLUSH_SLEEP_SEC", None)

    def test_default_pad_comment(self) -> None:
        self.assertEqual(sse_pad_bytes(), 512)
        self.assertEqual(sse_flush_sleep_sec(), 0.0)
        pad = sse_comment_pad()
        self.assertTrue(pad.startswith(": "))
        self.assertTrue(pad.endswith("\n\n"))
        # ": " + 512 spaces
        self.assertEqual(len(pad), len(": \n\n") + 512)

    def test_zero_pad_is_minimal_comment(self) -> None:
        os.environ["WORKBUDDY_SSE_PAD_BYTES"] = "0"
        self.assertEqual(sse_comment_pad(), ":\n\n")

    def test_legacy_env(self) -> None:
        os.environ["WORKBUDDY_SSE_PAD_BYTES"] = "2048"
        os.environ["WORKBUDDY_SSE_FLUSH_SLEEP_SEC"] = "0.04"
        self.assertEqual(sse_pad_bytes(), 2048)
        self.assertAlmostEqual(sse_flush_sleep_sec(), 0.04)
        self.assertEqual(len(sse_comment_pad()), len(": \n\n") + 2048)

    def test_process_types(self) -> None:
        self.assertTrue(needs_process_flush("status"))
        self.assertTrue(needs_process_flush("confirm"))
        self.assertFalse(needs_process_flush("token"))


if __name__ == "__main__":
    unittest.main()
