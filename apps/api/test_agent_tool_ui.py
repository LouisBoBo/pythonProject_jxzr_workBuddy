"""agent_tool_ui 单测：过程区标题与失败判定。"""
from __future__ import annotations

import unittest

from agent_tool_ui import (
    _IDE_BATCH_TOOLS,
    _as_text,
    _extract_json_object,
    _is_tool_failure,
    _parse_jsonish,
    _strip_line_numbers,
    _tool_label,
)


class AgentToolUiTests(unittest.TestCase):
    def test_tool_label_with_entity(self) -> None:
        self.assertEqual(
            _tool_label("query_platform_data", {"entity": "work_order"}),
            "查询平台数据 · work_order",
        )

    def test_ide_batch_label(self) -> None:
        self.assertIn(
            "第 2 批",
            _tool_label("request_ide_read_batch", {"batch_index": 1}),
        )
        self.assertIn("request_ide_read_batch", _IDE_BATCH_TOOLS)

    def test_is_tool_failure(self) -> None:
        self.assertTrue(_is_tool_failure({"error": "boom"}))
        self.assertFalse(_is_tool_failure({"status": "pending_confirmation", "action_id": "a"}))
        self.assertTrue(_is_tool_failure({"status": "offline", "message": "bridge down"}))

    def test_parse_and_strip(self) -> None:
        self.assertEqual(_parse_jsonish('{"x": 1}')["x"], 1)
        stripped = _strip_line_numbers("1|hello\n2|world")
        self.assertIn("hello", stripped)
        self.assertNotIn("1|", stripped.splitlines()[0] if stripped else "")

    def test_extract_write_confirm_json(self) -> None:
        blob = 'prefix {"__write_confirm__": true, "action_id": "a1", "status": "pending_confirmation"} tail'
        obj = _extract_json_object(blob)
        self.assertIsInstance(obj, dict)
        self.assertEqual(obj.get("action_id"), "a1")
        self.assertTrue(_as_text({"a": 1}).startswith("{"))


if __name__ == "__main__":
    unittest.main()
