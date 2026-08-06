"""D4：cursor_dev jobs 落盘与校验（不调 Cloud）。"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps"))

from cursor_dev.allowlist import normalize_repo  # noqa: E402
from cursor_dev.audit import append_audit  # noqa: E402
from cursor_dev.jobs import create_job, get_job, update_job  # noqa: E402
from cursor_dev.prompts import build_first_turn_prompt  # noqa: E402


def main() -> int:
    assert normalize_repo("https://github.com/a/b") == "a/b"
    prompt = build_first_turn_prompt(
        user_message="加个登录页",
        repo="LouisBoBo/pythonProject_zr_aicoding",
        work_branch="dev/wb/hebo",
        base_ref="main",
        create_pr=False,
    )
    assert "登录页" in prompt and "dev/wb/hebo" in prompt

    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp)
        job = create_job(
            data,
            user_id="1",
            username="tester",
            thread_id="session-1",
            repo="LouisBoBo/pythonProject_zr_aicoding",
            ref="hebo",
            message="加个登录页",
            create_pr=False,
            system_prompt=prompt,
        )
        assert job["status"] == "queued"
        assert get_job(data, job["id"])["repo"] == "LouisBoBo/pythonProject_zr_aicoding"
        updated = update_job(data, job["id"], status="idle_for_followup", agent_id="bc-test")
        assert updated["agent_id"] == "bc-test"
        append_audit(data, {"event": "test", "job_id": job["id"]})
        audit = (data / "cursor_dev" / "audit.jsonl").read_text(encoding="utf-8")
        assert job["id"] in audit

    # 拒绝未确认：由 HTTP 层测；此处只保证模块可 import
    print("smoke_cursor_dev_d4: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
