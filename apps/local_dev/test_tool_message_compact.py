"""本机写码 LLM 回退：工具结果截断。"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from local_dev.service import _compact_tool_messages, _truncate_tool_json


class ToolMessageCompactTests(unittest.TestCase):
    def test_truncate_tool_json(self) -> None:
        big = "x" * 20000
        out = _truncate_tool_json(big, 1000)
        self.assertLess(len(out), 1100)
        self.assertIn("截断", out)

    def test_compact_old_tool_rounds(self) -> None:
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "go"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "1"}]},
            {"role": "tool", "tool_call_id": "1", "content": "a" * 5000},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "2"}]},
            {"role": "tool", "tool_call_id": "2", "content": "b" * 5000},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "3"}]},
            {"role": "tool", "tool_call_id": "3", "content": "c" * 5000},
        ]
        _compact_tool_messages(messages, keep_rounds=1, max_tool_chars=12000)
        self.assertGreater(len(messages[3]["content"]), 800)
        self.assertLess(len(messages[5]["content"]), 6000)
        self.assertEqual(messages[7]["content"], "c" * 5000)


if __name__ == "__main__":
    unittest.main()
