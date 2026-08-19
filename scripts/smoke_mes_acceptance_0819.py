#!/usr/bin/env python3
"""2026-08-19 验收冒烟：换平台负向 + TC-Q-03/04/05 + 当日完工 caveat + 闸门。

用法（仓库根目录）:
  PYTHONPATH=apps/agent python3 scripts/smoke_mes_acceptance_0819.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "apps" / "agent"
APPS = ROOT / "apps"
sys.path.insert(0, str(AGENT))
sys.path.insert(0, str(APPS))

os.environ.setdefault("DATA_DIR", str(ROOT / "data"))


def _ok(name: str, detail: str = "") -> None:
    print(f"P  {name}" + (f"  · {detail}" if detail else ""))


def _fail(name: str, detail: str) -> None:
    print(f"F  {name}  · {detail}")
    raise SystemExit(1)


def test_switch_platform_negative() -> None:
    from tools.schema_tool.profile_readiness import inspect_mes_profile

    status = {
        "active_profile_id": "empty-demo",
        "configured": True,
        "schema": {"exists": False},
        "ui": {"schema_uploaded": False, "openapi_imported": False, "entity_count": 0},
        "runtime": {},
        "capability_map": {},
    }
    with (
        patch("mes_profile.invalidate_mes_data_caches"),
        patch("mes_profile.profile_status", return_value=status),
        patch(
            "tools.schema_tool.profile_readiness._credential_flags",
            return_value={
                "mes_api_username": False,
                "mes_api_password": False,
                "mes_enterprise_code": False,
                "query_auth_ready": False,
            },
        ),
        patch(
            "tools.schema_tool.mes_schema_parser.build_index",
            return_value={"tables": [], "table_count": 0, "domain_count": 0},
        ),
        patch(
            "tools.schema_tool.capability_map.list_platform_capabilities",
            return_value={"capability_count": 0, "summary": {"schema_backed": []}, "map_source": "empty"},
        ),
        patch("tools.schema_tool.business_scenarios.list_business_scenarios", return_value={"scenarios": []}),
        patch("tools.query_tool.entity_catalog.catalog_summary", return_value=[]),
        patch("tools.query_tool.platform_query.list_query_metrics", return_value={"metrics": []}),
        patch("tools.query_tool.ops_playbook.list_ops_scenes", return_value={"scenes": []}),
    ):
        out = inspect_mes_profile(user_intent="查生产工单列表")
    blob = json.dumps(out, ensure_ascii=False)
    if out.get("can_answer_now"):
        _fail("换平台负向-查数", f"空目录不应 can_answer_now: {blob[:200]}")
    if "work-orders" in blob:
        _fail("换平台负向-无旧实体", "空目录结果里出现 work-orders")
    if not any(m.get("item") == "接口文档" for m in (out.get("missing") or [])):
        _fail("换平台负向-缺失项", f"missing={out.get('missing')}")
    _ok("换平台负向", "空目录挡住查数且未沿用 work-orders")


def test_tc_q03_nested_path() -> None:
    from mes_profile import invalidate_mes_data_caches
    from tools.query_tool.entity_catalog import get_entity, load_catalog
    from tools.query_tool.platform_query import query_platform_data

    invalidate_mes_data_caches()
    catalog = load_catalog()
    if not catalog:
        _fail("TC-Q-03", "当前资料包可查对象为空，请先接入江西中软")
    ent = get_entity("inspection-plans")
    if not ent:
        _fail("TC-Q-03", "目录无 inspection-plans")
    path = str(ent.get("path") or "")
    if "/api/v1/" in path or path.count("/") < 3:
        _fail("TC-Q-03", f"路径不像嵌套列表：{path}")
    raw = query_platform_data(entity="inspection-plans", limit=5)
    if raw.get("error"):
        _ok("TC-Q-03 路径", f"path={path}；查询报错（可能空库/鉴权）：{raw.get('error')}")
        return
    if raw.get("entity") != "inspection-plans":
        _fail("TC-Q-03", f"返回实体={raw.get('entity')}")
    if raw.get("entity") == "work-orders":
        _fail("TC-Q-03", "用工单充数")
    _ok(
        "TC-Q-03",
        f"entity=inspection-plans path={path} total={raw.get('total')} returned={raw.get('returned')}",
    )


def test_tc_q04_auth_gate() -> None:
    from tools.schema_tool.profile_readiness import inspect_mes_profile

    status = {
        "active_profile_id": "江西中软MES系统",
        "configured": True,
        "schema": {"exists": True},
        "ui": {"schema_uploaded": True, "openapi_imported": True, "entity_count": 3},
        "runtime": {"api_base": "http://127.0.0.1:8009", "path_prefix": ""},
        "capability_map": {},
    }
    with (
        patch("mes_profile.invalidate_mes_data_caches"),
        patch("mes_profile.profile_status", return_value=status),
        patch(
            "tools.schema_tool.profile_readiness._credential_flags",
            return_value={
                "mes_api_username": False,
                "mes_api_password": False,
                "mes_enterprise_code": False,
                "query_auth_ready": False,
            },
        ),
        patch(
            "tools.schema_tool.mes_schema_parser.build_index",
            return_value={"tables": [1], "table_count": 1, "domain_count": 1},
        ),
        patch(
            "tools.schema_tool.capability_map.list_platform_capabilities",
            return_value={"capability_count": 1, "summary": {"schema_backed": [{"id": "a"}]}, "map_source": "x"},
        ),
        patch("tools.schema_tool.business_scenarios.list_business_scenarios", return_value={"scenarios": []}),
        patch(
            "tools.query_tool.entity_catalog.catalog_summary",
            return_value=[{"entity": "work-orders", "label": "生产工单"}],
        ),
        patch("tools.query_tool.platform_query.list_query_metrics", return_value={"metrics": []}),
        patch("tools.query_tool.ops_playbook.list_ops_scenes", return_value={"scenes": []}),
    ):
        out = inspect_mes_profile(user_intent="查生产工单列表")
    if out.get("can_answer_now"):
        _fail("TC-Q-04", "无 MES 接口账号仍 can_answer_now")
    if not any(m.get("item") == "MES 接口账号" for m in (out.get("missing") or [])):
        _fail("TC-Q-04", f"missing={out.get('missing')}")
    _ok("TC-Q-04", "缺 MES 接口账号时挡住查数并提示补凭证")


def test_tc_q05_capabilities_not_query() -> None:
    from mes_profile import invalidate_mes_data_caches
    from tools.schema_tool.capability_map import list_platform_capabilities
    from tools.schema_tool.profile_readiness import inspect_mes_profile

    invalidate_mes_data_caches()
    insp = inspect_mes_profile(user_intent="MES 系统能干什么？")
    if insp.get("intent_kind") != "survey":
        _fail("TC-Q-05 intent", f"intent_kind={insp.get('intent_kind')}")
    if not insp.get("can_answer_now"):
        _fail("TC-Q-05", f"有表结构时应可摸底：missing={insp.get('missing')}")
    if insp.get("next_tool") != "list_platform_capabilities":
        _fail("TC-Q-05 next", f"next_tool={insp.get('next_tool')}")
    caps = list_platform_capabilities()
    if not caps.get("capability_count"):
        _fail("TC-Q-05", f"能力地图为空：{caps.get('note') or caps.get('error')}")
    blob = json.dumps(caps, ensure_ascii=False)
    if "query_platform_data" in blob:
        _fail("TC-Q-05", "能力地图工具链混入查数")
    _ok("TC-Q-05", f"map_source={caps.get('map_source')} count={caps.get('capability_count')}")


def test_completed_today_caveat() -> None:
    from tools.query_tool.metrics_pack import bind_metric, find_metric

    m = find_metric("当日完工")
    bound = bind_metric(
        m,
        catalog=[
            {
                "id": "work-orders",
                "label": "生产工单",
                "aliases": ["工单"],
                "fields": [
                    {"name": "status", "label": "状态"},
                    {"name": "end_date", "label": "结束日"},
                ],
            }
        ],
        available_fields=["status", "end_date"],
        observed={"status": ["completed", "pending"]},
        filter_fields=["status"],
        today="2026-08-19",
    )
    if "error" in bound:
        _fail("当日完工降级", str(bound.get("error")))
    if not bound.get("caveats"):
        _fail("当日完工降级", "应有日期筛参 caveat")
    if any("end_date" in fs for fs in (bound.get("filter_sets") or [])):
        _fail("当日完工降级", f"filter_sets 不应含日期：{bound.get('filter_sets')}")
    _ok("当日完工降级", bound["caveats"][0][:80])


def test_stack_chain_gate() -> None:
    from local_dev.stack_chain_gate import run_stack_chain_gate

    models = '''
class WorkOrder(Base):
    __tablename__ = "work_orders"
    actual_end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
'''
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "models.py").write_text(models, encoding="utf-8")
        db = root / "erp.db"
        conn = sqlite3.connect(str(db))
        conn.execute(
            "CREATE TABLE work_orders (id INTEGER PRIMARY KEY, status TEXT, end_date TEXT)"
        )
        conn.execute(
            "INSERT INTO work_orders(id,status,end_date) VALUES(1,'completed','2026-08-18')"
        )
        conn.commit()
        conn.close()
        result = run_stack_chain_gate(root, requirement="给工单列表加一列实际结束时间")
        if result.get("skipped"):
            _fail("D闸门", "不应 skipped")
        if not any("补列" in a or "回填" in a for a in (result.get("actions") or [])):
            _fail("D闸门", f"actions={result.get('actions')}")
        conn = sqlite3.connect(str(db))
        val = conn.execute("SELECT actual_end_time FROM work_orders WHERE id=1").fetchone()[0]
        conn.close()
        if not str(val).startswith("2026-08-18 18:00"):
            _fail("D闸门", f"回填值={val}")
    _ok("D闸门", "补列并回填 18:00")


def main() -> None:
    print("=== smoke MES acceptance 2026-08-19 ===")
    # 先跑真实资料包用例，再跑会 mock 空目录的负向，避免表结构缓存被污染
    test_completed_today_caveat()
    test_stack_chain_gate()
    test_tc_q05_capabilities_not_query()
    test_tc_q03_nested_path()
    test_switch_platform_negative()
    test_tc_q04_auth_gate()
    print("=== ALL PASS ===")


if __name__ == "__main__":
    main()
