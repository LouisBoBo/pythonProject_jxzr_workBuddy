#!/usr/bin/env python3
"""API 健康分析无 LLM 冒烟（能力 A 探活抽样 + 能力 B 日志分析）。

用法（仓库根目录）:
  python3 scripts/smoke_api_health.py
  make smoke-api-health

环境:
  - 能力 B：仅需样例文件，不依赖网络
  - 能力 A：需 8081 OpenAPI + 8001 沙箱；不可用则 SKIP（不算失败）
  - 设置 SMOKE_REQUIRE_PROBE=1 时，探活不可用则失败

退出码: 0 通过；1 失败
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "apps" / "agent"
sys.path.insert(0, str(AGENT))

os.chdir(AGENT)
# 保证 DATA_DIR 指向仓库 data
if "DATA_DIR" not in os.environ:
    os.environ["DATA_DIR"] = str(ROOT / "data")


def _ok(name: str, detail: str = "") -> None:
    print(f"PASS  {name}" + (f"  {detail}" if detail else ""))


def _fail(name: str, detail: str) -> None:
    print(f"FAIL  {name}  {detail}")
    raise AssertionError(f"{name}: {detail}")


def _http_ok(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= int(resp.status) < 300
    except Exception:
        return False


def smoke_middleware() -> None:
    from middleware import build_custom_middleware

    names = [m.name for m in build_custom_middleware()]
    if "MesAccessLogRouteMiddleware" not in names:
        _fail("middleware", f"missing MesAccessLogRouteMiddleware in {names}")
    _ok("middleware", str(names))


def smoke_log_analysis() -> None:
    from config import Config
    from tools.api_log_tool.api_health import (
        analyze_api_errors_from_logs,
        import_external_api_logs,
    )

    samples = Path(Config.DATA_DIR) / "samples"
    nginx = samples / "api_access_sample.nginx.log"
    jsonl = samples / "api_access_sample.jsonl"
    if not nginx.is_file() or not jsonl.is_file():
        _fail("samples", f"missing {nginx} or {jsonl}")

    # 两轮导入：不替换，验证 run_id 隔离
    a = import_external_api_logs(str(nginx), replace_previous=True)
    if a.get("imported") != 3 or not a.get("run_id"):
        _fail("import_nginx", str(a))
    rid_a = a["run_id"]

    b = import_external_api_logs(str(jsonl), replace_previous=False)
    if b.get("imported") != 7 or not b.get("run_id"):
        _fail("import_jsonl", str(b))
    rid_b = b["run_id"]
    if rid_a == rid_b:
        _fail("run_id_unique", f"same run_id {rid_a}")

    latest = analyze_api_errors_from_logs(source_filter="import", run_id="latest")
    if latest.get("call_count") != 7 or latest.get("endpoint_count") != 4:
        _fail("analyze_latest_counts", str({k: latest.get(k) for k in ("call_count", "endpoint_count", "run_id")}))
    if latest.get("run_id") != rid_b:
        _fail("analyze_latest_run", f"want {rid_b} got {latest.get('run_id')}")

    md = latest.get("report_markdown") or ""
    if "62" in md or "swagger" in md.lower() or "对照目录" in md:
        _fail("no_doc_bleed", "log report must not contain catalog/docs numbers")
    # 错误排行段不得出现 inventory（属于 nginx 轮）
    rank = md.split("### 错误接口排行")[1].split("###")[0] if "### 错误接口排行" in md else md
    if "inventory" in rank:
        _fail("no_inventory_in_latest", "latest jsonl report polluted by nginx inventory")

    errs = {(e.get("method"), e.get("path_key")) for e in (latest.get("error_apis") or [])}
    oks = {(e.get("method"), e.get("path_key")) for e in (latest.get("healthy_apis") or [])}
    if ("DELETE", "/api/suppliers/delete/{id}") not in errs:
        _fail("error_suppliers", str(errs))
    if ("GET", "/api/orders/details/{id}") not in errs:
        _fail("error_orders", str(errs))
    if ("POST", "/api/parts/create") not in oks or ("GET", "/api/customers/get/{id}") not in oks:
        _fail("healthy_apis", str(oks))

    old = analyze_api_errors_from_logs(source_filter="import", run_id=rid_a)
    if old.get("call_count") != 3:
        _fail("analyze_old_run", f"want 3 got {old.get('call_count')}")
    old_keys = " ".join(
        e.get("path_key") or ""
        for e in (old.get("error_apis") or []) + (old.get("healthy_apis") or [])
    )
    if "inventory" not in old_keys:
        _fail("old_run_inventory", old_keys)

    # 默认替换导入：只剩 jsonl
    c = import_external_api_logs(str(jsonl), replace_previous=True)
    alone = analyze_api_errors_from_logs(source_filter="import", run_id="latest")
    if alone.get("call_count") != 7 or alone.get("run_id") != c.get("run_id"):
        _fail(
            "replace_previous",
            f"calls={alone.get('call_count')} run={alone.get('run_id')} expect={c.get('run_id')}",
        )

    _ok(
        "log_analysis",
        f"runs {rid_a} -> {rid_b}; latest 7/4 err={len(errs)} ok={len(oks)}",
    )


def smoke_probe() -> str:
    """返回 PASS / SKIP / 抛错失败。"""
    require = os.getenv("SMOKE_REQUIRE_PROBE", "").strip() in ("1", "true", "yes")
    docs = os.getenv("SMOKE_DOCS_URL", "http://localhost:8081/swagger-ui.html").strip()
    sandbox = os.getenv("API_PROBE_SANDBOX_URL", "http://127.0.0.1:8001").rstrip("/")
    os.environ["API_PROBE_SANDBOX_URL"] = sandbox

    if not _http_ok(f"{sandbox}/health"):
        msg = f"sandbox down: {sandbox}/health"
        if require:
            _fail("probe_sandbox", msg)
        print(f"SKIP  probe  {msg}")
        return "SKIP"

    # OpenAPI 可达性（8081）
    try:
        with urllib.request.urlopen("http://127.0.0.1:8081/v3/api-docs", timeout=3) as resp:
            if int(resp.status) >= 400:
                raise urllib.error.HTTPError(docs, resp.status, "bad", hdrs=None, fp=None)
    except Exception as e:
        msg = f"docs OpenAPI unavailable: {e}"
        if require:
            _fail("probe_docs", msg)
        print(f"SKIP  probe  {msg}")
        return "SKIP"

    from tools.api_log_tool.api_health import (
        build_api_catalog,
        probe_api_catalog,
        summarize_api_doc_vs_logs,
    )
    from tools.api_log_tool.call_store import get_last_run_id, query_api_calls

    cat = build_api_catalog(docs_url=docs)
    if cat.get("error"):
        _fail("build_catalog", str(cat))
    # index count
    from tools.api_log_tool.catalog import load_index

    idx = load_index() or {}
    n = int(idx.get("endpoint_count") or len(idx.get("endpoints") or []))
    if n < 1:
        _fail("catalog_empty", str(n))

    probe = probe_api_catalog(mode="sandbox", limit=8, reset_sandbox=True)
    if probe.get("error"):
        _fail("probe", str(probe))
    rid = probe.get("run_id")
    if not rid:
        _fail("probe_run_id", str(probe.keys()))
    failed = probe.get("failed_count")
    if failed is None:
        failed = probe.get("failed")
    if int(failed or 0) != 0:
        _fail("probe_failed", f"failed={failed} sample={probe.get('failed_sample')}")
    if get_last_run_id("sandbox") != rid:
        _fail("last_run", f"{get_last_run_id('sandbox')} != {rid}")

    page = query_api_calls(source="sandbox", run_id=rid, limit=50)
    if page.get("returned", 0) < 1:
        _fail("probe_log_empty", str(page))
    if any(x.get("run_id") != rid for x in (page.get("items") or [])):
        _fail("probe_log_run_id", "mismatched run_id in calls")

    summary = summarize_api_doc_vs_logs(source_filter="sandbox", run_id="latest")
    win = summary.get("window") or {}
    if win.get("run_id") != rid:
        _fail("summarize_run_id", str(win))
    if int(win.get("call_count") or 0) < 1:
        _fail("summarize_calls", str(win))

    _ok("probe", f"catalog={n} probed_run={rid} calls={win.get('call_count')} fail=0")
    return "PASS"


def main() -> int:
    print("=== smoke_api_health (no LLM) ===")
    print(f"ROOT={ROOT}")
    try:
        smoke_middleware()
        smoke_log_analysis()
        probe_status = smoke_probe()
    except AssertionError as e:
        print(f"\nSMOKE_FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\nSMOKE_ERROR: {type(e).__name__}: {e}")
        return 1

    print(f"\nSMOKE_OK  (probe={probe_status})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
