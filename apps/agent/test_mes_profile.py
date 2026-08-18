"""MES 资料包：未配置时不得回退仓库内置演示；配置后才覆盖。"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
AGENT = Path(__file__).resolve().parent  # apps/agent
APPS = ROOT / "apps"
if str(AGENT) not in sys.path:
    sys.path.insert(0, str(AGENT))
if str(APPS) not in sys.path:
    sys.path.insert(0, str(APPS))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class MesProfileResolveTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.data = Path(self._tmpdir.name)
        os.environ["DATA_DIR"] = str(self.data)
        os.environ.pop("MES_PROFILE_ID", None)
        os.environ.pop("MES_SCHEMA_DOC", None)
        from settings_store import invalidate_cache, settings_path

        invalidate_cache()
        sp = settings_path()
        if sp.is_file():
            sp.unlink()

        import importlib

        import mes_profile as mp

        importlib.reload(mp)
        self.mp = mp
        self.mp.invalidate_mes_data_caches()

    def tearDown(self) -> None:
        os.environ.pop("DATA_DIR", None)
        os.environ.pop("MES_PROFILE_ID", None)
        os.environ.pop("MES_SCHEMA_DOC", None)
        from settings_store import invalidate_cache

        invalidate_cache()
        self._tmpdir.cleanup()

    def test_none_when_no_profile(self) -> None:
        schema, ssrc = self.mp.resolve_schema_doc()
        entities, esrc = self.mp.resolve_entities_path()
        self.assertIsNone(schema)
        self.assertEqual(ssrc, "none")
        self.assertIsNone(entities)
        self.assertEqual(esrc, "none")

        from tools.query_tool.entity_catalog import invalidate_catalog, load_catalog

        invalidate_catalog()
        self.assertEqual(load_catalog(), [])

    def test_profile_schema_overrides(self) -> None:
        from settings_store import update_settings

        pid = "demo-customer"
        root = self.mp.ensure_profile_dir(pid)
        fake = root / self.mp.SCHEMA_FILENAME
        fake.write_text("# fake schema\n\n### 1.1 测试\n", encoding="utf-8")
        update_settings({"MES_PROFILE_ID": pid})
        self.mp.invalidate_mes_data_caches()

        schema, ssrc = self.mp.resolve_schema_doc()
        self.assertEqual(ssrc, "profile")
        self.assertEqual(schema, fake.resolve())

        entities, esrc = self.mp.resolve_entities_path()
        self.assertIsNone(entities)
        self.assertEqual(esrc, "none")

    def test_profile_entities_override(self) -> None:
        from settings_store import update_settings

        pid = "ent-only"
        root = self.mp.ensure_profile_dir(pid)
        payload = {
            "entities": [
                {
                    "id": "devices",
                    "label": "设备",
                    "path": "devices",
                    "aliases": ["设备"],
                    "ops": ["query"],
                    "fields": [],
                }
            ]
        }
        (root / self.mp.ENTITIES_FILENAME).write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        update_settings({"MES_PROFILE_ID": pid})
        self.mp.invalidate_mes_data_caches()

        path, src = self.mp.resolve_entities_path()
        self.assertEqual(src, "profile")
        self.assertEqual(path, (root / self.mp.ENTITIES_FILENAME).resolve())

        from tools.query_tool.entity_catalog import invalidate_catalog, load_catalog

        invalidate_catalog()
        cats = load_catalog()
        self.assertEqual(len(cats), 1)
        self.assertEqual(cats[0]["id"], "devices")

    def test_clear_profile_back_to_none(self) -> None:
        from settings_store import update_settings

        pid = "tmp-clear"
        root = self.mp.ensure_profile_dir(pid)
        (root / self.mp.SCHEMA_FILENAME).write_text("# x\n", encoding="utf-8")
        update_settings({"MES_PROFILE_ID": pid})
        schema, src = self.mp.resolve_schema_doc()
        self.assertEqual(src, "profile")

        update_settings({"MES_PROFILE_ID": ""})
        self.mp.invalidate_mes_data_caches()
        schema2, src2 = self.mp.resolve_schema_doc()
        self.assertIsNone(schema2)
        self.assertEqual(src2, "none")

    def test_sanitize_rejects_path_traversal(self) -> None:
        self.assertEqual(self.mp.sanitize_profile_id("../etc"), "")
        self.assertEqual(self.mp.sanitize_profile_id("a/b"), "")
        self.assertEqual(self.mp.sanitize_profile_id("ok_id-1"), "ok_id-1")
        self.assertEqual(self.mp.sanitize_profile_id("中软演示"), "中软演示")

    def test_profile_status_ui_flags(self) -> None:
        from settings_store import update_settings

        st0 = self.mp.profile_status()
        self.assertFalse(st0["ui"]["schema_uploaded"])
        self.assertFalse(st0["ui"]["openapi_imported"])
        self.assertEqual(st0["ui"]["entity_count"], 0)
        self.assertFalse(st0["configured"])

        pid = "ui-status"
        root = self.mp.ensure_profile_dir(pid)
        (root / self.mp.SCHEMA_FILENAME).write_text("# schema\n", encoding="utf-8")
        (root / self.mp.OPENAPI_FILENAME).write_text('{"openapi":"3.0.0"}', encoding="utf-8")
        (root / self.mp.ENTITIES_FILENAME).write_text(
            json.dumps(
                {
                    "entities": [
                        {
                            "id": "a",
                            "label": "A",
                            "path": "a",
                            "aliases": [],
                            "ops": ["query"],
                            "fields": [],
                        }
                    ],
                    "meta": {"source_url": "http://127.0.0.1:8009/openapi.json"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        update_settings({"MES_PROFILE_ID": pid})
        self.mp.invalidate_mes_data_caches()

        st = self.mp.profile_status()
        self.assertTrue(st["ui"]["schema_uploaded"])
        self.assertTrue(st["ui"]["openapi_imported"])
        self.assertEqual(st["ui"]["entity_count"], 1)
        self.assertEqual(st["openapi"]["source_url"], "http://127.0.0.1:8009/openapi.json")

    def test_login_paths_and_prefix_from_entities_meta(self) -> None:
        from settings_store import update_settings

        pid = "other-erp"
        root = self.mp.ensure_profile_dir(pid)
        payload = {
            "entities": [
                {
                    "id": "mo-list",
                    "label": "工单",
                    "path": "/erp/mo/list",
                    "aliases": ["工单"],
                    "ops": ["query"],
                    "fields": [],
                    "paging": {"page": "pageNo", "page_size": "pageSize"},
                }
            ],
            "meta": {
                "api_base": "http://10.0.0.8:8080",
                "login_paths": ["/erp/auth/login"],
                "path_prefix": "/erp",
            },
        }
        (root / self.mp.ENTITIES_FILENAME).write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        update_settings({"MES_PROFILE_ID": pid})
        self.mp.invalidate_mes_data_caches()

        self.assertEqual(self.mp.resolve_mes_api_base(), "http://10.0.0.8:8080")
        self.assertEqual(self.mp.resolve_login_paths(), ["/erp/auth/login"])
        self.assertEqual(self.mp.resolve_path_prefix(), "/erp")
        st = self.mp.profile_status()
        self.assertEqual(st["runtime"]["api_base"], "http://10.0.0.8:8080")
        self.assertEqual(st["runtime"]["login_paths"], ["/erp/auth/login"])

    def test_api_base_must_match_source_host(self) -> None:
        from settings_store import update_settings

        pid = "hijack-base"
        root = self.mp.ensure_profile_dir(pid)
        payload = {
            "entities": [
                {
                    "id": "wo",
                    "label": "工单",
                    "path": "/api/work-orders",
                    "aliases": [],
                    "ops": ["query"],
                    "fields": [],
                }
            ],
            "meta": {
                "api_base": "http://169.254.169.254",
                "source_url": "http://127.0.0.1:8009/openapi.json",
                "login_paths": ["/api/auth/login"],
            },
        }
        (root / self.mp.ENTITIES_FILENAME).write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        update_settings({"MES_PROFILE_ID": pid})
        self.mp.invalidate_mes_data_caches()
        self.assertEqual(self.mp.resolve_mes_api_base(), "http://127.0.0.1:8009")


if __name__ == "__main__":
    unittest.main()
