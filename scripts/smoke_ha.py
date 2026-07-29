#!/usr/bin/env python3
"""无 LLM：跨进程锁 + 写确认 CAS（模拟双实例抢同一 pending）。"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "apps" / "agent"


def _fail(name: str, detail: str) -> None:
    print(f"FAIL {name}: {detail}")
    raise SystemExit(1)


def _ok(name: str) -> None:
    print(f"OK   {name}")


def _worker_claim(data_dir: str, action_id: str, tag: str) -> str:
    os.environ["DATA_DIR"] = data_dir
    # 子进程需独立 import
    sys.path.insert(0, str(AGENT))
    from middleware.write_store import claim_action

    time.sleep(0.02)  # 错峰一点仍可能并发
    got = claim_action(
        action_id,
        to_status="confirmed",
        expected_statuses=("pending",),
        actor_username=tag,
        result={"ok": True, "by": tag},
        audit=True,
    )
    return tag if got else ""


def test_interprocess_lock_basic() -> None:
    with tempfile.TemporaryDirectory() as td:
        os.environ["DATA_DIR"] = td
        sys.path.insert(0, str(AGENT))
        # 清掉可能已加载的 config 缓存路径——Config.DATA_DIR 在 import 时求值
        import importlib
        import config

        importlib.reload(config)
        import ha.fs_lock as fs_lock

        importlib.reload(fs_lock)

        lock = fs_lock.InterProcessLock("smoke")
        assert lock.acquire(True, timeout=2)
        # 可重入
        assert lock.acquire(True, timeout=2)
        lock.release()
        lock.release()
        _ok("interprocess lock reentrant")


def test_dual_claim_cas() -> None:
    with tempfile.TemporaryDirectory() as td:
        os.environ["DATA_DIR"] = td
        sys.path.insert(0, str(AGENT))
        import importlib
        import config

        importlib.reload(config)
        import middleware.write_store as ws

        importlib.reload(ws)

        action = ws.create_pending_action(
            tool="import_file_to_platform",
            args={"file_path": "/tmp/x.csv", "target_entity": "work-orders"},
            preview={"file": "x.csv", "target_entity": "work-orders", "row_count": 1},
            thread_id="session-ha-smoke",
            user_id="1",
            username="admin",
        )
        aid = action["action_id"]

        winners: list[str] = []
        with ProcessPoolExecutor(max_workers=2) as pool:
            futs = [
                pool.submit(_worker_claim, td, aid, "api-a"),
                pool.submit(_worker_claim, td, aid, "api-b"),
            ]
            for f in as_completed(futs):
                tag = f.result()
                if tag:
                    winners.append(tag)

        if len(winners) != 1:
            _fail("dual_claim", f"expected exactly 1 winner, got {winners}")

        final = ws.get_action(aid)
        if not final or final.get("status") != "confirmed":
            _fail("final_status", str(final))
        _ok(f"dual claim CAS (winner={winners[0]})")


def main() -> None:
    test_interprocess_lock_basic()
    test_dual_claim_cas()
    print("SMOKE_OK ha")


if __name__ == "__main__":
    main()
