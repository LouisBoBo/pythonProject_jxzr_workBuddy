#!/usr/bin/env python3
"""Live：对白名单仓跑 run_job 小改 README，并检查 raw GitHub 是否出现标记。

  SMOKE_CURSOR_LIVE=1 python3 scripts/smoke_cursor_dev_live_write.py
"""
from __future__ import annotations

import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

from cursor_dev.allowlist import normalize_repo, parse_allowlist  # noqa: E402
from cursor_dev.config import reload_config  # noqa: E402
from cursor_dev.github_preflight import resolve_starting_ref  # noqa: E402
from cursor_dev.jobs import create_job, get_job  # noqa: E402
from cursor_dev.prompts import build_first_turn_prompt  # noqa: E402
from cursor_dev.service import run_job  # noqa: E402


def main() -> int:
    if os.getenv("SMOKE_CURSOR_LIVE", "").strip() not in {"1", "true", "yes"}:
        print("skip: set SMOKE_CURSOR_LIVE=1 to run")
        return 0

    cfg = reload_config()
    allow = parse_allowlist(os.getenv("CURSOR_DEV_REPO_ALLOWLIST", "") or "")
    repo = allow[0] if allow else normalize_repo(os.getenv("SMOKE_CURSOR_REPO", "") or "")
    if not repo:
        print("need CURSOR_DEV_REPO_ALLOWLIST or SMOKE_CURSOR_REPO", file=sys.stderr)
        return 2

    pre = resolve_starting_ref(repo, "main")
    print("preflight", pre)
    if not pre.get("ok"):
        print("PREFLIGHT_FAIL", pre.get("error"), file=sys.stderr)
        return 3

    marker = f"<!-- workbuddy-live-{int(time.time())} -->"
    user_msg = (
        f"请只在 README.md 末尾追加一行：`{marker}`。"
        "不要改其它文件，不要创建 Pull Request。完成后一句话说明。"
    )
    prompt = build_first_turn_prompt(
        user_message=user_msg,
        repo=repo,
        work_branch=f"dev/wb/smoke",
        base_ref=pre.get("ref") or "main",
        create_pr=False,
    )
    data = ROOT / "data"
    job = create_job(
        data,
        user_id="smoke",
        username="smoke",
        thread_id="smoke-live-write",
        repo=repo,
        ref=pre.get("ref") or "main",
        message=user_msg,
        create_pr=False,
        system_prompt=prompt,
    )
    events: list[dict] = []
    print("job", job["id"], "running…")
    out = run_job(data, job, sink=events.append, cfg=cfg)
    print("status", out.get("status"))
    print("error", (out.get("error") or "")[:400])
    print("agent", out.get("agent_id"), "run", out.get("run_id"))
    print("events", [e.get("type") for e in events])

    # poll raw README
    ok_marker = False
    body = ""
    for _ in range(6):
        time.sleep(2)
        try:
            req = urllib.request.Request(
                f"https://raw.githubusercontent.com/{repo}/main/README.md",
                headers={"User-Agent": "workbuddy-smoke"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            if marker in body:
                ok_marker = True
                break
        except Exception as exc:  # noqa: BLE001
            print("readme_poll", exc)

    print("README:\n", body)
    print("HAS_MARKER", ok_marker)
    if out.get("status") == "idle_for_followup" and ok_marker:
        print("LIVE_WRITE_OK")
        return 0
    if out.get("status") == "idle_for_followup":
        print("LIVE_RUN_OK_BUT_MARKER_NOT_VISIBLE_YET")
        return 0
    print("LIVE_WRITE_FAIL", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
