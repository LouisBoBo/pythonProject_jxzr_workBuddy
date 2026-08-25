"""文件管理路由辅助逻辑单测。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_API = Path(__file__).resolve().parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from routes import files as fm  # noqa: E402


class FileManagerHelperTests(unittest.TestCase):
    def test_allowed_extensions(self) -> None:
        self.assertTrue(fm._is_allowed_extension("pdf"))
        self.assertTrue(fm._is_allowed_extension("docx"))
        self.assertFalse(fm._is_allowed_extension("exe"))

    def test_normalize_extension_blocks_traversal(self) -> None:
        self.assertIsNone(fm._normalize_extension("../../etc"))
        self.assertIsNone(fm._normalize_extension("txt/../../x"))
        self.assertEqual(fm._normalize_extension("txt"), "txt")

    def test_safe_download_filename_strips_control_chars(self) -> None:
        self.assertEqual(
            fm._safe_download_filename('evil"\r\nname.txt', "txt"),
            "evil___name.txt",
        )

    def test_type_category(self) -> None:
        self.assertEqual(fm._type_category("pdf"), "document")
        self.assertEqual(fm._type_category("xlsx"), "spreadsheet")
        self.assertEqual(fm._type_category("pptx"), "presentation")
        self.assertEqual(fm._type_category("png"), "image")

    def test_list_and_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_id = "a" * 32
            rec_dir = root / file_id
            rec_dir.mkdir()
            (rec_dir / "file.txt").write_text("hello", encoding="utf-8")
            meta = {
                "id": file_id,
                "filename": "notes.txt",
                "extension": "txt",
                "size": 5,
                "status": "ok",
                "uploaded_at": "2026-08-24T08:00:00+00:00",
                "mime": "text/plain",
            }
            (rec_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

            with patch.object(fm, "FILE_MANAGER_DIR", str(root)):
                records = fm._list_records()
                self.assertEqual(len(records), 1)
                self.assertTrue(fm._matches_query(records[0], "note"))
                self.assertFalse(fm._matches_query(records[0], "missing"))
                self.assertTrue(fm._matches_type(records[0], "document"))
                self.assertFalse(fm._matches_type(records[0], "image"))


if __name__ == "__main__":
    unittest.main()
