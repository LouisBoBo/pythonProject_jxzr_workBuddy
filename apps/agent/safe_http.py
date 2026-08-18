"""
出站 HTTP 约束：仅 http(s)、禁凭证、禁链路本地/元数据，且禁止跨主机跳转。
供 OpenAPI 拉取、WorkBuddy 登录转发、MES 查数共用。
"""
from __future__ import annotations

import ipaddress
import re
import socket
from typing import Any
from urllib.error import URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

_MAX_REDIRECTS = 5
_SAFE_PATH = re.compile(r"^/[A-Za-z0-9._~\-/]*$")
_SAFE_PARAM = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]{0,64}$")
_BLOCKED_NETWORKS = (
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.100.100.200/32"),
    ipaddress.ip_network("fd00:ec2::254/128"),
)
_BLOCKED_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "metadata.google.com",
        "metadata",
        "instance-data",
    }
)


def _reject_bad_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, seen: str = "") -> None:
    label = seen or str(ip)
    if ip.is_multicast or ip.is_unspecified or ip.is_link_local or ip.is_reserved:
        raise ValueError(f"不支持的接口文档主机地址：{label}" if seen else "不支持的接口文档主机地址")
    for net in _BLOCKED_NETWORKS:
        if ip in net:
            raise ValueError(f"不支持的接口文档主机地址：{label}" if seen else "不支持的接口文档主机地址")


def _host_allowed(hostname: str) -> None:
    host = (hostname or "").strip().lower().rstrip(".")
    if not host:
        raise ValueError("地址缺少主机名")
    if host in _BLOCKED_HOSTS:
        raise ValueError("不支持的接口文档主机地址")
    if host in {"localhost", "localhost.localdomain"}:
        return
    try:
        ip = ipaddress.ip_address(host)
        _reject_bad_ip(ip)
        return
    except ValueError as exc:
        if "不支持" in str(exc):
            raise
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError(f"无法解析主机名：{host}") from exc
    if not infos:
        raise ValueError(f"无法解析主机名：{host}")
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        _reject_bad_ip(ip, seen=addr)


def assert_http_url_allowed(raw: str, *, what: str = "地址") -> str:
    """校验并规范化 http(s) URL。禁止用户名密码、file、链路本地。"""
    text = (raw or "").strip()
    if not text:
        raise ValueError(f"请填写{what}")
    if "://" not in text:
        text = "http://" + text
    try:
        parsed = urlparse(text)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{what}无效：{exc}") from exc
    if (parsed.scheme or "").lower() not in {"http", "https"}:
        raise ValueError(f"{what}仅允许 http/https")
    if parsed.username or parsed.password:
        raise ValueError(f"{what}请勿携带账号密码")
    if not parsed.netloc:
        raise ValueError(f"{what}缺少主机名")
    _host_allowed(parsed.hostname or "")
    return text.rstrip("/")


def origin_of(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def same_http_origin(a: str, b: str) -> bool:
    oa, ob = origin_of(a).lower(), origin_of(b).lower()
    return bool(oa and ob and oa == ob)


def safe_request_path(raw: str) -> str | None:
    """只允许相对路径，禁止协议相对、..、查询串。"""
    s = (raw or "").strip()
    if not s:
        return None
    if s.startswith("//") or "://" in s or "?" in s or "#" in s:
        return None
    if not s.startswith("/"):
        s = "/" + s
    if ".." in s or "//" in s:
        return None
    if not _SAFE_PATH.match(s):
        return None
    return s.rstrip("/") or "/"


def safe_query_name(raw: str) -> str | None:
    s = str(raw or "").strip()
    if _SAFE_PARAM.match(s):
        return s
    return None


class SameHostRedirectHandler(HTTPRedirectHandler):
    max_repeats = _MAX_REDIRECTS
    max_redirections = _MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        old = urlparse(req.full_url)
        joined = urljoin(req.full_url, newurl)
        new = urlparse(joined)
        if (old.scheme.lower(), (old.netloc or "").lower()) != (
            new.scheme.lower(),
            (new.netloc or "").lower(),
        ):
            raise URLError("拒绝跨主机跳转")
        try:
            assert_http_url_allowed(joined, what="跳转地址")
        except ValueError as exc:
            raise URLError(str(exc)) from exc
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def urlopen_limited(req: Request, *, timeout: float = 15, max_bytes: int | None = None):
    """urlopen：同主机跳转上限，可选截断体积。"""
    opener = build_opener(SameHostRedirectHandler())
    resp = opener.open(req, timeout=timeout)
    if max_bytes is None:
        return resp
    raw = resp.read(max_bytes + 1)
    if len(raw) > max_bytes:
        resp.close()
        raise URLError("响应过大")

    class _Buf:
        def __init__(self, data: bytes, src: Any):
            self._data = data
            self.status = getattr(src, "status", None) or 200
            self.headers = getattr(src, "headers", None)

        def read(self, n: int = -1) -> bytes:  # noqa: ARG002
            return self._data

        def __enter__(self) -> "_Buf":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

    resp.close()
    return _Buf(raw, resp)
