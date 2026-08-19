"""实体别名：库存列表应优先明细接口而非看板汇总。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
AGENT = ROOT / "apps" / "agent"
if str(AGENT) not in sys.path:
    sys.path.insert(0, str(AGENT))

ENTITIES = {
    "entities": [
        {
            "id": "warehouse-dashboard",
            "label": "仓储看板数据",
            "aliases": ["仓储看板数据", "warehouse-dashboard"],
            "path": "/api/warehouse/dashboard",
            "ops": ["query"],
            "list_keys": ["kpi_cards"],
        },
        {
            "id": "warehouse-inventory-stock",
            "label": "库存明细",
            "aliases": [
                "库存明细",
                "inventory-stock",
                "stock",
                "inventory",
                "库存",
                "库存列表",
            ],
            "path": "/api/warehouse/inventory-stock",
            "ops": ["query", "export"],
            "paging": {"page": "page", "page_size": "page_size"},
            "list_keys": ["items"],
        },
    ],
    "meta": {"api_base": "http://127.0.0.1:8009"},
}


class EntityResolveInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        import os

        prof = Path(self._tmpdir.name) / "mes_profiles" / "测试"
        prof.mkdir(parents=True)
        (prof / "entities.json").write_text(
            json.dumps(ENTITIES, ensure_ascii=False), encoding="utf-8"
        )
        os.environ["DATA_DIR"] = self._tmpdir.name
        os.environ["MES_PROFILE_ID"] = "测试"
        from settings_store import invalidate_cache

        invalidate_cache()
        import importlib
        import mes_profile as mp
        import tools.query_tool.entity_catalog as cat

        importlib.reload(mp)
        importlib.reload(cat)
        cat.invalidate_catalog()
        self.cat = cat

    def tearDown(self) -> None:
        import os

        os.environ.pop("DATA_DIR", None)
        os.environ.pop("MES_PROFILE_ID", None)
        self._tmpdir.cleanup()

    def test_inventory_list_prefers_detail_not_dashboard(self) -> None:
        eid = self.cat.resolve_entity_id("查询库存列表")
        self.assertEqual(eid, "warehouse-inventory-stock")

    def test_inventory_keyword(self) -> None:
        eid = self.cat.resolve_entity_id("库存")
        self.assertEqual(eid, "warehouse-inventory-stock")


if __name__ == "__main__":
    unittest.main()
