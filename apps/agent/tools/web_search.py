"""智谱 Web Search：联网检索新闻与公开信息。

对接智谱开放平台 Web Search API（与 cc-zhipu-web-search MCP 同源）：
POST {ZHIPU_BASE_URL}web_search

API Key 复用系统配置中的 ZHIPU_API_KEY；兼容 MCP 环境变量 BIGMODEL_API_KEY。
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Annotated, Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request

from safe_http import assert_http_url_allowed, urlopen_limited

logger = logging.getLogger(__name__)

SearchEngine = Literal[
    "search_std",
    "search_pro",
    "search_pro_sogou",
    "search_pro_quark",
]
RecencyFilter = Literal["oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"]
ContentSize = Literal["medium", "high"]

_KEY_MISSING_HINT = (
    "未配置智谱 API Key，无法联网搜索。"
    "请到「系统配置」填写 ZHIPU_API_KEY（或环境变量 BIGMODEL_API_KEY）。"
)


def _resolve_setting(key: str, default: str = "") -> str:
    try:
        from settings_store import resolve_setting

        return resolve_setting(key, default)
    except Exception:
        return os.getenv(key, default).strip()


def _api_key() -> str:
    try:
        from config import Config

        key = (getattr(Config, "ZHIPU_API_KEY", None) or "").strip()
        if key:
            return key
        key = (getattr(Config, "VISION_API_KEY", None) or "").strip()
        if key:
            return key
    except Exception:
        pass
    return (
        _resolve_setting("ZHIPU_API_KEY", "")
        or _resolve_setting("BIGMODEL_API_KEY", "")
        or _resolve_setting("VISION_API_KEY", "")
        or os.getenv("ZHIPU_API_KEY", "").strip()
        or os.getenv("BIGMODEL_API_KEY", "").strip()
        or os.getenv("VISION_API_KEY", "").strip()
    )


def _base_url() -> str:
    try:
        from config import Config

        raw = (getattr(Config, "ZHIPU_BASE_URL", None) or "").strip()
        if raw:
            return raw.rstrip("/") + "/"
        raw = (getattr(Config, "VISION_BASE_URL", None) or "").strip()
        if raw:
            return raw.rstrip("/") + "/"
    except Exception:
        pass
    raw = (
        _resolve_setting("ZHIPU_BASE_URL", "")
        or _resolve_setting("VISION_BASE_URL", "")
        or os.getenv("ZHIPU_BASE_URL", "").strip()
        or os.getenv("VISION_BASE_URL", "").strip()
        or "https://open.bigmodel.cn/api/paas/v4/"
    )
    return raw.rstrip("/") + "/"


def web_search_enabled() -> bool:
    flag = os.getenv("WEB_SEARCH_ENABLED", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    return bool(_api_key())


def _timeout_sec() -> float:
    raw = os.getenv("WEB_SEARCH_TIMEOUT_SEC", "30").strip()
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 30.0


def _call_zhipu_web_search(
    *,
    search_query: str,
    search_engine: SearchEngine = "search_std",
    count: int = 10,
    search_recency_filter: RecencyFilter = "noLimit",
    search_domain_filter: str | None = None,
    content_size: ContentSize | None = None,
    search_intent: bool = False,
) -> dict[str, Any]:
    api_key = _api_key()
    if not api_key:
        return {"error": _KEY_MISSING_HINT}

    endpoint = assert_http_url_allowed(
        f"{_base_url()}web_search",
        what="智谱联网搜索",
    )
    payload: dict[str, Any] = {
        "search_query": search_query,
        "search_engine": search_engine,
        "search_intent": search_intent,
        "count": count,
        "search_recency_filter": search_recency_filter,
        "request_id": str(uuid.uuid4()),
    }
    if search_domain_filter:
        payload["search_domain_filter"] = search_domain_filter.strip()
    if content_size:
        payload["content_size"] = content_size

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen_limited(req, timeout=_timeout_sec(), max_bytes=2_000_000) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            pass
        logger.warning("zhipu web_search HTTP %s: %s", exc.code, detail)
        return {"error": f"智谱搜索 HTTP {exc.code}", "detail": detail or str(exc)}
    except URLError as exc:
        logger.warning("zhipu web_search network error: %s", exc)
        return {"error": f"智谱搜索网络失败：{exc}"}
    except ValueError as exc:
        return {"error": str(exc)}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "智谱搜索返回非 JSON", "raw": raw[:300]}

    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        if isinstance(err, dict):
            return {
                "error": err.get("message") or err.get("code") or "智谱搜索失败",
                "code": err.get("code"),
            }
        return {"error": str(err)}

    return data if isinstance(data, dict) else {"error": "智谱搜索返回格式异常"}


def _format_results_markdown(results: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for idx, row in enumerate(results, start=1):
        title = str(row.get("title") or "（无标题）").strip()
        content = str(row.get("content") or "").strip()
        link = str(row.get("link") or "").strip()
        media = str(row.get("media") or "").strip()
        publish_date = str(row.get("publish_date") or "").strip()
        block = [f"{idx}. **{title}**"]
        if content:
            block.append(f"   {content}")
        meta: list[str] = []
        if media:
            meta.append(media)
        if publish_date:
            meta.append(publish_date)
        if link:
            meta.append(link)
        if meta:
            block.append(f"   来源：{' · '.join(meta)}")
        lines.append("\n".join(block))
    return "\n\n".join(lines)


def search_web(
    query: Annotated[str, "搜索关键词，建议不超过 70 字；用于新闻、行业动态、公开资料检索"],
    count: Annotated[int, "返回条数 1～50，默认 10"] = 10,
    search_recency_filter: Annotated[
        RecencyFilter,
        "时间范围：oneDay=一天内 oneWeek=一周内 oneMonth=一月内 oneYear=一年内 noLimit=不限",
    ] = "noLimit",
    search_engine: Annotated[
        SearchEngine,
        "搜索引擎：search_std 基础版；search_pro 高阶版；search_pro_sogou 搜狗；search_pro_quark 夸克",
    ] = "search_std",
    search_domain_filter: Annotated[
        str | None,
        "可选，限定域名白名单，如 www.example.com",
    ] = None,
) -> dict:
    """使用智谱 Web Search API 检索互联网公开信息（新闻、公告、行业报道等）。

    适用于「今日新闻」「PCB+AI 动态」「查最新资讯」等需联网的场景。
    结果含标题、摘要与链接；整理给用户时须保留来源，禁止编造未检索到的条目。
    """
    q = (query or "").strip()
    if not q:
        return {"error": "请提供搜索关键词 query"}
    truncated = False
    if len(q) > 70:
        q = q[:70]
        truncated = True

    n = max(1, min(int(count or 10), 50))
    raw = _call_zhipu_web_search(
        search_query=q,
        search_engine=search_engine,
        count=n,
        search_recency_filter=search_recency_filter,
        search_domain_filter=search_domain_filter,
    )
    if raw.get("error"):
        return {"ok": False, "query": q, **raw}

    results = raw.get("search_result") or []
    if not isinstance(results, list):
        results = []

    normalized: list[dict[str, str]] = []
    for row in results[:n]:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "title": str(row.get("title") or "").strip(),
                "content": str(row.get("content") or "").strip(),
                "link": str(row.get("link") or "").strip(),
                "media": str(row.get("media") or "").strip(),
                "publish_date": str(row.get("publish_date") or "").strip(),
            }
        )

    out: dict[str, Any] = {
        "ok": True,
        "query": q,
        "count": len(normalized),
        "results": normalized,
        "markdown": _format_results_markdown(normalized) if normalized else "（无匹配结果）",
        "hint": "整理给用户时保留标题、要点与来源链接；无结果时如实说明，勿编造。",
    }
    if truncated:
        out["query_truncated"] = True
    intent = raw.get("search_intent")
    if intent:
        out["search_intent"] = intent
    return out
