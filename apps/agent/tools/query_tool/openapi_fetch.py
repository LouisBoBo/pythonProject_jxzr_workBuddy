"""
从 URL 拉取 OpenAPI/Swagger 文档。

支持用户习惯填写的 Swagger UI 地址（如 http://127.0.0.1:8009/docs），
自动尝试同主机的 /openapi.json 等常见端点。
"""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request

from safe_http import assert_http_url_allowed, urlopen_limited


_MAX_BYTES = 16 * 1024 * 1024
_TIMEOUT_SEC = 25


def validate_docs_url(raw: str) -> str:
    return assert_http_url_allowed(raw, what="接口文档地址")


def openapi_candidate_urls(docs_url: str) -> list[str]:
    """根据用户输入生成待尝试的 OpenAPI 地址列表。"""
    base = validate_docs_url(docs_url)
    parsed = urlparse(base)
    path = (parsed.path or "").rstrip("/") or ""
    lower = path.lower()

    candidates: list[str] = []

    def add(u: str) -> None:
        u = u.rstrip("/")
        if u and u not in candidates:
            candidates.append(u)

    # 已是 openapi / swagger 文件
    if lower.endswith((".json", ".yaml", ".yml")) or "openapi" in lower or "swagger" in lower:
        add(base)
        return candidates

    # Swagger UI / ReDoc → 试同站 openapi
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if lower.endswith("/docs") or lower.endswith("/redoc") or lower in {"", "/"}:
        add(urljoin(origin + "/", "openapi.json"))
        add(urljoin(origin + "/", "openapi.yaml"))
        add(urljoin(origin + "/", "swagger.json"))
        add(urljoin(origin + "/", "v3/api-docs"))
        # 若 docs 挂在子路径，也试相对上级
        if lower.endswith("/docs") or lower.endswith("/redoc"):
            parent = path.rsplit("/", 1)[0]
            root = origin + (parent if parent else "")
            add(urljoin(root + "/", "openapi.json"))
        return candidates

    # 其它路径：先试原 URL，再试常见后缀
    add(base)
    add(urljoin(base + "/", "openapi.json"))
    add(f"{origin}/openapi.json")
    return candidates


def _looks_like_openapi(text: str) -> bool:
    s = (text or "").lstrip()
    if not s:
        return False
    if s.startswith("{"):
        try:
            data = json.loads(s)
        except json.JSONDecodeError:
            return False
        return isinstance(data, dict) and (
            "openapi" in data or "swagger" in data or isinstance(data.get("paths"), dict)
        )
    # YAML 粗判
    head = s[:200].lower()
    return "openapi:" in head or "swagger:" in head or "paths:" in head


def fetch_openapi_text(docs_url: str) -> tuple[str, str]:
    """
    拉取 OpenAPI 正文。
    返回 (text, used_url)。
    """
    errors: list[str] = []
    for url in openapi_candidate_urls(docs_url):
        try:
            req = Request(
                url,
                headers={
                    "Accept": "application/json, application/yaml, text/yaml, */*",
                    "User-Agent": "ZR-WorkBuddy-MES-Profile/1.0",
                },
                method="GET",
            )
            with urlopen_limited(req, timeout=_TIMEOUT_SEC, max_bytes=_MAX_BYTES) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            if not _looks_like_openapi(text):
                errors.append(f"{url}: 不是 OpenAPI/Swagger JSON")
                continue
            return text, url
        except HTTPError as exc:
            errors.append(f"{url}: HTTP {exc.code}")
        except URLError as exc:
            errors.append(f"{url}: {exc.reason}")
        except ValueError as exc:
            errors.append(f"{url}: {exc}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url}: {exc}")

    detail = "；".join(errors[:5]) if errors else "无候选地址"
    raise ValueError(
        "未能从该地址获取接口文档。"
        "可填该 MES 的 /docs 或直接填 /openapi.json。"
        f" 尝试结果：{detail}"
    )
