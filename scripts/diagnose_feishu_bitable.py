#!/usr/bin/env python3
"""诊断飞书写表：解析 wiki token、列字段、试写 1 行。用法：
  PYTHONPATH=apps:apps/agent:apps/automations:. python3 scripts/diagnose_feishu_bitable.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MES_DATA_DIR", str(ROOT / "data"))
sys.path[:0] = [str(ROOT / "apps"), str(ROOT / "apps" / "agent"), str(ROOT / "apps" / "automations")]

from automations.bitable_writer import map_rows_to_records  # noqa: E402
from automations.feishu_bitable import (  # noqa: E402
    batch_create_records,
    get_tenant_access_token,
    list_table_fields,
    resolve_bitable_app_token,
)
from automations.store import list_automations  # noqa: E402


def main() -> int:
    autos = list_automations(ROOT / "data")
    target = None
    for a in autos:
        bs = a.get("bitable_sync") if isinstance(a.get("bitable_sync"), dict) else None
        if bs and bs.get("enabled"):
            target = a
            break
    if not target:
        print("未找到已开启 bitable_sync 的自动化任务")
        return 1
    bs = target["bitable_sync"]
    app_token = str(bs.get("app_token") or "")
    table_id = str(bs.get("table_id") or "")
    print(f"automation={target.get('id')} name={target.get('name')}")
    print(f"app_token={app_token}")
    print(f"table_id={table_id}")

    tok = get_tenant_access_token(force=True)
    print("tenant_token:", "ok" if tok.get("ok") else tok)
    if not tok.get("ok"):
        return 2
    access = str(tok.get("tenant_access_token") or "")

    resolved = resolve_bitable_app_token(app_token, access_token=access)
    print("resolve_app_token:", json.dumps(resolved, ensure_ascii=False)[:400])
    if not resolved.get("ok"):
        return 3
    real_token = str(resolved.get("app_token") or app_token)

    listed = list_table_fields(app_token=real_token, table_id=table_id, access_token=access)
    print("list_fields:", json.dumps(listed, ensure_ascii=False)[:1200])
    if not listed.get("ok"):
        return 4

    rows = [
        {
            "date": "2026-08-27",
            "wip_count": 28,
            "open_count": 46,
            "urgent_open": 23,
            "utilization_avg": 83.5,
            "output_total": 0,
            "yield_min": 97.87,
            "yield_max": 97.89,
            "note": "诊断试写",
        }
    ]
    records = map_rows_to_records(rows, bs.get("field_map") if isinstance(bs.get("field_map"), dict) else None)
    print("mapped_records:", json.dumps(records, ensure_ascii=False)[:500])
    result = batch_create_records(app_token=real_token, table_id=table_id, records=records)
    print("write_result:", json.dumps(result, ensure_ascii=False)[:800])
    return 0 if result.get("ok") else 5


if __name__ == "__main__":
    raise SystemExit(main())
