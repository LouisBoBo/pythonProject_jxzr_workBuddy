"""相对 import 闸门单测。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_dev.import_check import (
    extract_relative_specs,
    find_broken_relative_imports,
    format_repair_prompt,
    resolve_relative_import,
)


class ImportCheckTests(unittest.TestCase):
    def test_extract_specs(self) -> None:
        src = (
            "import VChart from 'vue-echarts'\n"
            "import { fetchX } from '../api/kanbanGeneral'\n"
            "const m = await import('./foo')\n"
        )
        specs = extract_relative_specs(src)
        self.assertEqual(specs, ["../api/kanbanGeneral", "./foo"])

    def test_kanban_wrong_depth_detected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            view = root / "frontend/src/views/kanban/ComprehensiveKanbanView.vue"
            api = root / "frontend/src/api/kanbanGeneral.js"
            view.parent.mkdir(parents=True)
            api.parent.mkdir(parents=True)
            api.write_text("export async function fetchX() {}\n", encoding="utf-8")
            view.write_text(
                "<script setup>\n"
                "import { fetchX } from '../api/kanbanGeneral'\n"
                "</script>\n",
                encoding="utf-8",
            )
            issues = find_broken_relative_imports(
                root, ["frontend/src/views/kanban/ComprehensiveKanbanView.vue"]
            )
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0]["import"], "../api/kanbanGeneral")
            self.assertIn("相对 import", format_repair_prompt(issues))

    def test_kanban_correct_depth_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            view = root / "frontend/src/views/kanban/ComprehensiveKanbanView.vue"
            api = root / "frontend/src/api/kanbanGeneral.js"
            view.parent.mkdir(parents=True)
            api.parent.mkdir(parents=True)
            api.write_text("export async function fetchX() {}\n", encoding="utf-8")
            view.write_text(
                "<script setup>\n"
                "import { fetchX } from '../../api/kanbanGeneral'\n"
                "</script>\n",
                encoding="utf-8",
            )
            issues = find_broken_relative_imports(
                root, ["frontend/src/views/kanban/ComprehensiveKanbanView.vue"]
            )
            self.assertEqual(issues, [])
            resolved = resolve_relative_import(view, "../../api/kanbanGeneral")
            self.assertEqual(resolved, api.resolve())


if __name__ == "__main__":
    unittest.main()
