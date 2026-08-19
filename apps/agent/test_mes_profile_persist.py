"""mes_profile_persist 单元测试。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "apps" / "agent"
if str(AGENT) not in sys.path:
    sys.path.insert(0, str(AGENT))

from mes_profile_persist import merge_entities, persist_openapi_text  # noqa: E402


class MergeEntitiesUnitTests(unittest.TestCase):
    def test_merge_by_path_keeps_old_id_no_duplicate(self) -> None:
        existing = [
            {
                "id": "legacy-stock",
                "label": "旧库存",
                "path": "/api/warehouse/inventory-stock",
                "aliases": ["旧库存"],
            }
        ]
        generated = [
            {
                "id": "warehouse-inventory-stock",
                "label": "库存明细",
                "path": "/api/warehouse/inventory-stock",
                "aliases": ["库存明细"],
            }
        ]
        merged, stats = merge_entities(existing, generated)
        ids = [e["id"] for e in merged]
        self.assertEqual(ids.count("legacy-stock"), 1)
        self.assertNotIn("warehouse-inventory-stock", ids)
        self.assertEqual(stats["updated"], ["legacy-stock"])
        self.assertEqual(stats["preserved"], [])


OPENAPI = """{
  "openapi": "3.0.0",
  "info": {"title": "MES", "version": "1.0"},
  "paths": {
    "/api/v1/work-orders": {"get": {"summary": "工单", "tags": ["工单"]}},
    "/api/v1/inventory": {"get": {"summary": "库存", "tags": ["库存"]}}
  }
}"""


class PersistOpenApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        import os

        os.environ["DATA_DIR"] = self._tmpdir.name
        from settings_store import invalidate_cache

        invalidate_cache()
        import importlib
        import mes_profile as mp

        importlib.reload(mp)

    def tearDown(self) -> None:
        import os

        os.environ.pop("DATA_DIR", None)
        self._tmpdir.cleanup()

    def test_merge_persist_keeps_old_entities(self) -> None:
        from mes_profile import ensure_profile_dir, ENTITIES_FILENAME

        root = ensure_profile_dir("测试平台")
        (root / ENTITIES_FILENAME).write_text(
            json.dumps(
                {
                    "entities": [
                        {
                            "id": "legacy",
                            "label": "遗留",
                            "path": "/api/v1/legacy",
                            "aliases": ["遗留"],
                        }
                    ],
                    "meta": {"source_url": "http://127.0.0.1:8009/docs"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        out = persist_openapi_text(
            "测试平台",
            OPENAPI,
            source_url="http://127.0.0.1:8009/openapi.json",
            merge_existing=True,
            reload_agent=False,
        )
        ids = out.get("entity_ids") or []
        self.assertIn("inventory", ids)
        self.assertIn("legacy", ids)
        merge = out.get("merge") or {}
        self.assertIn("legacy", merge.get("preserved") or [])


if __name__ == "__main__":
    unittest.main()
