#!/usr/bin/env python3
"""WorkBuddy IDE Bridge（M1）：本机出站连 API，承接代码审核任务。

本机与 API 共享 DATA_DIR 时，用扫盘取任务（避免 Agent 阻塞事件循环导致 HTTP poll 死锁）。
结果写回 results/，并短请求心跳保持「在线」。

用法:
  python3 apps/ide-bridge/run.py \\
    --api http://127.0.0.1:8765 \\
    --token "<与网页同一 ERP JWT>" \\
    --workspace /path/to/repo
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "apps" / "agent"
sys.path.insert(0, str(AGENT))

from tools.ide_review import bridge_store  # noqa: E402
from tools.ide_review.local_files import read_workspace_files, to_workspace_relative  # noqa: E402
from tools.ide_review.mock_provider import mock_review_files  # noqa: E402
from tools.ide_review.paths import resolve_repo_paths  # noqa: E402
from tools.ide_review.review import DEFAULT_REVIEW_PATHS  # noqa: E402


def _req(
    method: str,
    url: str,
    token: str,
    body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {url}: {detail}") from e
    except URLError as e:
        raise RuntimeError(f"连接失败 {url}: {e}") from e


def run_once_review(workspace: Path, task: dict[str, Any]) -> dict[str, Any]:
    paths = task.get("paths") if isinstance(task.get("paths"), list) else None
    prompt = str(task.get("prompt") or "")
    files, errors = resolve_repo_paths(
        workspace, paths, default_paths=DEFAULT_REVIEW_PATHS
    )
    if errors and not files:
        return {
            "status": "error",
            "findings": [],
            "file_contents": [],
            "diagnostics_count": {"P0": 0, "P1": 0, "P2": 0},
            "raw_summary": "；".join(errors),
            "workspace_root": str(workspace),
            "files": [],
            "errors": errors,
            "provider": "bridge",
        }
    result = mock_review_files(workspace, files, prompt=prompt)
    if errors:
        result = dict(result)
        result["path_warnings"] = errors
    result["provider"] = "bridge"

    if task.get("include_file_contents", True):
        rels: list[str] = []
        for p in paths or []:
            rel, _err = to_workspace_relative(workspace, str(p))
            if rel:
                rels.append(rel)
        if not rels:
            root = workspace.resolve()
            rels = [f.resolve().relative_to(root).as_posix() for f in files]
        packed = read_workspace_files(workspace, rels)
        result["file_contents"] = packed.get("file_contents") or []
        if packed.get("errors"):
            result["errors"] = list(result.get("errors") or []) + list(packed["errors"])
        result["raw_summary"] = (
            str(result.get("raw_summary") or "")
            + f"；附带 {len(result['file_contents'])} 个文件内容"
        )
    return result


def run_once_read(workspace: Path, task: dict[str, Any]) -> dict[str, Any]:
    paths = task.get("paths") if isinstance(task.get("paths"), list) else []
    packed = read_workspace_files(workspace, paths)
    packed["hint"] = "内容来自本机工作区；勿用服务端 read_file 再读绝对路径。"
    return packed


def main() -> None:
    parser = argparse.ArgumentParser(description="WorkBuddy IDE Bridge (M1)")
    parser.add_argument("--api", default="http://127.0.0.1:8765", help="WorkBuddy API 根地址")
    parser.add_argument("--token", required=True, help="与网页登录相同的 Bearer JWT")
    parser.add_argument(
        "--workspace",
        default=str(ROOT),
        help="本地代码仓库根目录（载体）",
    )
    parser.add_argument("--bridge-id", default="", help="可选；默认随机生成")
    parser.add_argument(
        "--data-dir",
        default="",
        help="与 API 相同的 DATA_DIR；默认读环境变量或仓库 data/",
    )
    args = parser.parse_args()

    if args.data_dir.strip():
        import os

        os.environ["DATA_DIR"] = str(Path(args.data_dir).expanduser().resolve())

    api = args.api.rstrip("/")
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.is_dir():
        print(f"workspace 不存在: {workspace}", file=sys.stderr)
        raise SystemExit(2)

    bridge_id = (args.bridge_id or "").strip() or f"bridge-{uuid.uuid4().hex[:12]}"
    token = args.token.strip()
    if not token:
        print("token 不能为空", file=sys.stderr)
        raise SystemExit(2)

    print(f"[ide-bridge] api={api}")
    print(f"[ide-bridge] workspace={workspace}")
    print(f"[ide-bridge] bridge_id={bridge_id}")
    print("[ide-bridge] 注册中…")

    reg = _req(
        "POST",
        f"{api}/api/ide/bridge/register",
        token,
        {
            "bridge_id": bridge_id,
            "workspace_root": str(workspace),
            "carrier": "local_workspace",
            "workspace_ready": True,
        },
    )
    session = (reg or {}).get("session") or {}
    user_id = session.get("user_id")
    if user_id is None:
        print("[ide-bridge] 注册响应缺少 user_id", file=sys.stderr)
        raise SystemExit(2)

    print(f"[ide-bridge] 已连接 user_id={user_id}（扫盘取任务，Ctrl+C 退出）")
    last_hb = 0.0

    try:
        while True:
            now = time.time()
            if now - last_hb >= 10.0:
                try:
                    _req(
                        "POST",
                        f"{api}/api/ide/bridge/heartbeat",
                        token,
                        {
                            "bridge_id": bridge_id,
                            "workspace_root": str(workspace),
                            "workspace_ready": True,
                        },
                        timeout=10.0,
                    )
                    last_hb = now
                except Exception as e:
                    print(f"[ide-bridge] heartbeat 失败: {e}", file=sys.stderr)
                    time.sleep(2)
                    continue

            try:
                task = bridge_store.claim_pending_task(user_id, bridge_id)
            except PermissionError:
                print("[ide-bridge] bridge_id 不匹配，请重启 Bridge", file=sys.stderr)
                time.sleep(2)
                continue

            if not task:
                time.sleep(0.35)
                continue

            task_id = str(task.get("task_id") or "")
            intent = str(task.get("intent") or "code_review")
            print(f"[ide-bridge] 收到任务 {task_id} intent={intent} paths={task.get('paths')}")
            if intent == "read_files":
                result = run_once_read(workspace, task)
            else:
                result = run_once_review(workspace, task)
            body = {
                "status": result.get("status") or "ok",
                "findings": result.get("findings") or [],
                "file_contents": result.get("file_contents") or [],
                "diagnostics_count": result.get("diagnostics_count")
                or {"P0": 0, "P1": 0, "P2": 0},
                "raw_summary": result.get("raw_summary") or "",
                "workspace_root": result.get("workspace_root") or str(workspace),
                "files": result.get("files") or [],
                "provider": "bridge",
                "errors": result.get("errors") or [],
                "hint": result.get("hint") or "",
            }
            # 直接写共享 DATA_DIR，不依赖被 Agent 堵住的 HTTP
            bridge_store.put_result(user_id, task_id, body)
            try:
                _req(
                    "POST",
                    f"{api}/api/ide/bridge/result",
                    token,
                    {"task_id": task_id, **body},
                    timeout=10.0,
                )
            except Exception as e:
                # 文件已写好即可；HTTP 失败只告警
                print(f"[ide-bridge] HTTP 回传可选失败（已写本地 result）: {e}", file=sys.stderr)
            n_find = len(body["findings"])
            n_files = len(body["file_contents"])
            print(f"[ide-bridge] 已回传 {task_id} findings={n_find} file_contents={n_files}")
    except KeyboardInterrupt:
        print("\n[ide-bridge] 已退出")


if __name__ == "__main__":
    main()
