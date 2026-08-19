"""MES 资料包写码后自动同步单元测试。"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "apps" / "agent"
if str(AGENT) not in sys.path:
    sys.path.insert(0, str(AGENT))
if str(ROOT / "apps") not in sys.path:
    sys.path.insert(0, str(ROOT / "apps"))

from local_dev.mes_profile_sync import (  # noqa: E402
    collect_tables_from_files,
    merge_schema_markdown,
    parse_sqlalchemy_tables,
    synced_touches_api,
    synced_touches_schema,
)
from mes_profile_persist import merge_entities  # noqa: E402

SAMPLE_OPENAPI = """{
  "openapi": "3.0.0",
  "info": {"title": "MES", "version": "1.0"},
  "paths": {
    "/api/v1/work-orders": {"get": {"summary": "工单列表", "tags": ["工单"]}},
    "/api/v1/inventory": {"get": {"summary": "库存列表", "tags": ["库存"]}}
  }
}"""

INVENTORY_MODEL = '''
from sqlalchemy.orm import Mapped, mapped_column

class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str]
    quantity: Mapped[int]
'''


class MergeEntitiesTests(unittest.TestCase):
    def test_merge_preserves_old_and_adds_new(self) -> None:
        existing = [
            {
                "id": "work-orders",
                "label": "工单",
                "aliases": ["工单", "生产工单"],
                "path": "/api/v1/work-orders",
                "ops": ["query"],
            }
        ]
        generated = [
            {
                "id": "work-orders",
                "label": "工单列表",
                "aliases": ["工单列表"],
                "path": "/api/v1/work-orders",
                "ops": ["query", "export"],
            },
            {
                "id": "inventory",
                "label": "库存列表",
                "aliases": ["库存"],
                "path": "/api/v1/inventory",
                "ops": ["query"],
            },
        ]
        merged, stats = merge_entities(existing, generated)
        ids = {e["id"] for e in merged}
        self.assertEqual(ids, {"work-orders", "inventory"})
        wo = next(e for e in merged if e["id"] == "work-orders")
        self.assertIn("生产工单", wo["aliases"])
        self.assertIn("工单列表", wo["aliases"])
        self.assertEqual(stats["added"], ["inventory"])
        self.assertEqual(stats["updated"], ["work-orders"])


class SyncDetectionTests(unittest.TestCase):
    def test_api_detection(self) -> None:
        self.assertTrue(synced_touches_api(["backend/app/routes/inventory.py"]))
        self.assertFalse(synced_touches_api(["frontend/src/App.vue"]))

    def test_schema_detection(self) -> None:
        self.assertTrue(synced_touches_schema(["backend/app/models/inventory.py"]))
        self.assertFalse(synced_touches_schema(["backend/app/routes/inventory.py"]))


class SchemaMergeTests(unittest.TestCase):
    def test_parse_and_merge_new_table(self) -> None:
        tables = parse_sqlalchemy_tables(INVENTORY_MODEL)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["table"], "inventory_items")
        merged, stats = merge_schema_markdown("", tables)
        self.assertIn("inventory_items", merged)
        self.assertEqual(stats["added"], ["inventory_items"])

    def test_collect_rejects_path_outside_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = Path(tmp).parent / "outside_model.py"
            outside.write_text(
                'class X:\n    __tablename__ = "evil"\n    id: Mapped[int]\n',
                encoding="utf-8",
            )
            rel = os.path.relpath(outside, root)
            tables = collect_tables_from_files(root, [rel])
            self.assertEqual(tables, [])

    def test_collect_from_synced_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_path = root / "backend" / "app" / "models" / "inventory.py"
            model_path.parent.mkdir(parents=True)
            model_path.write_text(INVENTORY_MODEL, encoding="utf-8")
            tables = collect_tables_from_files(
                root, ["backend/app/models/inventory.py"]
            )
            self.assertEqual(len(tables), 1)


if __name__ == "__main__":
    unittest.main()
