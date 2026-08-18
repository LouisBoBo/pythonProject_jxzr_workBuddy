#!/usr/bin/env python3
"""Smoke：可查对象别名解析（依赖当前 MES 资料包，无资料包则跳过）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "apps" / "agent"
for p in (str(AGENT), str(ROOT / "apps"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _fail(name: str, msg: str) -> None:
    print(f"FAIL {name}: {msg}")
    sys.exit(1)


def main() -> None:
    from tools.query_tool.entity_catalog import (
        invalidate_catalog,
        list_entity_ids,
        load_catalog,
        resolve_entity_id,
    )

    invalidate_catalog()
    cats = load_catalog()
    ids = set(list_entity_ids())
    if not cats:
        print("SKIP: 未配置 MES 资料包可查对象（请先在系统配置上传接口文档）")
        return

    print(f"OK catalog entities={sorted(ids)}")
    for e in cats:
        eid = e["id"]
        label = e.get("label") or eid
        if resolve_entity_id(eid) != eid:
            _fail("id", f"resolve({eid!r}) != {eid}")
        if resolve_entity_id(label) != eid:
            _fail("label", f"resolve({label!r}) != {eid}")
        for a in (e.get("aliases") or [])[:5]:
            if resolve_entity_id(str(a)) != eid:
                _fail("alias", f"resolve({a!r}) != {eid}")
    print("OK smoke_entity_phrases")


if __name__ == "__main__":
    main()
