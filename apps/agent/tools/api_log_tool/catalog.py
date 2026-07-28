"""
接口目录：从 Swagger/OpenAPI URL 或上传文件构建统一索引。
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

from config import Config

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

def _catalog_dir() -> Path:
    d = Path(Config.DATA_DIR) / "api_catalog"
    d.mkdir(parents=True, exist_ok=True)
    return d


def index_path() -> Path:
    return _catalog_dir() / "api_index.json"


def meta_path() -> Path:
    return _catalog_dir() / "meta.json"


def _allowlist_hosts() -> set[str]:
    hosts = {"127.0.0.1", "localhost"}
    try:
        base = urlparse(Config.PLATFORM_BASE_URL)
        if base.hostname:
            hosts.add(base.hostname.lower())
    except Exception:
        pass
    extra = os.getenv("API_DOCS_URL_ALLOWLIST", "")
    for part in extra.split(","):
        h = part.strip().lower()
        if h:
            hosts.add(h)
    return hosts


def _host_allowed(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    return host in _allowlist_hosts()


def resolve_openapi_url(docs_url: str) -> str:
    """把文档页 URL 规范成「优先候选」的 OpenAPI 地址（完整候选见 resolve_openapi_url_candidates）。"""
    cands = resolve_openapi_url_candidates(docs_url)
    return cands[0]


def resolve_openapi_url_candidates(docs_url: str) -> list[str]:
    """根据文档页类型返回多个 OpenAPI 候选（按优先级）。

    - FastAPI/通用：/docs、/redoc → /openapi.json
    - SpringDoc / springfox：/swagger-ui.html → /v3/api-docs、/v2/api-docs …
    """
    raw = (docs_url or "").strip()
    if not raw:
        raise ValueError("docs_url 为空")
    if "#" in raw:
        raw = raw.split("#", 1)[0]
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"无效 URL: {docs_url}")
    path = (parsed.path or "").rstrip("/")
    lower = path.lower()
    origin = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))

    # 已是规范文件
    if lower.endswith(("openapi.json", "swagger.json", ".yaml", ".yml", "api-docs")):
        # .../v3/api-docs 或 .../openapi.json
        return [urlunparse((parsed.scheme, parsed.netloc, path or "/", "", "", ""))]

    cands: list[str] = []

    def add(rel: str) -> None:
        u = urljoin(origin + "/", rel.lstrip("/"))
        if u not in cands:
            cands.append(u)

    # Spring Swagger UI
    if "swagger-ui" in lower or lower.endswith("swagger-ui.html"):
        add("/v3/api-docs")
        add("/v3/api-docs/swagger-config")  # 可能是配置，后面会过滤
        add("/v2/api-docs")
        add("/swagger.json")
        add("/openapi.json")
        return cands

    # FastAPI / Scalar / 通用
    if lower.endswith("/docs") or lower.endswith("/redoc") or lower in ("", "/"):
        add("/openapi.json")
        add("/v3/api-docs")
        add("/swagger.json")
        return cands

    # 未知文档页：多试几种常见路径
    add("/openapi.json")
    add("/v3/api-docs")
    add("/v2/api-docs")
    add("/swagger.json")
    return cands


def _looks_like_openapi_spec(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if isinstance(data.get("paths"), dict):
        return True
    # springdoc swagger-config 等无 paths
    return False


def _fetch_openapi_spec(docs_url: str) -> tuple[Any, str]:
    """按候选列表拉取第一份可用的 OpenAPI/Swagger 规范。"""
    last_err: Exception | None = None
    tried: list[str] = []
    for url in resolve_openapi_url_candidates(docs_url):
        tried.append(url)
        try:
            data = _http_get_json(url)
        except Exception as e:
            last_err = e
            continue
        # swagger-config 可能返回 {url: "/v3/api-docs"} 
        if isinstance(data, dict) and not _looks_like_openapi_spec(data):
            nested = data.get("url") or data.get("configUrl")
            if isinstance(nested, str) and nested.strip():
                nested_url = urljoin(url, nested.strip())
                tried.append(nested_url)
                try:
                    data = _http_get_json(nested_url)
                    url = nested_url
                except Exception as e:
                    last_err = e
                    continue
        if _looks_like_openapi_spec(data):
            return data, url
        last_err = ValueError(f"响应不是 OpenAPI paths 规范: {url}")
    hint = (
        "已尝试: " + ", ".join(tried)
        + "。Spring 文档页请确认 /v3/api-docs 可访问，或直接传 openapi JSON 地址。"
    )
    detail = f"{last_err} | {hint}" if last_err is not None else hint
    raise RuntimeError(f"无法从文档 URL 解析 OpenAPI | {detail}")


def _http_get_json(url: str, timeout: float = 10.0) -> Any:
    if not _host_allowed(url):
        raise PermissionError(
            f"URL host 不在白名单: {urlparse(url).hostname}。"
            f"允许: {sorted(_allowlist_hosts())}；可用 API_DOCS_URL_ALLOWLIST 扩展"
        )
    req = Request(url, headers={"Accept": "application/json, application/yaml, text/plain"}, method="GET")
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        text = raw.decode("utf-8", errors="replace")
        ctype = (resp.headers.get("Content-Type") or "").lower()
    if "yaml" in ctype or url.lower().endswith((".yaml", ".yml")):
        if yaml is None:
            raise RuntimeError("需要 PyYAML 才能解析 YAML OpenAPI")
        return yaml.safe_load(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        if yaml is not None:
            return yaml.safe_load(text)
        raise


def _parse_openapi_spec(spec: Any) -> list[dict[str, Any]]:
    if not isinstance(spec, dict):
        raise ValueError("OpenAPI 根对象必须是 JSON object")
    paths = spec.get("paths") or {}
    if not isinstance(paths, dict):
        raise ValueError("OpenAPI 缺少 paths")
    http_methods = {"get", "post", "put", "patch", "delete", "head", "options"}
    out: list[dict[str, Any]] = []
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            m = str(method).lower()
            if m not in http_methods:
                continue
            if not isinstance(op, dict):
                op = {}
            tags = op.get("tags") if isinstance(op.get("tags"), list) else []
            out.append(
                {
                    "method": m.upper(),
                    "path": str(path),
                    "summary": (op.get("summary") or op.get("operationId") or "")[:200],
                    "tags": [str(t) for t in tags][:12],
                    "operation_id": str(op.get("operationId") or "")[:120],
                }
            )
    out.sort(key=lambda x: (x["path"], x["method"]))
    return out


_MD_ROW = re.compile(
    r"^\|\s*(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s*\|\s*([^\|]+)\|\s*(.*?)\s*\|?\s*$",
    re.I,
)


def _parse_markdown_table(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        m = _MD_ROW.match(line.strip())
        if not m:
            continue
        method, path, summary = m.group(1), m.group(2).strip(), m.group(3).strip()
        path = path.strip().strip("`")
        if not path.startswith("/"):
            continue
        rows.append(
            {
                "method": method.upper(),
                "path": path,
                "summary": summary[:200],
                "tags": [],
                "operation_id": "",
            }
        )
    return rows


def _load_spec_from_file(file_path: str) -> tuple[list[dict[str, Any]], str]:
    p = Path(file_path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    text = p.read_text(encoding="utf-8", errors="replace")
    suffix = p.suffix.lower()
    name_l = p.name.lower()
    # 有些环境文件名可能异常；用 name 兜底识别日志
    if suffix in (".jsonl", ".log") or name_l.endswith(".jsonl") or name_l.endswith(".log"):
        raise ValueError(
            f"不支持的文件类型: {suffix or Path(name_l).suffix or '.jsonl'}（这是访问日志）。"
            "请使用 import_external_api_logs 导入后再 analyze_api_errors_from_logs；"
            "OpenAPI 仅支持 .json/.yaml/.yml/.md/.txt"
        )
    if suffix in (".json", ".yaml", ".yml"):
        if suffix == ".json":
            spec = json.loads(text)
        else:
            if yaml is None:
                raise RuntimeError("需要 PyYAML 才能解析 YAML")
            spec = yaml.safe_load(text)
        return _parse_openapi_spec(spec), "openapi_file"
    if suffix in (".md", ".txt"):
        # 尝试整文件当 OpenAPI JSON；否则 Markdown 表
        try:
            spec = json.loads(text)
            return _parse_openapi_spec(spec), "openapi_file"
        except Exception:
            pass
        rows = _parse_markdown_table(text)
        if not rows:
            raise ValueError(
                "无法解析文件：请提供 OpenAPI JSON/YAML，或含 Method|Path|说明 的 Markdown 表格"
            )
        return rows, "markdown_table"
    raise ValueError(f"不支持的文件类型: {suffix}（支持 .json/.yaml/.yml/.md/.txt）")


def _save_index(
    endpoints: list[dict[str, Any]],
    *,
    source_type: str,
    source: str,
) -> dict[str, Any]:
    payload = {
        "version": 1,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "source_type": source_type,
        "source": source,
        "endpoint_count": len(endpoints),
        "endpoints": endpoints,
    }
    index_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = {
        "source_type": source_type,
        "source": source,
        "built_at": payload["built_at"],
        "endpoint_count": len(endpoints),
        "index": str(index_path()),
    }
    meta_path().write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def load_index() -> dict[str, Any] | None:
    p = index_path()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def build_catalog_from_url(docs_url: str) -> dict[str, Any]:
    spec, openapi_url = _fetch_openapi_spec(docs_url)
    endpoints = _parse_openapi_spec(spec)
    meta = _save_index(endpoints, source_type="url", source=openapi_url)
    return {
        "status": "ok",
        "docs_url": docs_url,
        "openapi_url": openapi_url,
        **meta,
        "sample": endpoints[:8],
        "note": (
            "已从 OpenAPI 构建接口目录；探活默认打沙箱（非文档 host）。"
            "请用 summarize_api_doc_vs_logs 对照调用日志。"
        ),
    }


def build_catalog_from_file(file_path: str) -> dict[str, Any]:
    endpoints, kind = _load_spec_from_file(file_path)
    meta = _save_index(endpoints, source_type="file", source=str(Path(file_path).resolve()))
    return {
        "status": "ok",
        "file_path": str(Path(file_path).resolve()),
        "parse_kind": kind,
        **meta,
        "sample": endpoints[:8],
        "note": "已从上传文件构建接口目录；请用 summarize_api_doc_vs_logs 对照调用日志。",
    }
