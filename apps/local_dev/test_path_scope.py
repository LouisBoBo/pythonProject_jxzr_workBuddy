"""写范围 path_scope 单测。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_dev.path_scope import (
    list_workspace_entries,
    normalize_write_scope,
    partition_by_scope,
    path_in_scope,
)


class PathScopeTests(unittest.TestCase):
    def test_empty_scope_allows_all(self) -> None:
        self.assertTrue(path_in_scope("a/b.py", []))
        inside, outside = partition_by_scope(["a.py", "b/c.js"], [])
        self.assertEqual(inside, ["a.py", "b/c.js"])
        self.assertEqual(outside, [])

    def test_file_and_dir_prefix(self) -> None:
        scope = normalize_write_scope(["src/App.vue", "apps/web/"])
        self.assertTrue(path_in_scope("src/App.vue", scope))
        self.assertFalse(path_in_scope("src/Other.vue", scope))
        self.assertTrue(path_in_scope("apps/web/x.js", scope))
        self.assertFalse(path_in_scope("apps/api/x.py", scope))

    def test_file_without_slash_is_exact_only(self) -> None:
        # 不带尾斜杠只匹配该文件，禁止当目录前缀（防误扩写）
        self.assertFalse(path_in_scope("src/foo.ts", ["src"]))
        self.assertTrue(path_in_scope("src", ["src"]))
        self.assertTrue(path_in_scope("src/foo.ts", ["src/"]))
        self.assertFalse(path_in_scope("src2/foo.ts", ["src/"]))

    def test_reject_dotdot_and_weird(self) -> None:
        self.assertEqual(normalize_write_scope(["../etc/passwd"]), [])
        self.assertEqual(normalize_write_scope(["C:/Windows"]), [])
        self.assertEqual(normalize_write_scope(["~/secret"]), [])

    def test_list_entries(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.txt").write_text("x", encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "b.txt").write_text("y", encoding="utf-8")
            (root / ".git").mkdir()
            out = list_workspace_entries(root, subdir="")
            self.assertTrue(out["ok"])
            names = {e["name"] for e in out["entries"]}
            self.assertIn("a.txt", names)
            self.assertIn("sub", names)
            self.assertNotIn(".git", names)
            nested = list_workspace_entries(root, subdir="sub")
            self.assertEqual(nested["cwd"], "sub")
            self.assertTrue(any(e["name"] == "b.txt" for e in nested["entries"]))


if __name__ == "__main__":
    unittest.main()
