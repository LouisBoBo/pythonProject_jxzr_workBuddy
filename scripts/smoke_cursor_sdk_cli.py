#!/usr/bin/env python3
"""Cursor SDK CLI 冒烟（D3）。

默认（安全）：校验 import + models.list，不创建 Cloud Agent。
Live（耗用量/会改仓）：

  SMOKE_CURSOR_LIVE=1 python3 scripts/smoke_cursor_sdk_cli.py

显式 Cloud，禁止静默落到 local。勿并入默认 make smoke 必跑集。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from cursor_dev.allowlist import normalize_repo, parse_allowlist  # noqa: E402


def _require_key() -> str:
    key = (os.getenv("CURSOR_API_KEY") or "").strip()
    if not key:
        raise SystemExit("缺少 CURSOR_API_KEY")
    return key


def smoke_models(api_key: str) -> None:
    from cursor_sdk import Cursor

    models = Cursor.models.list(api_key=api_key)
    ids = []
    for m in models or []:
        mid = getattr(m, "id", None) or (m.get("id") if isinstance(m, dict) else None)
        if mid:
            ids.append(str(mid))
    print(f"models.list: count={len(ids)}")
    if ids:
        print("models.sample:", ", ".join(ids[:8]))
    want = (os.getenv("CURSOR_DEV_MODEL") or "composer-2.5").strip()
    if ids and want not in ids and want != "auto":
        print(f"WARN: 配置模型 {want!r} 不在当前账号 models.list 中（仍可尝试 Cloud）")
    else:
        print(f"model_ok_hint: {want}")


def smoke_cloud_live(api_key: str) -> int:
    from cursor_sdk import (
        Agent,
        AgentOptions,
        CloudAgentOptions,
        CloudRepository,
        CursorAgentError,
    )

    allow = parse_allowlist(os.getenv("CURSOR_DEV_REPO_ALLOWLIST", "") or "")
    repo = allow[0] if allow else normalize_repo(os.getenv("SMOKE_CURSOR_REPO", "") or "")
    if not repo:
        print("LIVE 需要 CURSOR_DEV_REPO_ALLOWLIST 或 SMOKE_CURSOR_REPO=owner/repo", file=sys.stderr)
        return 2

    model = (os.getenv("CURSOR_DEV_MODEL") or "composer-2.5").strip()
    url = f"https://github.com/{repo}"
    ref = (
        (os.getenv("SMOKE_CURSOR_REF") or "").strip()
        or (os.getenv("CURSOR_DEV_STARTING_REF") or "").strip()
        or None
    )
    auto_pr = (os.getenv("SMOKE_CURSOR_AUTO_PR") or "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    skip_rev = (os.getenv("CURSOR_DEV_SKIP_REVIEWER_REQUEST") or "1").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    prompt = (
        "这是 WorkBuddy cursor-dev CLI 冒烟。"
        "请仅在 README.md（若不存在则创建）末尾追加一行："
        "`<!-- workbuddy-cursor-dev-smoke -->`。"
        "不要改其它文件，不要扩大范围。"
        + (" 完成后创建 Pull Request。" if auto_pr else " 不要创建 Pull Request。")
    )

    cloud_kwargs = {
        "repos": [CloudRepository(url=url, **({"starting_ref": ref} if ref else {}))],
        "auto_create_pr": auto_pr,
    }
    # skip_reviewer_request 若 SDK 支持则传入
    try:
        cloud = CloudAgentOptions(**cloud_kwargs, skip_reviewer_request=skip_rev)
    except TypeError:
        cloud = CloudAgentOptions(**cloud_kwargs)

    print(f"LIVE cloud repo={repo} model={model} auto_pr={auto_pr}")
    try:
        result = Agent.prompt(
            prompt,
            AgentOptions(
                api_key=api_key,
                model=model,
                cloud=cloud,
            ),
        )
    except CursorAgentError as err:
        print(
            f"startup_failed: {err.message} retryable={getattr(err, 'is_retryable', None)}",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"startup_failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    status = getattr(result, "status", None)
    run_id = getattr(result, "id", None)
    agent_id = getattr(result, "agent_id", None)
    print(f"run.status={status} run.id={run_id} agent_id={agent_id}")
    text = getattr(result, "result", None) or getattr(result, "text", None)
    if text:
        print("result_text_head:", str(text)[:500])
    if str(status).lower() in {"error", "failed"}:
        return 2
    print("LIVE: OK")
    return 0


def main() -> int:
    api_key = _require_key()
    print("import cursor_sdk: OK")
    live = (os.getenv("SMOKE_CURSOR_LIVE") or "").strip().lower() in {"1", "true", "yes"}

    try:
        smoke_models(api_key)
    except Exception as exc:  # noqa: BLE001
        print(f"models.list failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        if not live:
            return 1
        print("WARN: models.list 失败，继续尝试 LIVE", file=sys.stderr)

    if not live:
        print("skip LIVE（设置 SMOKE_CURSOR_LIVE=1 才会 Cloud 改仓）")
        print("提示：LIVE 若报 default branch，请设 SMOKE_CURSOR_REF=实际分支名")
        print("smoke_cursor_sdk_cli: OK (dry)")
        return 0
    return smoke_cloud_live(api_key)


if __name__ == "__main__":
    raise SystemExit(main())
