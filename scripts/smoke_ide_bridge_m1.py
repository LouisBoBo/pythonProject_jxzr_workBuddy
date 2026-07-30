#!/usr/bin/env python3
"""M1 IDE Bridge 冒烟：无 LLM。register → submit → poll/result → findings。"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "apps" / "agent"
API = ROOT / "apps" / "api"
sys.path.insert(0, str(AGENT))
sys.path.insert(0, str(API))


def _fail(name: str, detail: str) -> None:
    print(f"FAIL {name}: {detail}")
    raise SystemExit(1)


def _ok(name: str) -> None:
    print(f"OK   {name}")


def main() -> None:
    print("=== smoke_ide_bridge_m1 ===")
    td = tempfile.mkdtemp(prefix="wb-ide-bridge-")
    os.environ["DATA_DIR"] = td
    os.environ["IDE_REVIEW_ENABLED"] = "1"
    os.environ["IDE_BRIDGE_HEARTBEAT_TTL_SEC"] = "30"
    os.environ["IDE_BRIDGE_TASK_TIMEOUT_SEC"] = "20"

    import importlib

    import config

    importlib.reload(config)
    from tools.ide_review import bridge_store
    from tools.ide_review.mock_provider import mock_review_files
    from tools.ide_review.paths import resolve_repo_paths
    from tools.ide_review.review import DEFAULT_REVIEW_PATHS

    importlib.reload(bridge_store)

    if not bridge_store.feature_enabled():
        _fail("feature_enabled", "期望 IDE_REVIEW_ENABLED=1")

    uid = "smoke-user-1"
    bridge_id = "smoke-bridge-1"

    # 已连接但未开工程
    bridge_store.register_bridge(
        user_id=uid,
        username="smoke",
        bridge_id=bridge_id,
        workspace_root="",
        carrier="vscode",
        workspace_ready=False,
    )
    nw = bridge_store.submit_review_task(
        uid,
        paths=["apps/web/src/embed.js"],
        prompt="no ws",
        timeout_sec=2,
    )
    if nw.get("status") != "no_workspace":
        _fail("no_workspace", str(nw))
    _ok("no_workspace_message")

    bridge_store.register_bridge(
        user_id=uid,
        username="smoke",
        bridge_id=bridge_id,
        workspace_root=str(ROOT),
        carrier="vscode",
        workspace_ready=True,
    )
    st = bridge_store.get_status(uid)
    if not st.get("online") or not st.get("workspace_ready"):
        _fail("online_after_register", str(st))
    _ok("register_online")

    # 离线用户
    off = bridge_store.submit_review_task(
        "nobody",
        paths=["apps/web/src/embed.js"],
        prompt="offline",
        timeout_sec=2,
    )
    if off.get("status") != "offline":
        _fail("offline_status", str(off))
    _ok("offline_message")

    stop = threading.Event()

    def bridge_worker() -> None:
        from tools.ide_review.local_files import read_workspace_files

        while not stop.is_set():
            try:
                task = bridge_store.claim_pending_task(uid, bridge_id)
            except Exception:
                time.sleep(0.2)
                continue
            if not task:
                time.sleep(0.2)
                continue
            intent = str(task.get("intent") or "code_review")
            paths = task.get("paths") if isinstance(task.get("paths"), list) else None
            if intent == "read_files":
                packed = read_workspace_files(ROOT, paths or [])
                bridge_store.put_result(uid, task["task_id"], packed)
                continue
            files, errors = resolve_repo_paths(
                ROOT, paths, default_paths=DEFAULT_REVIEW_PATHS
            )
            if errors and not files:
                bridge_store.put_result(
                    uid,
                    task["task_id"],
                    {
                        "status": "error",
                        "findings": [],
                        "file_contents": [],
                        "raw_summary": ";".join(errors),
                        "provider": "bridge",
                    },
                )
                continue
            result = mock_review_files(
                ROOT, files, prompt=str(task.get("prompt") or "")
            )
            result["provider"] = "bridge"
            packed = read_workspace_files(
                ROOT, [f.relative_to(ROOT).as_posix() for f in files]
            )
            result["file_contents"] = packed.get("file_contents") or []
            bridge_store.put_result(uid, task["task_id"], result)

    t = threading.Thread(target=bridge_worker, daemon=True)
    t.start()
    try:
        result = bridge_store.submit_review_task(
            uid,
            paths=["apps/web/src/embed.js"],
            prompt="M1 smoke",
            timeout_sec=15,
        )
        if result.get("status") not in ("ok",):
            _fail("submit_status", str(result))
        if result.get("provider") != "bridge":
            _fail("provider", str(result.get("provider")))
        findings = result.get("findings") or []
        if not isinstance(findings, list) or len(findings) < 1:
            _fail("findings", str(result))
        contents = result.get("file_contents") or []
        if not contents or not contents[0].get("content"):
            _fail("file_contents", str(result.get("file_contents")))
        _ok(f"roundtrip findings={len(findings)} file_contents={len(contents)}")

        # 绝对路径（工作区内）经 Bridge 读取，模拟 Agent 误传绝对路径
        abs_path = str((ROOT / "apps/web/src/embed.js").resolve())
        read_res = bridge_store.submit_read_files_task(
            uid, paths=[abs_path], timeout_sec=15
        )
        if read_res.get("status") != "ok":
            _fail("read_abs_status", str(read_res))
        fc = read_res.get("file_contents") or []
        if not fc or "access_token" not in str(fc[0].get("content") or ""):
            _fail("read_abs_content", str(read_res)[:500])
        _ok("read_files_absolute_under_workspace")

        # 回归：HTTP ResultBody 必须保留 file_contents（VS Code 扩展走此路径）
        from routes.ide_bridge import ResultBody

        body = ResultBody.model_validate(
            {
                "task_id": "smoke-http-1",
                "status": "ok",
                "findings": [],
                "file_contents": [
                    {
                        "path": "src/Foo.java",
                        "content": "class Foo {}",
                        "bytes": 12,
                        "truncated": False,
                    }
                ],
                "hint": "must keep",
                "sources": ["file_contents"],
                "review_empty": True,
            }
        )
        if not body.file_contents or body.file_contents[0].get("path") != "src/Foo.java":
            _fail("http_result_body_file_contents", str(body))
        if body.hint != "must keep":
            _fail("http_result_body_hint", body.hint)
        _ok("http_result_body_keeps_file_contents")

        # 配对码：create → redeem → 一次性
        created = bridge_store.create_pairing_code(
            user_id=uid,
            username="smoke",
            access_token="smoke-jwt-token-xyz",
        )
        code = created.get("code") or ""
        if len(code) != 6:
            _fail("pairing_code_len", str(created))
        redeemed = bridge_store.redeem_pairing_code(code)
        tok = str(redeemed.get("access_token") or "")
        if not tok.startswith("wb1.") or redeemed.get("token_type") != "bridge":
            _fail("pairing_redeem_bridge_token", str(redeemed)[:200])
        from tools.ide_review.bridge_token import verify_bridge_token

        payload = verify_bridge_token(tok)
        if not payload or str(payload.get("sub")) != str(uid):
            _fail("pairing_verify", str(payload))
        try:
            bridge_store.redeem_pairing_code(code)
            _fail("pairing_reuse", "应拒绝二次兑换")
        except KeyError:
            pass
        _ok("pairing_create_redeem_once")

        # Git/本地目录降级审核
        from tools.ide_review.git_review import run_git_or_local_review

        grev = run_git_or_local_review(
            local_path=str(ROOT),
            paths=["apps/web/src/embed.js"],
            prompt="smoke",
        )
        if grev.get("status") != "ok":
            _fail("git_review_status", str(grev)[:400])
        if not (grev.get("file_contents") or []):
            _fail("git_review_contents", str(grev)[:400])
        _ok(f"git_local_review findings={len(grev.get('findings') or [])}")

        # —— 企业级：跨用户结果隔离 ——
        tid = bridge_store.enqueue_task(
            uid,
            {
                "intent": "code_review",
                "paths": ["apps/web/src/embed.js"],
                "prompt": "iso",
            },
        )
        try:
            bridge_store.put_result(
                "attacker-user",
                tid,
                {"status": "ok", "findings": [], "file_contents": [], "stolen": True},
            )
            _fail("cross_user_put_result", "应拒绝异用户回传")
        except PermissionError as e:
            if "task_owner_mismatch" not in str(e):
                _fail("cross_user_put_result_reason", str(e))
        try:
            bridge_store.wait_result(tid, timeout_sec=0.5, user_id="attacker-user")
            _fail("cross_user_wait_result", "应拒绝异用户等待")
        except PermissionError:
            pass
        from tools.ide_review.ide_audit import query_ide_audit

        rejected = query_ide_audit(event="ide_result_rejected", limit=20)
        if not any(
            str(r.get("task_id")) == tid and r.get("reason") == "task_owner_mismatch"
            for r in rejected
        ):
            _fail("audit_result_rejected", str(rejected)[:400])
        _ok("cross_user_isolation")

        # —— 企业级：路径穿越 + 敏感文件拒绝 ——
        from tools.ide_review.local_files import read_workspace_files, to_workspace_relative

        _, trav_err = to_workspace_relative(ROOT, "../etc/passwd")
        if not trav_err or "穿越" not in trav_err:
            _fail("path_traversal", str(trav_err))
        _, sens_err = to_workspace_relative(ROOT, ".env")
        if not sens_err or "敏感" not in sens_err:
            _fail("sensitive_env", str(sens_err))
        packed_bad = read_workspace_files(
            ROOT,
            ["../etc/passwd", ".env", "apps/web/src/embed.js"],
            audit_user_id=uid,
        )
        paths_ok = [i.get("path") for i in (packed_bad.get("file_contents") or [])]
        if "apps/web/src/embed.js" not in paths_ok:
            _fail("path_filter_keep_good", str(packed_bad)[:400])
        if any("passwd" in str(p) or p == ".env" for p in paths_ok):
            _fail("path_filter_leak", str(paths_ok))
        path_rej = query_ide_audit(event="ide_path_rejected", user_id=uid, limit=20)
        if len(path_rej) < 1:
            _fail("audit_path_rejected", "缺少路径拒绝审计")
        _ok("path_traversal_and_sensitive_denied")
    finally:
        stop.set()
        t.join(timeout=2)

    # 开关关闭时 feature 应为 false（reload config）
    os.environ["IDE_REVIEW_ENABLED"] = "0"
    importlib.reload(config)
    importlib.reload(bridge_store)
    if bridge_store.feature_enabled():
        _fail("feature_off", "期望关闭")
    # 关闭后入队接口应视为功能不可用（工具层依赖 feature_enabled）
    st_off = bridge_store.get_status(uid)
    if st_off.get("feature_enabled") is not False:
        _fail("status_feature_off", str(st_off))
    _ok("feature_flag_off")

    print("SMOKE_OK")


if __name__ == "__main__":
    main()
