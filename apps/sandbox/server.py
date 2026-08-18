#!/usr/bin/env python3
"""
API 探活沙箱 HTTP 服务（与生产 PLATFORM_BASE_URL 隔离）。

- 内存 REST：支持 GET/POST/PUT/PATCH/DELETE /api/v1/...
- 提供 /openapi.json 与 /docs，便于「根据沙箱文档测接口」
- 不写宿主业务目录（uploads/writes）；进程退出即丢数据

默认端口：8001（API_PROBE_SANDBOX_PORT）
"""
from __future__ import annotations

import base64
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

PORT = int(os.getenv("API_PROBE_SANDBOX_PORT", "8001"))
HOST = os.getenv("API_PROBE_SANDBOX_HOST", "127.0.0.1")

_LOCK = threading.RLock()
# collection path -> list of dict records
_STORE: dict[str, list[dict[str, Any]]] = {}
_SEQ = 0


def _next_id() -> str:
    global _SEQ
    _SEQ += 1
    return str(_SEQ)


OPENAPI: dict[str, Any] = {
    "openapi": "3.0.3",
    "info": {
        "title": "WorkBuddy API Probe Sandbox",
        "version": "1.0.0",
        "description": "本地探活沙箱（非生产）。数据仅存内存。",
    },
    "paths": {
        "/": {"get": {"summary": "Root", "tags": ["meta"], "responses": {"200": {"description": "ok"}}}},
        "/api/v1/auth/login": {
            "post": {
                "summary": "Login",
                "tags": ["auth"],
                "responses": {"200": {"description": "token"}},
            }
        },
        "/api/v1/probe-items/": {
            "get": {
                "summary": "探活样例列表",
                "tags": ["探活"],
                "responses": {"200": {"description": "ok"}},
            },
            "post": {
                "summary": "探活样例创建",
                "tags": ["探活"],
                "responses": {"201": {"description": "created"}},
            },
        },
        "/api/v1/probe-items/{item_id}": {
            "get": {
                "summary": "探活样例详情",
                "tags": ["探活"],
                "responses": {"200": {"description": "ok"}},
            },
            "put": {
                "summary": "探活样例更新",
                "tags": ["探活"],
                "responses": {"200": {"description": "ok"}},
            },
            "delete": {
                "summary": "探活样例删除",
                "tags": ["探活"],
                "responses": {"204": {"description": "deleted"}},
            },
        },
    },
}


_ACTION_SEGS = frozenset(
    {
        "create",
        "add",
        "save",
        "insert",
        "get",
        "getbyid",
        "query",
        "list",
        "detail",
        "details",
        "info",
        "find",
        "update",
        "edit",
        "modify",
        "put",
        "patch",
        "delete",
        "remove",
        "del",
    }
)


def _is_id_seg(seg: str) -> bool:
    s = seg or ""
    if s.isdigit():
        return True
    if s.startswith(("sandbox", "seed-")):
        return True
    return bool(
        re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            s,
        )
    )


def _is_action_seg(seg: str) -> bool:
    s = (seg or "").lower()
    if s in _ACTION_SEGS:
        return True
    return s.startswith(("update-", "get-", "delete-", "set-", "change-", "modify-"))


def _resource_bucket(path: str) -> tuple[str, str | None]:
    """同资源族共用桶。返回 (bucket, item_id|None)。

    /api/customers/create → (/api/customers, None)
    /api/customers/get/12 → (/api/customers, 12)
    /api/parts/123/alternates → (/api/parts/alternates, None)  # 父 id 剥掉
    /api/parts/alternates/9 → (/api/parts/alternates, 9)
    /api/parts/supplier/5 → (/api/parts/supplier, 5)
    """
    p = (path or "").split("?", 1)[0].rstrip("/") or "/"
    parts = [x for x in p.split("/") if x]
    if not parts:
        return "/", None

    item_id: str | None = None
    last = parts[-1]
    if _is_id_seg(last):
        item_id = last
        parts = parts[:-1]
    while parts and _is_action_seg(parts[-1]):
        parts.pop()
    # 中间父资源 id（如 /api/parts/123/alternates）不进桶名
    parts = [x for x in parts if not _is_id_seg(x)]
    bucket = "/" + "/".join(parts) if parts else "/"
    return bucket, item_id


def _is_item(path: str) -> tuple[bool, str, str | None]:
    bucket, item_id = _resource_bucket(path)
    p = path.split("?", 1)[0].rstrip("/") or "/"
    if p in ("/", "/health", "/docs", "/openapi.json", "/redoc"):
        return False, p, None
    if p == "/api/v1/auth/login":
        return False, p, None
    return bool(item_id), bucket, item_id


class Handler(BaseHTTPRequestHandler):
    server_version = "WorkBuddySandbox/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[sandbox] {self.address_string()} {fmt % args}")

    def _send(self, code: int, body: Any = None, content_type: str = "application/json") -> None:
        raw = b""
        if body is not None:
            if isinstance(body, (bytes, bytearray)):
                raw = bytes(body)
            elif content_type == "application/json":
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            else:
                raw = str(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if self.command != "HEAD" and raw:
            self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET(head_only=True)

    def do_GET(self, head_only: bool = False) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"

        if path in ("/",):
            return self._send(
                200,
                {
                    "service": "workbuddy-api-probe-sandbox",
                    "docs": "/docs",
                    "openapi": "/openapi.json",
                    "health": "/health",
                    "note": "内存沙箱，非生产",
                },
            )
        if path == "/health":
            return self._send(200, {"status": "ok", "sandbox": True, "ts": time.time()})
        if path == "/__reset":
            return self._send(405, {"error": "use POST /__reset", "sandbox": True})
        if path == "/openapi.json":
            return self._send(200, OPENAPI)
        if path in ("/docs", "/docs/"):
            html = """<!DOCTYPE html>
<html><head><title>Sandbox API Docs</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head><body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
SwaggerUIBundle({ url: '/openapi.json', dom_id: '#swagger-ui' });
</script>
<p style="font-family:sans-serif;padding:8px">WorkBuddy 探活沙箱（内存，非生产）</p>
</body></html>"""
            return self._send(200, html, "text/html; charset=utf-8")

        is_item, coll, item_id = _is_item(path)
        with _LOCK:
            items = _STORE.setdefault(coll, [])
            if is_item:
                found = next((x for x in items if str(x.get("id")) == str(item_id)), None)
                if not found:
                    return self._send(404, {"error": f"not found: {item_id}", "sandbox": True})
                return self._send(200, found)
            # list
            limit = 100
            qs = parse_qs(parsed.query)
            if "limit" in qs:
                try:
                    limit = max(1, min(int(qs["limit"][0]), 500))
                except Exception:
                    pass
            return self._send(200, items[:limit])

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = (parsed.path or "/").rstrip("/") or "/"
        body = self._read_json()

        if path == "/api/v1/auth/login":
            # 签发本地假 JWT（API 只读 payload 不验签），带上 sub，避免历史会话按 user_id 隔离后「消失」
            uname = str((body or {}).get("username") or "admin").strip() or "admin"
            # 与常见本地 ERP 一致：admin → user_id=1
            uid = "1" if uname.lower() == "admin" else str(abs(hash(uname)) % 100000)
            now = int(time.time())

            def _b64(obj: dict[str, Any]) -> str:
                raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
                return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

            token = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64({'sub': uid, 'preferred_username': uname, 'exp': now + 86400 * 30})}."
            return self._send(
                200,
                {
                    "access_token": token,
                    "token_type": "bearer",
                    "sandbox": True,
                },
            )

        if path == "/__reset":
            global _SEQ
            with _LOCK:
                _STORE.clear()
                _SEQ = 0
            return self._send(200, {"status": "ok", "reset": True, "sandbox": True})

        is_item, coll, _item_id = _is_item(path)
        # POST /.../create 或 REST 集合：写入资源族桶
        with _LOCK:
            items = _STORE.setdefault(coll, [])
            new_id = str(body.get("id") or _next_id())
            items[:] = [x for x in items if str(x.get("id")) != new_id]
            rec = dict(body)
            rec["id"] = new_id
            rec.setdefault("name", f"sandbox-{new_id}")
            rec["sandbox"] = True
            items.append(rec)
            return self._send(201, rec)

    def do_PUT(self) -> None:  # noqa: N802
        self._upsert(method="PUT")

    def do_PATCH(self) -> None:  # noqa: N802
        self._upsert(method="PATCH")

    def _upsert(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = (parsed.path or "/").rstrip("/") or "/"
        body = self._read_json()
        is_item, coll, item_id = _is_item(path)
        if not is_item or not item_id:
            return self._send(405, {"error": f"{method} requires item path", "sandbox": True})
        with _LOCK:
            items = _STORE.setdefault(coll, [])
            found = next((x for x in items if str(x.get("id")) == str(item_id)), None)
            if found:
                found.update(body)
                found["id"] = item_id
                found["sandbox"] = True
                return self._send(200, found)
            rec = dict(body)
            rec["id"] = item_id
            rec.setdefault("name", f"upsert-{item_id}")
            rec["sandbox"] = True
            items.append(rec)
            return self._send(201, rec)

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = (parsed.path or "/").rstrip("/") or "/"
        is_item, coll, item_id = _is_item(path)
        if not is_item or not item_id:
            return self._send(405, {"error": "DELETE requires item path", "sandbox": True})
        with _LOCK:
            items = _STORE.setdefault(coll, [])
            before = len(items)
            _STORE[coll] = [x for x in items if str(x.get("id")) != str(item_id)]
            if len(_STORE[coll]) < before:
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                return
            return self._send(404, {"error": f"not found: {item_id}", "sandbox": True})


def main() -> None:
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[sandbox] listening on http://{HOST}:{PORT}")
    print(f"[sandbox] docs     http://{HOST}:{PORT}/docs")
    print(f"[sandbox] openapi  http://{HOST}:{PORT}/openapi.json")
    print(f"[sandbox] health   http://{HOST}:{PORT}/health")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[sandbox] stopped")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
