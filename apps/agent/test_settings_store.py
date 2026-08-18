"""settings.json 密钥落盘加密。"""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

_AGENT = Path(__file__).resolve().parent
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))


class SettingsEncryptTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["DATA_DIR"] = self._tmpdir.name
        os.environ["WORKBUDDY_SETTINGS_KEY"] = "unit-test-settings-key"
        from settings_store import invalidate_cache

        invalidate_cache()

    def tearDown(self) -> None:
        from settings_store import invalidate_cache

        invalidate_cache()
        os.environ.pop("DATA_DIR", None)
        os.environ.pop("WORKBUDDY_SETTINGS_KEY", None)
        self._tmpdir.cleanup()

    def test_secret_encrypted_on_disk(self) -> None:
        from settings_store import resolve_setting, settings_path, update_settings

        update_settings({"MES_API_PASSWORD": "plain-secret", "MES_API_USERNAME": "mes"})
        raw = json.loads(settings_path().read_text(encoding="utf-8"))
        self.assertTrue(str(raw["MES_API_PASSWORD"]).startswith("enc:v1:"))
        self.assertNotIn("plain-secret", json.dumps(raw))
        self.assertEqual(raw["MES_API_USERNAME"], "mes")
        self.assertEqual(resolve_setting("MES_API_PASSWORD"), "plain-secret")
        mode = stat.S_IMODE(settings_path().stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_migrates_plaintext_secret(self) -> None:
        from settings_store import (
            invalidate_cache,
            resolve_setting,
            settings_path,
        )

        settings_path().parent.mkdir(parents=True, exist_ok=True)
        settings_path().write_text(
            json.dumps({"MES_API_PASSWORD": "legacy-pass"}, ensure_ascii=False),
            encoding="utf-8",
        )
        invalidate_cache()
        self.assertEqual(resolve_setting("MES_API_PASSWORD"), "legacy-pass")
        raw = json.loads(settings_path().read_text(encoding="utf-8"))
        self.assertTrue(str(raw["MES_API_PASSWORD"]).startswith("enc:v1:"))


if __name__ == "__main__":
    unittest.main()
