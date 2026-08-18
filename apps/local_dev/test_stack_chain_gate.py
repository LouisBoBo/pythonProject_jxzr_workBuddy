"""数据链路闸门：补列 + 按状态回填。"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from local_dev.stack_chain_gate import (
    _safe_sql_ident,
    find_sqlite_dbs,
    format_gate_summary,
    parse_model_datetime_fields,
    repair_sqlite_datetime_chain,
    run_stack_chain_gate,
)


_MODELS = '''
class WorkOrder(Base):
    __tablename__ = "work_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    actual_start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
'''


class StackChainGateTests(unittest.TestCase):
    def test_parse_model_fields(self) -> None:
        fields = parse_model_datetime_fields(_MODELS)
        self.assertEqual(fields["work_orders"], ["actual_start_time", "actual_end_time"])

    def test_backfills_completed_end_time(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "erp.db"
            conn = sqlite3.connect(str(db))
            conn.execute(
                """
                CREATE TABLE work_orders (
                    id INTEGER PRIMARY KEY,
                    status TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    actual_start_time DATETIME,
                    actual_end_time DATETIME
                )
                """
            )
            conn.executemany(
                "INSERT INTO work_orders(id,status,start_date,end_date) VALUES(?,?,?,?)",
                [
                    (1, "completed", "2026-08-01", "2026-08-02"),
                    (2, "pending", "2026-08-03", "2026-08-04"),
                    (3, "in_progress", "2026-08-05", "2026-08-06"),
                ],
            )
            conn.commit()
            conn.close()

            result = repair_sqlite_datetime_chain(db)
            self.assertTrue(any("actual_end_time" in a for a in result["actions"]))

            conn = sqlite3.connect(str(db))
            rows = {
                r[0]: r[1:]
                for r in conn.execute(
                    "SELECT id, actual_start_time, actual_end_time FROM work_orders"
                )
            }
            conn.close()
            self.assertTrue(str(rows[1][0]).startswith("2026-08-01 08:00"))
            self.assertTrue(str(rows[1][1]).startswith("2026-08-02 18:00"))
            self.assertIsNone(rows[2][0])
            self.assertIsNone(rows[2][1])
            self.assertTrue(str(rows[3][0]).startswith("2026-08-05 08:00"))
            self.assertIsNone(rows[3][1])

    def test_adds_missing_column_from_model(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "models.py").write_text(_MODELS, encoding="utf-8")
            db = root / "erp.db"
            conn = sqlite3.connect(str(db))
            conn.execute(
                """
                CREATE TABLE work_orders (
                    id INTEGER PRIMARY KEY,
                    status TEXT,
                    start_date TEXT,
                    end_date TEXT
                )
                """
            )
            conn.execute(
                "INSERT INTO work_orders(id,status,start_date,end_date) "
                "VALUES(1,'closed','2026-07-01','2026-07-02')"
            )
            conn.commit()
            conn.close()

            result = run_stack_chain_gate(root, requirement="给工单列表加一列实际结束时间")
            self.assertFalse(result["skipped"])
            self.assertTrue(any("补列" in a for a in result["actions"]))
            conn = sqlite3.connect(str(db))
            end = conn.execute(
                "SELECT actual_end_time FROM work_orders WHERE id=1"
            ).fetchone()[0]
            conn.close()
            self.assertTrue(str(end).startswith("2026-07-02 18:00"))

    def test_css_layout_skips(self) -> None:
        result = run_stack_chain_gate(
            Path("/tmp"),
            requirement="【任务档位：css_layout】去掉横向滚动",
        )
        self.assertTrue(result["skipped"])

    def test_does_not_overwrite_existing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "erp.db"
            conn = sqlite3.connect(str(db))
            conn.execute(
                """
                CREATE TABLE work_orders (
                    id INTEGER PRIMARY KEY,
                    status TEXT,
                    end_date TEXT,
                    actual_end_time DATETIME
                )
                """
            )
            conn.execute(
                "INSERT INTO work_orders VALUES(1,'completed','2026-08-02','2026-08-02 12:34:00')"
            )
            conn.commit()
            conn.close()
            repair_sqlite_datetime_chain(db)
            conn = sqlite3.connect(str(db))
            val = conn.execute("SELECT actual_end_time FROM work_orders").fetchone()[0]
            conn.close()
            self.assertEqual(val, "2026-08-02 12:34:00")

    def test_format_summary(self) -> None:
        text = format_gate_summary({"skipped": False, "actions": ["erp.db:work_orders 回填 actual_end_time 3 行"]})
        self.assertIn("3 行", text)
        self.assertEqual(format_gate_summary({"skipped": True}), "")

    def test_rejects_unsafe_ident(self) -> None:
        self.assertIsNone(_safe_sql_ident('work; DROP TABLE x'))
        self.assertIsNone(_safe_sql_ident('x"y'))
        self.assertIsNone(_safe_sql_ident("odd-name"))
        self.assertEqual(_safe_sql_ident("work_orders"), "work_orders")

    def test_skips_unsafe_table_name(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "erp.db"
            conn = sqlite3.connect(str(db))
            conn.execute(
                'CREATE TABLE "odd-name" ('
                "id INTEGER, status TEXT, end_date TEXT, actual_end_time DATETIME)"
            )
            conn.execute(
                'INSERT INTO "odd-name" VALUES (1, "completed", "2026-08-02", NULL)'
            )
            conn.commit()
            conn.close()
            result = repair_sqlite_datetime_chain(db)
            self.assertEqual(result["actions"], [])
            conn = sqlite3.connect(str(db))
            val = conn.execute('SELECT actual_end_time FROM "odd-name"').fetchone()[0]
            conn.close()
            self.assertIsNone(val)

    def test_skips_symlink_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "proj"
            outside = Path(td) / "secret.db"
            root.mkdir()
            conn = sqlite3.connect(str(outside))
            conn.execute(
                "CREATE TABLE work_orders ("
                "id INTEGER, status TEXT, end_date TEXT, actual_end_time DATETIME)"
            )
            conn.execute(
                "INSERT INTO work_orders VALUES(1,'completed','2026-08-02', NULL)"
            )
            conn.commit()
            conn.close()
            link = root / "erp.db"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlink not allowed")
            dbs = find_sqlite_dbs(root)
            self.assertFalse(any(p.resolve() == outside.resolve() for p in dbs))
            run_stack_chain_gate(root, requirement="给工单列表加一列实际结束时间")
            conn = sqlite3.connect(str(outside))
            val = conn.execute("SELECT actual_end_time FROM work_orders").fetchone()[0]
            conn.close()
            self.assertIsNone(val)


if __name__ == "__main__":
    unittest.main()
