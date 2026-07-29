#!/usr/bin/env python3
"""无 LLM：实体别名解析 + 实体守卫规则冒烟。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "apps" / "agent"
sys.path.insert(0, str(AGENT))

from tools.query_tool.entity_catalog import load_catalog, resolve_entity_id  # noqa: E402


def _fail(name: str, detail: str) -> None:
    print(f"FAIL {name}: {detail}")
    raise SystemExit(1)


def _ok(name: str) -> None:
    print(f"OK   {name}")


def test_resolve() -> None:
    load_catalog.cache_clear()
    cases = [
        ("工单", "work-orders"),
        ("生产工单", "work-orders"),
        ("派工单", "work-orders"),
        ("异常工单", "work-orders"),
        ("WO", "work-orders"),
        ("work orders", "work-orders"),
        ("生产计划", "production-plans"),
        ("排产计划", "production-plans"),
        ("排程计划", "production-plans"),
        ("排产", "production-plans"),
        ("排程", "production-plans"),
        ("主生产计划", "production-plans"),
        ("production-plans", "production-plans"),
        ("查一下排程计划有哪些", "production-plans"),
        ("看看派工单", "work-orders"),
    ]
    for phrase, expect in cases:
        got = resolve_entity_id(phrase)
        if got != expect:
            _fail("resolve", f"{phrase!r} → {got!r}, expect {expect!r}")
    _ok(f"resolve ({len(cases)} phrases)")


def test_guard_rules() -> None:
    from middleware.entity_guard_rules import guard_mismatch_tip

    tip = guard_mismatch_tip("work-orders", "查一下排程计划")
    if not tip:
        _fail("guard_plan", "expected tip when plan→work-orders")
    tip = guard_mismatch_tip("production-plans", "查一下派工单")
    if not tip:
        _fail("guard_wo", "expected tip when wo→production-plans")
    if guard_mismatch_tip("work-orders", "查工单") is not None:
        _fail("guard_ok_wo", "should not tip matching entity")
    if guard_mismatch_tip("work-orders", "工单和排产对比一下") is not None:
        _fail("guard_both", "should not tip when both hints present")
    _ok("entity_guard bidirectional")


def test_catalog_has_core() -> None:
    load_catalog.cache_clear()
    ids = {e["id"] for e in load_catalog()}
    if ids != {"work-orders", "production-plans"}:
        _fail("catalog_ids", str(ids))
    _ok("catalog core entities")


def main() -> None:
    test_catalog_has_core()
    test_resolve()
    test_guard_rules()
    print("SMOKE_OK entity-phrases")


if __name__ == "__main__":
    main()
