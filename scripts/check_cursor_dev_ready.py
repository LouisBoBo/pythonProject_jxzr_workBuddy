#!/usr/bin/env python3
"""上线前检查 Cursor 写码车道是否已由管理员配好（同事零配置）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps"))


def main() -> int:
    from cursor_dev.config import reload_config
    from cursor_dev.readiness import build_readiness

    cfg = reload_config()
    report = build_readiness(cfg)
    print("=== Cursor 写码车道就绪检查（管理员）===")
    print(f"ready: {report['ready']}")
    print(f"summary: {report['summary']}")
    print(f"colleague_zero_config: {report.get('colleague_zero_config')}")
    print(f"work_branch: {report.get('work_branch') or '(按用户命名)'}")
    print(f"auto_pr: {report.get('auto_pr')}")
    print(f"github_token_configured: {report.get('github_token_configured')}")
    print("--- checks ---")
    for c in report["checks"]:
        flag = "OK " if c.get("ok") else "FAIL"
        if c.get("manual"):
            flag = "TODO"
        print(f"[{flag}] {c.get('title')}")
        if c.get("detail"):
            print(f"       {c['detail']}")
    print("---")
    if report["ready"]:
        print("服务端闸门通过。请确认两条人工 TODO 后即可让同事开箱使用 WorkBuddy 写码。")
        if not report.get("github_token_configured"):
            print("提示：建议补 GITHUB_TOKEN（私有仓预检 / 误开 PR 清理）。")
        return 0
    print("未通过：按 FAIL 项修复 .env / 白名单仓 / SDK 后重跑。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
