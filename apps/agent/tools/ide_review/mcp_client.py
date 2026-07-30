"""最小 MCP stdio JSON-RPC 客户端（无第三方依赖，仅供 M0 可选 live）。

支持 MCP 标准 Content-Length 帧；兼容部分实现的 NDJSON 行协议。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from typing import Any


class McpStdioError(RuntimeError):
    pass


class McpStdioClient:
    """极简 MCP client：initialize → tools/list → tools/call。"""

    def __init__(
        self,
        command: str,
        args: list[str],
        *,
        cwd: str | None = None,
        timeout_sec: float = 45.0,
    ) -> None:
        self.command = command
        self.args = args
        self.cwd = cwd
        self.timeout_sec = timeout_sec
        self._proc: subprocess.Popen[bytes] | None = None
        self._id = 0
        self._lock = threading.Lock()
        self._pending: dict[int, dict[str, Any]] = {}
        self._reader: threading.Thread | None = None
        self._stderr_chunks: list[str] = []

    def __enter__(self) -> McpStdioClient:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def start(self) -> None:
        if shutil.which(self.command) is None and not os.path.isfile(self.command):
            raise McpStdioError(f"找不到命令: {self.command}")
        self._proc = subprocess.Popen(
            [self.command, *self.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            cwd=self.cwd,
            env=os.environ.copy(),
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "workbuddy-ide-review-m0", "version": "0.1.0"},
            },
        )
        self.notify("notifications/initialized", {})

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._write(msg)

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        with self._lock:
            self._id += 1
            req_id = self._id
        msg: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            msg["params"] = params
        event = threading.Event()
        slot: dict[str, Any] = {"event": event, "result": None, "error": None}
        self._pending[req_id] = slot
        self._write(msg)
        if not event.wait(self.timeout_sec):
            self._pending.pop(req_id, None)
            raise McpStdioError(f"MCP 请求超时: {method}")
        if slot["error"] is not None:
            raise McpStdioError(f"MCP 错误 {method}: {slot['error']}")
        return slot["result"]

    def list_tools(self) -> list[dict[str, Any]]:
        result = self.request("tools/list", {})
        if not isinstance(result, dict):
            return []
        tools = result.get("tools") or []
        return tools if isinstance(tools, list) else []

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        return self.request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )

    def _write(self, msg: dict[str, Any]) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise McpStdioError("MCP 进程未启动")
        body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        try:
            proc.stdin.write(header + body)
            proc.stdin.flush()
        except Exception as e:
            raise McpStdioError(f"写入 MCP stdin 失败: {e}") from e

    def _read_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        stdout = proc.stdout
        while True:
            msg = self._read_one_message(stdout)
            if msg is None:
                break
            if "id" in msg and ("result" in msg or "error" in msg):
                slot = self._pending.pop(msg["id"], None)
                if slot is None:
                    continue
                if "error" in msg:
                    slot["error"] = msg["error"]
                else:
                    slot["result"] = msg.get("result")
                slot["event"].set()

    def _read_one_message(self, stdout: Any) -> dict[str, Any] | None:
        # Content-Length framing
        headers: dict[str, str] = {}
        while True:
            line = stdout.readline()
            if not line:
                return None
            if line in (b"\r\n", b"\n"):
                break
            try:
                text = line.decode("ascii", errors="replace").strip()
            except Exception:
                continue
            if ":" in text:
                k, v = text.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        if "content-length" in headers:
            try:
                length = int(headers["content-length"])
            except ValueError:
                return None
            raw = stdout.read(length)
            if not raw:
                return None
            try:
                data = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return None
            return data if isinstance(data, dict) else None

        return None

    def _read_stderr(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        while True:
            line = proc.stderr.readline()
            if not line:
                break
            try:
                self._stderr_chunks.append(line.decode("utf-8", errors="replace"))
            except Exception:
                continue
            if len(self._stderr_chunks) > 50:
                self._stderr_chunks = self._stderr_chunks[-50:]

    def stderr_tail(self) -> str:
        return "".join(self._stderr_chunks[-20:]).strip()


def default_mcp_command_args() -> tuple[str, list[str]]:
    cmd = (os.getenv("IDE_REVIEW_MCP_COMMAND") or "npx").strip()
    raw = (os.getenv("IDE_REVIEW_MCP_ARGS") or "-y,vscode-as-mcp-server").strip()
    args = [a for a in raw.split(",") if a.strip()]
    return cmd, args
