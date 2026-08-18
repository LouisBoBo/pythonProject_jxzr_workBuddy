"""表结构 Markdown 解析：支持中软字典与 ERP `table` — 标题两种格式。"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # repo root
AGENT = Path(__file__).resolve().parents[2]  # apps/agent
for p in (str(AGENT), str(ROOT / "apps"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)


ERP_SAMPLE = """# ERP 表结构

### 4.1 系统与权限

#### `users` — 系统用户

| 字段名 | 类型 | 约束 | 默认值 | 说明 |
|--------|------|------|--------|------|
| id | INTEGER | PK, NN | — | 主键 |
| username | VARCHAR(50) | UK, NN | — | 登录名 |

### 4.2 生产执行

#### `work_orders` — 生产工单

| 字段名 | 类型 | 约束 | 默认值 | 说明 |
|--------|------|------|--------|------|
| id | INTEGER | PK, NN | — | 主键 |
| order_no | VARCHAR(50) | UK, NN | — | 工单号 |
"""

ZR_SAMPLE = """### 1.1 生产管理

#### 1 工单主表 (TBL_MO)

- **业务含义**：生产工单
- **所属数据库**：MES

| 字段名 | 类型 | 可空 | 默认值 | 说明 |
|--------|------|------|--------|------|
| MO_ID | VARCHAR | N | | 工单ID |
"""


class SchemaParserFormatTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.doc = Path(self._tmpdir.name) / "schema.md"
        import os

        os.environ["DATA_DIR"] = self._tmpdir.name
        os.environ["MES_SCHEMA_DOC"] = str(self.doc)
        from settings_store import invalidate_cache

        invalidate_cache()
        import importlib
        import mes_profile as mp
        import tools.schema_tool.mes_schema_parser as parser

        importlib.reload(mp)
        importlib.reload(parser)
        self.parser = parser
        self.parser.invalidate_schema_caches()

    def tearDown(self) -> None:
        import os

        os.environ.pop("MES_SCHEMA_DOC", None)
        os.environ.pop("DATA_DIR", None)
        self._tmpdir.cleanup()

    def test_erp_backtick_heads(self) -> None:
        self.doc.write_text(ERP_SAMPLE, encoding="utf-8")
        self.parser.invalidate_schema_caches()
        idx = self.parser.build_index(force=True)
        self.assertEqual(idx["table_count"], 2)
        self.assertEqual(idx["domain_count"], 2)
        names = {t["table"] for t in idx["tables"]}
        self.assertEqual(names, {"users", "work_orders"})
        wo = self.parser.find_table_full("work_orders")
        assert wo is not None
        self.assertEqual(wo["label"], "生产工单")
        self.assertGreaterEqual(wo["field_count"], 2)
        self.assertEqual(wo["domain"], "生产执行")

    def test_zhongruan_heads(self) -> None:
        self.doc.write_text(ZR_SAMPLE, encoding="utf-8")
        self.parser.invalidate_schema_caches()
        idx = self.parser.build_index(force=True)
        self.assertEqual(idx["table_count"], 1)
        self.assertEqual(idx["tables"][0]["table"], "TBL_MO")


if __name__ == "__main__":
    unittest.main()
