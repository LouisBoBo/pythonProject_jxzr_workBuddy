#!/usr/bin/env python3
"""M0 IDE 审核冒烟：默认 mock（必过）；IDE_REVIEW_MCP=1 时可选试本机 MCP。

不启动 API / 不加载 Deep Agent / 不改现网工具列表。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "apps" / "agent"
sys.path.insert(0, str(AGENT))

from tools.ide_review.review import run_ide_review  # noqa: E402


def _ok(name: str) -> None:
    print(f"OK   {name}")


def _fail(name: str, detail: str) -> None:
    print(f"FAIL {name}: {detail}")
    raise SystemExit(1)


def _skip(name: str, detail: str) -> None:
    print(f"SKIP {name}: {detail}")


def test_mock() -> dict:
    result = run_ide_review(
        ROOT,
        paths=None,
        prompt="M0 smoke mock：关注 token / except",
        provider="mock",
    )
    if result.get("status") != "ok":
        _fail("mock_status", json.dumps(result, ensure_ascii=False))
    if result.get("provider") != "mock":
        _fail("mock_provider", str(result.get("provider")))
    findings = result.get("findings")
    if not isinstance(findings, list) or len(findings) < 1:
        _fail("mock_findings", "期望至少 1 条 finding（样例文件应命中规则）")
    for f in findings:
        for key in ("severity", "path", "line", "rule", "message"):
            if key not in f:
                _fail("mock_finding_shape", f"缺少字段 {key}: {f}")
        if f["severity"] not in ("P0", "P1", "P2"):
            _fail("mock_severity", str(f["severity"]))
    _ok(f"mock_review findings={len(findings)}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def test_live_optional() -> None:
    wanted = os.getenv("IDE_REVIEW_MCP", "").strip().lower() in ("1", "true", "yes")
    if not wanted:
        _skip("live_mcp", "未设置 IDE_REVIEW_MCP=1（可选；mock 已足够验收 Checkpoint A）")
        return

    require = os.getenv("IDE_REVIEW_MCP_REQUIRE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    result = run_ide_review(
        ROOT,
        paths=None,
        prompt="M0 smoke live MCP",
        provider="mcp",
    )
    status = result.get("status")
    if status == "ok":
        _ok(
            f"live_mcp tool={result.get('mcp_tool')} findings={len(result.get('findings') or [])}"
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    reason = result.get("skip_reason") or result.get("raw_summary") or status
    if require:
        _fail("live_mcp_required", str(reason))
    _skip("live_mcp", str(reason))
    if result.get("stderr_tail"):
        print("--- stderr tail ---")
        print(result["stderr_tail"])


def main() -> None:
    print("=== smoke_ide_review_m0 ===")
    test_mock()
    test_live_optional()
    print("SMOKE_OK")


if __name__ == "__main__":
    main()
