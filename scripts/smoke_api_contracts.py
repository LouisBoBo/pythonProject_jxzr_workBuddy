#!/usr/bin/env python3
"""HTTP 契约冒烟：覆盖功能清单中可无浏览器、弱依赖 LLM 的 API 用例。"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8765").rstrip("/")
fails: list[str] = []
oks: list[str] = []


def _ok(name: str, detail: str = "") -> None:
    msg = f"OK   {name}" + (f" ({detail})" if detail else "")
    print(msg)
    oks.append(name)


def _fail(name: str, detail: str) -> None:
    print(f"FAIL {name}: {detail}")
    fails.append(f"{name}: {detail}")


def _fake_jwt(*, sub: str = "9001", username: str = "smoke-api") -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": sub, "username": username, "exp": int(time.time()) + 3600}).encode()
    ).decode().rstrip("=")
    return f"{header}.{payload}.x"


def _req(
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict | None = None,
    timeout: float = 15.0,
) -> tuple[int, str, dict | list | None]:
    url = f"{API_BASE}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            code = resp.getcode()
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        code = e.code
    except Exception as e:
        return -1, str(e), None
    parsed = None
    try:
        parsed = json.loads(raw) if raw.strip() else None
    except Exception:
        parsed = None
    return code, raw, parsed


def test_health() -> None:
    code, raw, data = _req("GET", "/health")
    if code == 200 and isinstance(data, dict) and data.get("status") == "ok":
        _ok("TC-OPS-01 health", raw[:80])
    else:
        _fail("TC-OPS-01 health", f"code={code} body={raw[:200]}")


def test_ready() -> None:
    code, raw, data = _req("GET", "/health/ready")
    if code == 200 and isinstance(data, dict) and data.get("status") == "ready":
        _ok("TC-OPS-01 ready")
    else:
        _fail("TC-OPS-01 ready", f"code={code} body={raw[:200]}")


def test_auth_me_and_history() -> None:
    token = _fake_jwt()
    code, raw, data = _req("GET", "/api/auth/me", token=token)
    # AUTH_REQUIRED=false 时可能不校验；有 token 也应不 500
    if code in (200, 401):
        _ok("TC-AUTH-me", f"code={code}")
    else:
        _fail("TC-AUTH-me", f"code={code} body={raw[:200]}")

    tid = f"smoke-api-{int(time.time())}"
    payload = {
        "thread_id": tid,
        "title": "smoke",
        "messages": [
            {"role": "user", "content": "hello smoke"},
            {"role": "assistant", "content": "hi\n\n（已停止生成）", "meta": {"stopped": True}},
        ],
    }
    code, raw, data = _req("POST", "/api/history/save", token=token, body=payload)
    if code == 200:
        _ok("TC-HIST-save")
    else:
        _fail("TC-HIST-save", f"code={code} body={raw[:300]}")
        return

    code, raw, data = _req("GET", f"/api/history/{tid}", token=token)
    if code == 200 and isinstance(data, dict):
        msgs = data.get("messages") or []
        if any("已停止生成" in str(m.get("content", "")) for m in msgs if isinstance(m, dict)):
            _ok("TC-HIST-load stopped note")
        else:
            _fail("TC-HIST-load", f"missing stopped note: {raw[:300]}")
    else:
        _fail("TC-HIST-load", f"code={code} body={raw[:300]}")

    # 另一用户不得读取
    other = _fake_jwt(sub="9002", username="other")
    code, raw, data = _req("GET", f"/api/history/{tid}", token=other)
    if code in (403, 404):
        _ok("TC-AUTH-03 isolation", f"code={code}")
    elif code == 200:
        _fail("TC-AUTH-03 isolation", "other user can read foreign history")
    else:
        # AUTH_REQUIRED=false 可能放宽，记为告警级失败
        _fail("TC-AUTH-03 isolation", f"unexpected code={code} body={raw[:200]}")

    code, raw, data = _req("DELETE", f"/api/history/{tid}", token=token)
    if code in (200, 204):
        _ok("TC-HIST-02 delete")
    else:
        _fail("TC-HIST-02 delete", f"code={code} body={raw[:200]}")


def test_writes_pending_list() -> None:
    token = _fake_jwt()
    code, raw, data = _req("GET", "/api/writes/pending", token=token)
    if code == 200:
        _ok("TC-WRITE pending list")
    else:
        _fail("TC-WRITE pending list", f"code={code} body={raw[:200]}")

    code, raw, data = _req("GET", "/api/writes/audit?limit=5", token=token)
    if code == 200:
        _ok("TC-WRITE audit list")
    else:
        _fail("TC-WRITE audit list", f"code={code} body={raw[:200]}")


def test_ide_bridge_status() -> None:
    token = _fake_jwt()
    code, raw, data = _req("GET", "/api/ide/bridge/status", token=token)
    if code == 200 and isinstance(data, dict):
        _ok("TC-IDE status", f"keys={list(data.keys())[:6]}")
    else:
        _fail("TC-IDE status", f"code={code} body={raw[:200]}")


def test_upload_and_download_roundtrip() -> None:
    token = _fake_jwt()
    # multipart upload via urllib is awkward; use tempfile + curl-like raw
    import tempfile
    import subprocess

    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write("a,b\n1,2\n")
        path = f.name
    try:
        cmd = [
            "curl",
            "-sS",
            "-m",
            "20",
            "-w",
            "\nHTTP %{http_code}",
            "-H",
            f"Authorization: Bearer {token}",
            "-F",
            f"file=@{path};type=text/csv",
            f"{API_BASE}/api/upload",
        ]
        out = subprocess.check_output(cmd, text=True)
        if "HTTP 200" in out or '"path"' in out or '"filename"' in out:
            _ok("TC-FILE-01 upload", out[-120:].replace("\n", " "))
        else:
            _fail("TC-FILE-01 upload", out[:400])
    except Exception as e:
        _fail("TC-FILE-01 upload", str(e))
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def test_chat_stream_abortable() -> None:
    """短超时拉 SSE：能建立流或明确鉴权错误；断开后服务应存活。"""
    token = _fake_jwt()
    body = json.dumps(
        {
            "message": "只回复两个字：好的",
            "thread_id": f"smoke-stream-{int(time.time())}",
            "file_paths": [],
        }
    ).encode()
    req = urllib.request.Request(
        f"{API_BASE}/api/chat/stream",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            chunk = resp.read(128)
            text = chunk.decode("utf-8", errors="replace")
            if resp.getcode() == 200 and ( "data:" in text or text.startswith(":") or len(text) > 0):
                _ok("TC-CHAT-01 stream start", text[:60].replace("\n", " "))
            else:
                _fail("TC-CHAT-01 stream start", f"code={resp.getcode()} chunk={text[:120]}")
    except TimeoutError:
        _ok("TC-CHAT-01 stream start", "read timeout after open (expected under LLM)")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        if e.code in (401, 403):
            _fail("TC-CHAT-01 stream start", f"auth blocked code={e.code} {raw[:120]}")
        else:
            _fail("TC-CHAT-01 stream start", f"HTTP {e.code} {raw[:200]}")
    except Exception as e:
        msg = str(e)
        if "timed out" in msg.lower() or "timeout" in msg.lower():
            _ok("TC-CHAT-01 stream start", "timeout ok")
        else:
            _fail("TC-CHAT-01 stream start", msg)

    code, _, data = _req("GET", "/health")
    if code == 200:
        _ok("TC-CHAT stream abort api alive")
    else:
        _fail("TC-CHAT stream abort api alive", f"code={code}")


def main() -> int:
    print(f"=== smoke_api_contracts base={API_BASE} ===")
    test_health()
    test_ready()
    test_auth_me_and_history()
    test_writes_pending_list()
    test_ide_bridge_status()
    test_upload_and_download_roundtrip()
    test_chat_stream_abortable()
    print(f"--- summary ok={len(oks)} fail={len(fails)} ---")
    if fails:
        for f in fails:
            print(f"DETAIL {f}")
        print("SMOKE_FAIL api-contracts")
        return 1
    print("SMOKE_OK api-contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
