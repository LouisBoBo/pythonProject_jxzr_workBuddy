"""
Agent 可调用的 API 日志 / 目录对照工具。
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Annotated, Any

from tools.api_log_tool.call_store import (
    default_since_ts,
    path_pattern_key,
    query_api_calls,
)
from tools.api_log_tool.catalog import (
    build_catalog_from_file,
    build_catalog_from_url,
    load_index,
)
from tools.api_log_tool.probe import run_catalog_probe
from tools.api_log_tool.log_import import import_log_file


def build_api_catalog(
    docs_url: Annotated[
        str | None,
        "用户提供的 Swagger/OpenAPI 文档 URL。"
        "FastAPI 例: http://127.0.0.1:8000/docs；"
        "Spring 例: http://localhost:8081/swagger-ui.html（会自动改拉 /v3/api-docs）。"
        "只用于建目录，不是探活目标。",
    ] = None,
    file_path: Annotated[
        str | None,
        "上传的接口文档本地路径（OpenAPI json/yaml，或 Method|Path|说明 Markdown 表）",
    ] = None,
) -> dict[str, Any]:
    """从文档 URL 或上传文件构建统一接口目录（二选一，优先 docs_url）。"""
    url = (docs_url or "").strip() or None
    path = (file_path or "").strip() or None
    if not url and not path:
        return {
            "error": "请提供 docs_url 或 file_path",
            "hint": "例如 docs_url='http://127.0.0.1:8000/docs' 或上传 openapi.json 后传 file_path",
        }
    try:
        if url:
            return build_catalog_from_url(url)
        return build_catalog_from_file(path or "")
    except Exception as e:
        msg = str(e)
        lower_path = (path or url or "").lower()
        if (
            lower_path.endswith((".jsonl", ".log"))
            or ".jsonl" in lower_path
            or lower_path.endswith(".log")
            or "访问日志" in msg
            or "jsonl" in msg.lower()
        ):
            return {
                "error": msg,
                "hint": (
                    "该文件是访问日志，不是 OpenAPI 文档。"
                    f"请改用 import_external_api_logs(file_path='{path or url}')，"
                    "再 analyze_api_errors_from_logs(source_filter='import')。"
                ),
                "next": "import_external_api_logs → analyze_api_errors_from_logs",
            }
        return {"error": msg}


def list_api_catalog(
    tag: Annotated[str | None, "按 OpenAPI tag 过滤"] = None,
    keyword: Annotated[str | None, "path/summary 关键字"] = None,
    offset: Annotated[int, "分页偏移"] = 0,
    limit: Annotated[int, "每页条数，默认 40，最大 100"] = 40,
) -> dict[str, Any]:
    """列出当前已构建的接口目录。"""
    index = load_index()
    if not index:
        return {
            "error": "尚未构建接口目录",
            "hint": "先 build_api_catalog(docs_url=...) 或 build_api_catalog(file_path=...)",
        }
    rows = list(index.get("endpoints") or [])
    if tag:
        t = tag.strip().lower()
        rows = [r for r in rows if any(t in str(x).lower() for x in (r.get("tags") or []))]
    if keyword:
        k = keyword.strip().lower()
        rows = [
            r
            for r in rows
            if k in str(r.get("path") or "").lower()
            or k in str(r.get("summary") or "").lower()
            or k in str(r.get("method") or "").lower()
        ]
    limit = max(1, min(int(limit or 40), 100))
    offset = max(0, int(offset or 0))
    total = len(rows)
    page = rows[offset : offset + limit]
    return {
        "source_type": index.get("source_type"),
        "source": index.get("source"),
        "built_at": index.get("built_at"),
        "total_matched": total,
        "returned": len(page),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
        "endpoints": page,
    }


def query_api_call_log(
    method: Annotated[str | None, "HTTP 方法过滤，如 GET"] = None,
    path_keyword: Annotated[str | None, "path 关键字"] = None,
    only_errors: Annotated[bool, "仅失败调用"] = False,
    source: Annotated[
        str | None,
        "日志来源过滤：erp / sandbox / probe / import；空=全部",
    ] = None,
    lookback_days: Annotated[int, "未指定 since 时的回溯天数，默认 7"] = 7,
    since: Annotated[str | None, "起始时间 YYYY-MM-DD"] = None,
    offset: Annotated[int, "分页偏移"] = 0,
    limit: Annotated[int, "每页条数，默认 30"] = 30,
) -> dict[str, Any]:
    """查询调用日志（助手出站 / 沙箱探活 / 外部导入）。"""
    since_ts = _parse_since(since, lookback_days)
    ok = False if only_errors else None
    page = query_api_calls(
        method=method,
        path_keyword=path_keyword,
        ok=ok,
        source=source,
        since_ts=since_ts,
        offset=offset,
        limit=limit,
    )
    page["since"] = datetime.fromtimestamp(since_ts).strftime("%Y-%m-%d %H:%M:%S") if since_ts else None
    page["note"] = (
        "来源：erp=助手出站，sandbox/probe=探活，import=外部日志导入。"
        "未见调用≠接口不可用。"
    )
    return page


def summarize_api_doc_vs_logs(
    lookback_days: Annotated[int, "回溯天数，默认 7"] = 7,
    error_rate_threshold: Annotated[float, "错误率阈值（0-1），默认 0.3"] = 0.3,
    slow_ms: Annotated[int, "慢调用阈值毫秒，默认 3000"] = 3000,
    top_n: Annotated[int, "问题接口返回条数，默认 15"] = 15,
    source_filter: Annotated[
        str | None,
        "仅统计该 source：erp / sandbox / import；空=全部来源合并",
    ] = None,
) -> dict[str, Any]:
    """对照当前接口目录与调用日志：可行 / 有问题 / 未见调用。"""
    index = load_index()
    if not index:
        return {
            "error": "尚未构建接口目录",
            "hint": "先 build_api_catalog(docs_url='http://127.0.0.1:8000/docs') 或上传 openapi 文件",
        }

    since_ts = default_since_ts(lookback_days)
    src = (source_filter or "").strip() or None
    # 拉取时间窗内全部调用（分页拼）
    calls: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = query_api_calls(since_ts=since_ts, offset=offset, limit=200, source=src)
        items = page.get("items") or []
        calls.extend(items)
        if not page.get("has_more") or not items:
            break
        offset += len(items)
        if offset > 20000:
            break

    # 按 method+path_key 聚合日志
    stats: dict[tuple[str, str], dict[str, Any]] = {}
    for c in calls:
        method = str(c.get("method") or "GET").upper()
        key = str(c.get("path_key") or path_pattern_key(str(c.get("path") or "")))
        st = stats.setdefault(
            (method, key),
            {"method": method, "path_key": key, "total": 0, "fail": 0, "slow": 0, "latencies": []},
        )
        st["total"] += 1
        if not c.get("ok", True):
            st["fail"] += 1
        try:
            lat = float(c.get("latency_ms") or 0)
        except Exception:
            lat = 0
        st["latencies"].append(lat)
        if lat >= float(slow_ms):
            st["slow"] += 1

    thr = max(0.0, min(float(error_rate_threshold or 0.3), 1.0))
    top_n = max(1, min(int(top_n or 15), 50))

    ok_list: list[dict[str, Any]] = []
    bad_list: list[dict[str, Any]] = []
    unseen: list[dict[str, Any]] = []
    doc_keys: set[tuple[str, str]] = set()

    for ep in index.get("endpoints") or []:
        method = str(ep.get("method") or "GET").upper()
        path = str(ep.get("path") or "")
        key = path_pattern_key(path)
        doc_keys.add((method, key))
        st = stats.get((method, key))
        base = {
            "method": method,
            "path": path,
            "path_key": key,
            "summary": ep.get("summary") or "",
            "tags": ep.get("tags") or [],
        }
        if not st or st["total"] <= 0:
            unseen.append({**base, "status": "unseen", "reason": "时间窗内无调用记录"})
            continue
        fail_rate = st["fail"] / max(st["total"], 1)
        p95 = _percentile(st["latencies"], 95)
        row = {
            **base,
            "calls": st["total"],
            "failures": st["fail"],
            "error_rate": round(fail_rate, 4),
            "slow_calls": st["slow"],
            "p95_ms": round(p95, 1) if p95 is not None else None,
        }
        # 低样本（≤3 次且仅 1 次失败）不标 problematic：多为探活占位 id / 历史噪声
        low_sample_noise = st["total"] <= 3 and st["fail"] == 1 and fail_rate >= thr
        if low_sample_noise:
            row["status"] = "healthy"
            row["reason"] = (
                f"调用仅 {st['total']} 次、失败 1 次（错误率看似 {fail_rate:.0%}），"
                "样本过小，不按缺陷计；若持续失败请再探活或查 inspect_api_path"
            )
            row["low_sample"] = True
            ok_list.append(row)
        elif fail_rate >= thr or st["fail"] >= 3 and fail_rate >= 0.1:
            row["status"] = "problematic"
            row["reason"] = f"错误率 {fail_rate:.0%}（阈值 {thr:.0%}）"
            bad_list.append(row)
        elif st["slow"] >= max(2, st["total"] // 3) or (p95 is not None and p95 >= slow_ms * 1.5):
            row["status"] = "problematic"
            row["reason"] = f"偏慢（慢调用 {st['slow']}，P95={row['p95_ms']}ms）"
            bad_list.append(row)
        else:
            row["status"] = "healthy"
            ok_list.append(row)

    # 日志有、文档无
    undocumented = []
    for (method, key), st in stats.items():
        if (method, key) in doc_keys:
            continue
        fail_rate = st["fail"] / max(st["total"], 1)
        undocumented.append(
            {
                "method": method,
                "path_key": key,
                "calls": st["total"],
                "failures": st["fail"],
                "error_rate": round(fail_rate, 4),
                "status": "undocumented",
            }
        )
    undocumented.sort(key=lambda x: (-x["failures"], -x["calls"]))
    bad_list.sort(key=lambda x: (-x["error_rate"], -x["failures"]))
    ok_list.sort(key=lambda x: -x["calls"])

    modules = _build_module_breakdown(index, ok_list, bad_list, unseen)
    probe_metrics = _probe_metrics_from_calls(calls, doc_keys=doc_keys, index=index)
    report = _compose_health_report_markdown(
        index=index,
        summary={
            "healthy": len(ok_list),
            "problematic": len(bad_list),
            "unseen": len(unseen),
            "undocumented_in_logs": len(undocumented),
            "endpoint_total": int(index.get("endpoint_count") or len(doc_keys)),
        },
        modules=modules,
        probe_metrics=probe_metrics,
        problematic=bad_list[:top_n],
        docs_display=_docs_display_from_index(index),
    )

    return {
        "catalog": {
            "source_type": index.get("source_type"),
            "source": index.get("source"),
            "built_at": index.get("built_at"),
            "endpoint_count": index.get("endpoint_count"),
            "docs_display": _docs_display_from_index(index),
        },
        "window": {
            "lookback_days": lookback_days,
            "since": datetime.fromtimestamp(since_ts).strftime("%Y-%m-%d %H:%M:%S"),
            "call_count": len(calls),
            "error_rate_threshold": thr,
            "slow_ms": slow_ms,
            "source_filter": src,
        },
        "summary": {
            "healthy": len(ok_list),
            "problematic": len(bad_list),
            "unseen": len(unseen),
            "undocumented_in_logs": len(undocumented),
            "endpoint_total": int(index.get("endpoint_count") or len(doc_keys)),
        },
        "modules": modules,
        "probe_metrics": probe_metrics,
        "problematic": bad_list[:top_n],
        "healthy_sample": ok_list[: min(10, top_n)],
        "unseen_sample": unseen[: min(20, top_n)],
        "undocumented_sample": undocumented[:10],
        "report_markdown": report,
        "path_key_rule": (
            "path_key 将数字/UUID/以及文档中的 {任意参数名} 统一为 {id}；"
            "{order_id} 与 {id} 是同一路径形态，不是路由写错。"
        ),
        "note": (
            "未见调用 ≠ 不可用（仅表示助手出站日志无证据）。"
            "有问题 = 错误率或延迟超阈值，须依据 status/error/latency，"
            "禁止用「文档参数名与 path_key 不同」推断接口故障。"
            "调用次数≤3 且仅失败 1 次的接口不标为缺陷（低样本噪声，常见于探活用了不存在的 id）。"
            "本结论不是表结构业务能力摸底。"
            "请优先采用 report_markdown 作为对用户回复骨架，可微调用语但勿删减模块与总览。"
        ),
    }


def rank_problematic_apis(
    lookback_days: Annotated[int, "回溯天数，默认 7"] = 7,
    top_n: Annotated[int, "返回条数，默认 20"] = 20,
    min_calls: Annotated[int, "最少调用次数，默认 1"] = 1,
    source_filter: Annotated[
        str | None,
        "仅统计该 source：erp / sandbox / import；空=全部",
    ] = None,
) -> dict[str, Any]:
    """仅按调用日志排行问题接口（可不依赖目录）。"""
    since_ts = default_since_ts(lookback_days)
    src = (source_filter or "").strip() or None
    calls: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = query_api_calls(since_ts=since_ts, offset=offset, limit=200, source=src)
        items = page.get("items") or []
        calls.extend(items)
        if not page.get("has_more") or not items:
            break
        offset += len(items)
        if offset > 20000:
            break

    buckets: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"total": 0, "fail": 0, "slow": 0, "latencies": [], "sample_error": "", "sample_status": None}
    )
    for c in calls:
        method = str(c.get("method") or "GET").upper()
        key = str(c.get("path_key") or path_pattern_key(str(c.get("path") or "")))
        b = buckets[(method, key)]
        b["total"] += 1
        if not c.get("ok", True):
            b["fail"] += 1
            if not b["sample_error"]:
                b["sample_error"] = str(c.get("error") or "")[:160]
            if b["sample_status"] is None:
                b["sample_status"] = c.get("status")
        try:
            lat = float(c.get("latency_ms") or 0)
        except Exception:
            lat = 0
        b["latencies"].append(lat)
        if lat >= 3000:
            b["slow"] += 1

    ranked = []
    for (method, key), b in buckets.items():
        if b["total"] < max(1, int(min_calls or 1)):
            continue
        rate = b["fail"] / max(b["total"], 1)
        if b["fail"] <= 0 and b["slow"] <= 0:
            continue
        ranked.append(
            {
                "method": method,
                "path_key": key,
                "calls": b["total"],
                "failures": b["fail"],
                "error_rate": round(rate, 4),
                "slow_calls": b["slow"],
                "p95_ms": round(_percentile(b["latencies"], 95) or 0, 1),
                "sample_error": b["sample_error"],
                "sample_status": b["sample_status"],
            }
        )
    ranked.sort(key=lambda x: (-x["error_rate"], -x["failures"], -x["slow_calls"]))
    return {
        "lookback_days": lookback_days,
        "since": datetime.fromtimestamp(since_ts).strftime("%Y-%m-%d %H:%M:%S"),
        "source_filter": src,
        "returned": min(len(ranked), max(1, min(int(top_n or 20), 50))),
        "items": ranked[: max(1, min(int(top_n or 20), 50))],
        "note": "仅基于调用日志；可与 summarize_api_doc_vs_logs 配合。外部导入请 source_filter='import'。",
    }


def inspect_api_path(
    path: Annotated[str, "接口 path 或关键字，如 /api/v1/work-orders"],
    method: Annotated[str | None, "可选方法，如 GET"] = None,
    lookback_days: Annotated[int, "回溯天数，默认 7"] = 7,
    limit: Annotated[int, "样例条数，默认 15"] = 15,
) -> dict[str, Any]:
    """查看某 path 的近期调用样例（含失败）。"""
    since_ts = default_since_ts(lookback_days)
    page = query_api_calls(
        method=method,
        path_keyword=path,
        since_ts=since_ts,
        offset=0,
        limit=max(1, min(int(limit or 15), 50)),
    )
    items = page.get("items") or []
    fails = [x for x in items if not x.get("ok", True)]
    return {
        "path_query": path,
        "method": method,
        "since": datetime.fromtimestamp(since_ts).strftime("%Y-%m-%d %H:%M:%S"),
        "returned": len(items),
        "failure_in_page": len(fails),
        "samples": [
            {
                "ts": x.get("ts"),
                "method": x.get("method"),
                "path": x.get("path"),
                "ok": x.get("ok"),
                "status": x.get("status"),
                "latency_ms": x.get("latency_ms"),
                "error": x.get("error"),
            }
            for x in items
        ],
        "note": page.get("note"),
    }


def probe_api_catalog(
    mode: Annotated[
        str,
        "文档接口测试一律默认 sandbox（不改生产，可含写）。禁止因「测试」自动改用 live；"
        "仅当用户明确要求「打生产/真实出站只读」时才传 live",
    ] = "sandbox",
    only_unseen: Annotated[
        bool,
        "仅探活未见调用的接口；文档全量测试默认 false",
    ] = False,
    lookback_days: Annotated[int, "判定「未见」的回溯天数，默认 7"] = 7,
    sample_id: Annotated[
        str | None,
        "路径模板通用占位值：替换所有 {param}；sandbox 默认每轮唯一 seed",
    ] = None,
    keyword: Annotated[str | None, "只探活 path/summary 含该关键字的接口"] = None,
    tag: Annotated[str | None, "只探活指定 OpenAPI tag"] = None,
    limit: Annotated[
        int,
        "最多探活条数；默认 0=目录全量（上限 200）。文档测试请用 0，不要为省事缩小而漏测",
    ] = 0,
    include_writes: Annotated[
        bool | None,
        "是否含写方法；sandbox 默认 true；live 禁止 true",
    ] = None,
    reset_sandbox: Annotated[
        bool, "仅 local_mock：探活前清空进程内沙箱内存；文档全量测试默认 true"
    ] = True,
) -> dict[str, Any]:
    """对接口目录做批量探活并写日志，供 summarize 分析。

    硬性约定：凡「根据文档/OpenAPI/Swagger 测试接口」一律走 sandbox，
    不得默认打生产。live 仅用于用户明确要求的生产只读核验。
    返回已压缩（失败全量 + 成功样例），避免超大结果诱发多轮追问触顶 recursion。
    """
    raw = run_catalog_probe(
        mode=mode,
        only_unseen=only_unseen,
        lookback_days=lookback_days,
        sample_id=sample_id,
        keyword=keyword,
        tag=tag,
        limit=limit,
        include_writes=include_writes,
        reset_sandbox=reset_sandbox,
    )
    return _compact_probe_payload(raw)


def import_external_api_logs(
    file_path: Annotated[
        str,
        "外部日志路径：优先用消息里的 [附件路径] 绝对路径；也可只传文件名（自动在 data/uploads 查找）。"
        "支持 Nginx access、JSONL、CSV。不要用 read_file 读上传目录。",
    ],
    format: Annotated[
        str,
        "日志格式：auto（默认自动识别）| jsonl | nginx | csv",
    ] = "auto",
    max_lines: Annotated[int, "最多导入行数，默认 5000，上限 20000"] = 5000,
    replace_previous: Annotated[
        bool,
        "默认 true：导入前清除旧的 source=import，避免上次日志污染本次结论",
    ] = True,
) -> dict[str, Any]:
    """导入网关/平台外部访问日志到 calls.jsonl（source=import），供错误分析。

    支持：
    - jsonl：每行 JSON，字段 method/path|uri|url、status、latency_ms、ts
    - nginx：combined 访问日志（可带 request_time）
    - csv：表头含 method,path,status,latency_ms,ts

    默认会替换旧导入，保证分析只反映本次文件中真实出现的接口。
    """
    path = (file_path or "").strip()
    if not path:
        return {"error": "请提供 file_path", "hint": "上传日志后传入本地绝对路径"}
    try:
        return import_log_file(
            path,
            format=format or "auto",
            max_lines=max_lines,
            source="import",
            replace_previous=bool(replace_previous),
        )
    except Exception as e:
        return {"error": str(e)}


def analyze_api_errors_from_logs(
    lookback_days: Annotated[int, "回溯天数，默认 7"] = 7,
    source_filter: Annotated[
        str,
        "默认 import（仅外部导入）。也可 erp / sandbox / 空字符串表示全部",
    ] = "import",
    top_n: Annotated[int, "问题接口条数，默认 20"] = 20,
    min_calls: Annotated[int, "最少调用次数，默认 1"] = 1,
    with_catalog: Annotated[
        bool,
        "默认 false。仅当用户同时要求对照接口文档、或传入 docs_url 时再 true。"
        "纯日志分析不要开，避免把历史目录的「文档 N 个接口」混进日志报告。",
    ] = False,
    docs_url: Annotated[
        str | None,
        "可选：用户明确要求对照文档时传入；会建目录并做附录对照。纯日志分析请留空。",
    ] = None,
    error_rate_threshold: Annotated[float, "错误率阈值，默认 0.3"] = 0.3,
) -> dict[str, Any]:
    """基于（导入的）调用日志分析 API 接口错误：排行 + 样例 + 好/坏接口总评。

    典型流程：用户上传网关日志 → import_external_api_logs([附件路径]) → 本工具。
    默认只分析本次导入日志，不把接口文档目录的接口总数写进主报告。
    文档沙箱探活请走 build_api_catalog → probe → render_api_health_report，勿与本工具混用。
    """
    src_raw = source_filter if source_filter is not None else "import"
    src = str(src_raw).strip()
    src_filter = src if src else None

    docs_url_s = (docs_url or "").strip()
    use_catalog = bool(with_catalog) or bool(docs_url_s)

    if docs_url_s:
        cat = build_api_catalog(docs_url=docs_url_s)
        if cat.get("error"):
            return {"status": "error", "stage": "catalog", "catalog": cat}

    since_ts = default_since_ts(lookback_days)
    thr = max(0.0, min(float(error_rate_threshold or 0.3), 1.0))

    # 拉取该来源全部调用，同时算好/坏
    calls: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = query_api_calls(since_ts=since_ts, offset=offset, limit=200, source=src_filter)
        items = page.get("items") or []
        calls.extend(items)
        if not page.get("has_more") or not items:
            break
        offset += len(items)
        if offset > 20000:
            break

    buckets: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "total": 0,
            "fail": 0,
            "slow": 0,
            "latencies": [],
            "sample_error": "",
            "sample_status": None,
            "sample_ok_path": "",
        }
    )
    for c in calls:
        method = str(c.get("method") or "GET").upper()
        key = str(c.get("path_key") or path_pattern_key(str(c.get("path") or "")))
        b = buckets[(method, key)]
        b["total"] += 1
        try:
            lat = float(c.get("latency_ms") or 0)
        except Exception:
            lat = 0.0
        # 过滤明显异常延迟噪声（>10分钟多为错误单位历史数据）
        if 0 < lat < 600_000:
            b["latencies"].append(lat)
        elif lat >= 600_000:
            b["latencies"].append(lat)  # 仍记录，报告里会标注异常
        if not c.get("ok", True):
            b["fail"] += 1
            if not b["sample_error"]:
                b["sample_error"] = str(c.get("error") or "")[:160]
            if b["sample_status"] is None:
                b["sample_status"] = c.get("status")
        else:
            if not b["sample_ok_path"]:
                b["sample_ok_path"] = str(c.get("path") or "")
        if lat >= 3000:
            b["slow"] += 1

    error_apis: list[dict[str, Any]] = []
    healthy_apis: list[dict[str, Any]] = []
    for (method, key), b in buckets.items():
        if b["total"] < max(1, int(min_calls or 1)):
            continue
        rate = b["fail"] / max(b["total"], 1)
        p95 = round(_percentile(b["latencies"], 95) or 0, 1)
        row = {
            "method": method,
            "path_key": key,
            "calls": b["total"],
            "failures": b["fail"],
            "error_rate": round(rate, 4),
            "slow_calls": b["slow"],
            "p95_ms": p95,
            "sample_error": b["sample_error"],
            "sample_status": b["sample_status"],
        }
        # 低样本单次失败不进错误榜（与 summarize 一致）
        low_noise = b["total"] <= 3 and b["fail"] == 1 and rate >= thr
        is_bad = (not low_noise) and (rate >= thr or (b["fail"] >= 3 and rate >= 0.1) or b["slow"] >= max(2, b["total"] // 3))
        if is_bad and b["fail"] > 0:
            error_apis.append(row)
        elif b["fail"] == 0:
            healthy_apis.append(row)
        elif low_noise:
            row["note"] = "低样本单次失败，暂不计入错误榜"
            healthy_apis.append(row)
        else:
            # 有失败但未达阈值 → 仍算「基本正常」并备注
            row["note"] = f"有失败但错误率 {rate:.0%} 未超阈值"
            healthy_apis.append(row)

    error_apis.sort(key=lambda x: (-x["error_rate"], -x["failures"]))
    healthy_apis.sort(key=lambda x: (-x["calls"], x["path_key"]))

    # —— 文档对照仅在用户明确要求时启用；默认纯日志，避免把历史目录「62 个接口」串进日志报告 ——
    doc_keys: set[tuple[str, str]] = set()
    catalog_endpoints: list[dict[str, Any]] = []
    index = load_index() if use_catalog else None
    if index:
        for ep in index.get("endpoints") or []:
            method = str(ep.get("method") or "GET").upper()
            path = str(ep.get("path") or "")
            key = path_pattern_key(path)
            doc_keys.add((method, key))
            catalog_endpoints.append(
                {
                    "method": method,
                    "path": path,
                    "path_key": key,
                    "summary": ep.get("summary") or "",
                    "tags": ep.get("tags") or [],
                }
            )

    undocumented_apis: list[dict[str, Any]] = []
    if doc_keys:
        kept_err: list[dict[str, Any]] = []
        kept_ok: list[dict[str, Any]] = []
        for row in error_apis:
            mk = (str(row["method"]).upper(), str(row["path_key"]))
            if mk in doc_keys:
                row["in_catalog"] = True
                kept_err.append(row)
            else:
                row["in_catalog"] = False
                undocumented_apis.append(row)
        for row in healthy_apis:
            mk = (str(row["method"]).upper(), str(row["path_key"]))
            if mk in doc_keys:
                row["in_catalog"] = True
                kept_ok.append(row)
            else:
                row["in_catalog"] = False
                undocumented_apis.append(row)
        error_apis = kept_err
        healthy_apis = kept_ok

    # 文档有、本次日志未见（仅附录用）
    seen_keys = {(str(m).upper(), str(k)) for (m, k) in buckets.keys()}
    unseen_in_docs: list[dict[str, Any]] = []
    if catalog_endpoints:
        for ep in catalog_endpoints:
            mk = (ep["method"], ep["path_key"])
            if mk not in seen_keys:
                unseen_in_docs.append(ep)

    ranked_items = error_apis[: max(1, min(int(top_n or 20), 50))]

    err_page = query_api_calls(
        ok=False,
        source=src_filter,
        since_ts=since_ts,
        offset=0,
        limit=min(30, max(5, int(top_n or 20))),
    )
    samples = []
    for x in err_page.get("items") or []:
        method = str(x.get("method") or "GET").upper()
        key = str(x.get("path_key") or path_pattern_key(str(x.get("path") or "")))
        if doc_keys and (method, key) not in doc_keys:
            continue
        samples.append(
            {
                "ts": x.get("ts"),
                "method": x.get("method"),
                "path": x.get("path"),
                "path_key": x.get("path_key"),
                "status": x.get("status"),
                "error": x.get("error"),
                "latency_ms": x.get("latency_ms"),
                "source": x.get("source"),
            }
        )

    status_hist: dict[str, int] = defaultdict(int)
    for x in samples:
        status_hist[str(x.get("status") or "unknown")] += 1

    catalog_part: dict[str, Any] | None = None
    catalog_summary: dict[str, Any] = {}
    docs_display = ""
    if use_catalog and index:
        health = summarize_api_doc_vs_logs(
            lookback_days=lookback_days,
            source_filter=src_filter,
            top_n=top_n,
            error_rate_threshold=thr,
        )
        catalog_part = {
            "summary": health.get("summary"),
            "problematic": health.get("problematic"),
            "modules": health.get("modules"),
            "undocumented_sample": health.get("undocumented_sample"),
        }
        docs_display = _docs_display_from_index(index)
        catalog_summary = {
            **(health.get("summary") or {}),
            "catalog_total": len(catalog_endpoints),
            "log_hit": len(seen_keys & doc_keys) if doc_keys else len(seen_keys),
            "unseen_in_docs": len(unseen_in_docs),
            "undocumented_in_logs": len(undocumented_apis),
        }

    report_md = _compose_error_analysis_report(
        source_filter=src_filter or "all",
        ranked=ranked_items,
        healthy_apis=healthy_apis[:30],
        samples=samples,
        status_hist=dict(status_hist),
        catalog_summary=catalog_summary,
        docs_display=docs_display,
        lookback_days=lookback_days,
        call_count=len(calls),
        endpoint_count=len(buckets),
        unseen_in_docs=unseen_in_docs if use_catalog else [],
        undocumented_apis=undocumented_apis if use_catalog else [],
        catalog_total=len(catalog_endpoints) if use_catalog else 0,
        with_catalog=use_catalog,
    )

    return {
        "status": "ok",
        "source_filter": src_filter,
        "lookback_days": lookback_days,
        "call_count": len(calls),
        "endpoint_count": len(buckets),
        "with_catalog": use_catalog,
        "catalog_total": len(catalog_endpoints) if use_catalog else 0,
        "error_apis": ranked_items,
        "healthy_apis": healthy_apis[:30],
        "unseen_in_docs_count": len(unseen_in_docs) if use_catalog else 0,
        "unseen_in_docs": unseen_in_docs[:40] if use_catalog else [],
        "undocumented_apis": undocumented_apis[:20] if use_catalog else [],
        "error_rank": ranked_items,
        "error_samples": samples,
        "status_histogram": dict(status_hist),
        "catalog_contrast": catalog_part,
        "report_markdown": report_md,
        "reply_hint": (
            "请把 report_markdown 作为最终回复主体。"
            "本报告以「本次导入日志」为准（调用条数 / 错误与正常接口）；"
            "不要把接口文档的接口总数说成日志里的接口数。"
            "文档沙箱探活请用 render_api_health_report，勿与本报告混谈。"
        ),
    }


def _compose_error_analysis_report(
    *,
    source_filter: str,
    ranked: list[dict[str, Any]],
    healthy_apis: list[dict[str, Any]],
    samples: list[dict[str, Any]],
    status_hist: dict[str, int],
    catalog_summary: dict[str, Any],
    docs_display: str,
    lookback_days: int,
    call_count: int = 0,
    endpoint_count: int = 0,
    unseen_in_docs: list[dict[str, Any]] | None = None,
    undocumented_apis: list[dict[str, Any]] | None = None,
    catalog_total: int = 0,
    with_catalog: bool = False,
) -> str:
    src_label = {
        "import": "外部导入日志（source=import）",
        "erp": "助手出站日志（source=erp）",
        "sandbox": "沙箱探活日志（source=sandbox）",
        "all": "全部来源合并",
    }.get(source_filter, f"source={source_filter}")

    unseen_in_docs = unseen_in_docs or []
    undocumented_apis = undocumented_apis or []
    cat_total = int(catalog_total or catalog_summary.get("catalog_total") or 0) if with_catalog else 0
    log_hit = int(catalog_summary.get("log_hit") or (len(ranked) + len(healthy_apis))) if with_catalog else 0

    # —— 主报告只谈「本次日志」，文档数字绝不进覆盖行 ——
    lines = [
        "## API 接口错误分析",
        "",
        f"**证据来源**：{src_label}（近 {lookback_days} 天）",
        "**分析范围**：仅本次导入日志中出现的调用；与接口文档目录相互独立，不把文档接口总数当作日志接口数。",
        f"**本次日志**：共 **{call_count}** 条调用，归并为 **{endpoint_count}** 个接口"
        f"（同一 path 模板多次调用合并统计）。",
    ]

    lines.extend(["", "### 结果总览", ""])
    err_n = len(ranked)
    ok_n = len(healthy_apis)
    lines.extend(
        [
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 日志调用条数 | **{call_count}** |",
            f"| 日志中的接口数 | **{endpoint_count or (err_n + ok_n)}** |",
            f"| ❌ 错误接口 | **{err_n}** |",
            f"| ✅ 正常接口 | **{ok_n}** |",
            f"| 失败样例 | {len(samples)} |",
            "",
        ]
    )

    if status_hist:
        hist = "、".join(f"{k}×{v}" for k, v in sorted(status_hist.items(), key=lambda x: -x[1]))
        lines.append(f"**失败状态码分布（样例集）**：{hist}")
        lines.append("")

    lines.extend(["### 错误接口排行", ""])
    if not ranked:
        lines.append("未发现满足条件的问题接口（无失败/无偏慢，或调用量不足）。")
    else:
        for i, p in enumerate(ranked[:15], 1):
            p95 = p.get("p95_ms")
            try:
                p95_f = float(p95 or 0)
            except Exception:
                p95_f = 0.0
            p95_s = f"{p95_f:.0f}ms" if p95_f < 600_000 else f"{p95_f:.0f}ms（异常偏大，请核对日志时间单位）"
            lines.append(
                f"{i}. ❌ `{p.get('method')} {p.get('path_key')}` — "
                f"错误率 {float(p.get('error_rate') or 0):.0%} "
                f"（失败 {p.get('failures')}/{p.get('calls')}），"
                f"P95={p95_s}"
                + (f"，status={p.get('sample_status')}" if p.get("sample_status") is not None else "")
                + (f"，{p.get('sample_error')}" if p.get("sample_error") else "")
            )

    if samples:
        lines.extend(["", "### 失败调用样例", ""])
        for s in samples[:10]:
            lat = s.get("latency_ms")
            try:
                lat_f = float(lat or 0)
            except Exception:
                lat_f = 0.0
            lat_s = f"{lat_f:.1f}ms" if lat_f < 600_000 else f"{lat_f:.0f}ms（异常偏大，请核对日志时间单位）"
            lines.append(
                f"- `{s.get('method')} {s.get('path')}` → "
                f"status={s.get('status')}，{s.get('error') or 'error'}，{lat_s}"
            )

    lines.extend(["", "### 总体评估", ""])
    lines.append("#### ❌ 错误接口（需处理）")
    lines.append("")
    if ranked:
        lines.extend(
            [
                "| 接口 | 方法 | 调用 | 失败 | 错误率 | 说明 |",
                "|------|------|------|------|--------|------|",
            ]
        )
        for p in ranked:
            err_txt = str(p.get("sample_error") or "")[:40]
            if not err_txt and p.get("sample_status") is not None:
                err_txt = f"status={p.get('sample_status')}"
            lines.append(
                f"| `{p.get('path_key')}` | {p.get('method')} | {p.get('calls')} | "
                f"**{p.get('failures')}** | **{float(p.get('error_rate') or 0):.0%}** | "
                f"{err_txt} |"
            )
    else:
        lines.append("无。")

    lines.extend(["", "#### ✅ 正常接口（本次日志内）", ""])
    if healthy_apis:
        lines.extend(
            [
                "| 接口 | 方法 | 调用 | 失败 | 错误率 |",
                "|------|------|------|------|--------|",
            ]
        )
        for p in healthy_apis[:25]:
            note = f" {p.get('note')}" if p.get("note") else ""
            lines.append(
                f"| `{p.get('path_key')}` | {p.get('method')} | {p.get('calls')} | "
                f"{p.get('failures')} | {float(p.get('error_rate') or 0):.0%}{note} |"
            )
        if len(healthy_apis) > 25:
            lines.append(f"| … | | | | 另有 {len(healthy_apis) - 25} 个正常接口未列出 |")
    else:
        lines.append("本次日志未覆盖到「零失败/未达阈值」的其它接口。")

    lines.extend(["", "#### 结论", ""])
    if ranked:
        names = "、".join(f"`{p.get('method')} {p.get('path_key')}`" for p in ranked[:5])
        ok_names = "、".join(f"`{p.get('method')} {p.get('path_key')}`" for p in healthy_apis[:5])
        lines.append(
            f"- **错误（{len(ranked)}）**：{names}"
            + (" …" if len(ranked) > 5 else "")
        )
        if healthy_apis:
            lines.append(
                f"- **正常（{len(healthy_apis)}）**：{ok_names}"
                + (" …" if len(healthy_apis) > 5 else "")
            )
        else:
            lines.append("- **正常**：本次日志内无其它稳定成功接口。")
        lines.append(
            f"- **优先处理**：`{ranked[0].get('method')} {ranked[0].get('path_key')}`"
            f"（错误率 {float(ranked[0].get('error_rate') or 0):.0%}）。"
        )
    else:
        lines.append(
            f"本次日志中的 {ok_n or endpoint_count} 个接口均未达到错误阈值，"
            "可视为当前样本下运行正常。"
        )

    # —— 可选附录：仅当用户明确要求对照文档时出现；与「文档探活报告」仍是两回事 ——
    if with_catalog and cat_total:
        lines.extend(
            [
                "",
                "### 附录：与接口文档对照（可选）",
                "",
                f"以下为**额外对照**，**不是**本次日志的接口清单。"
                f"接口文档另有 **{cat_total}** 个接口（`{docs_display or '已建目录'}`）；"
                f"本次日志命中其中 {log_hit} 个。"
                "完整文档探活请使用「根据 docs 测试接口」流程（`render_api_health_report`），"
                "勿将文档接口总数与日志条数混为一谈。",
            ]
        )
        if undocumented_apis:
            lines.extend(["", "日志有但当前文档目录无（仅提示）："])
            for p in undocumented_apis[:10]:
                lines.append(
                    f"- `{p.get('method')} {p.get('path_key')}` "
                    f"（调用 {p.get('calls')}，失败 {p.get('failures')}）"
                )
        if unseen_in_docs and len(unseen_in_docs) <= 15:
            lines.extend(["", "文档有但本次日志未见（≠故障）："])
            for ep in unseen_in_docs[:10]:
                lines.append(
                    f"- `{ep.get('method')} {ep.get('path') or ep.get('path_key')}`"
                )
        elif unseen_in_docs:
            lines.append(
                f"文档中另有 **{len(unseen_in_docs)}** 个接口本次日志未见调用（≠故障，此处不展开）。"
            )

    lines.append("")
    return "\n".join(lines)


def render_api_health_report(
    docs_url: Annotated[
        str | None,
        "用户原始文档 URL（仅用于报告展示，可空；空则用目录 source）",
    ] = None,
    lookback_days: Annotated[int, "与 summarize 一致的回溯天数，默认 7"] = 7,
) -> dict[str, Any]:
    """生成专业中文接口文档测试报告（Markdown）。

    须在 build → list → probe → summarize → rank 之后调用；
    对用户回复应直接采用返回的 report_markdown（可微调措辞，勿删模块与总览表）。
    """
    index = load_index()
    if not index:
        return {"error": "尚未构建接口目录", "hint": "先 build_api_catalog"}

    health = summarize_api_doc_vs_logs(lookback_days=lookback_days)
    if health.get("error"):
        return health

    display = (docs_url or "").strip() or _docs_display_from_index(index)
    report = _compose_health_report_markdown(
        index=index,
        summary=health.get("summary") or {},
        modules=health.get("modules") or [],
        probe_metrics=health.get("probe_metrics") or {},
        problematic=health.get("problematic") or [],
        docs_display=display,
    )
    return {
        "status": "ok",
        "docs_display": display,
        "summary": health.get("summary"),
        "modules": health.get("modules"),
        "probe_metrics": health.get("probe_metrics"),
        "problematic": health.get("problematic"),
        "report_markdown": report,
        "reply_hint": (
            "请把 report_markdown 原样或略作润色后作为最终回复；"
            "保持「接口文档测试结论」标题、总览表、业务模块列表、结论段。"
            "说明探活在沙箱、未改生产。"
        ),
    }


def _docs_display_from_index(index: dict[str, Any]) -> str:
    src = str(index.get("source") or "")
    if "/v3/api-docs" in src:
        base = src.split("/v3/api-docs", 1)[0]
        return f"{base}/swagger-ui.html（自动解析为 `/v3/api-docs`）"
    if src.endswith("/openapi.json"):
        base = src[: -len("/openapi.json")]
        return f"{base}/docs（自动解析为 `/openapi.json`）"
    return src or "（未记录文档来源）"


def _capability_phrases(endpoints: list[dict[str, Any]]) -> str:
    """从 summary / path 提炼业务能力短语。"""
    phrases: list[str] = []
    seen: set[str] = set()
    for ep in endpoints:
        summary = str(ep.get("summary") or "").strip()
        if summary:
            # 去掉「接口」等尾巴，保留业务动作
            label = summary.replace("接口", "").strip() or summary
        else:
            path = str(ep.get("path") or "")
            segs = [x for x in path.split("/") if x and not x.startswith("{")]
            label = segs[-1] if segs else str(ep.get("method") or "操作")
        if label and label not in seen:
            seen.add(label)
            phrases.append(label)
        if len(phrases) >= 8:
            break
    return "、".join(phrases) if phrases else "相关读写接口"


def _build_module_breakdown(
    index: dict[str, Any],
    ok_list: list[dict[str, Any]],
    bad_list: list[dict[str, Any]],
    unseen: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    status_map: dict[tuple[str, str], str] = {}
    for row in ok_list:
        status_map[(row["method"], row["path_key"])] = "healthy"
    for row in bad_list:
        status_map[(row["method"], row["path_key"])] = "problematic"
    for row in unseen:
        status_map[(row["method"], row["path_key"])] = "unseen"

    buckets: dict[str, dict[str, Any]] = {}
    for ep in index.get("endpoints") or []:
        tags = ep.get("tags") or []
        mod = str(tags[0]) if tags else "未分类"
        method = str(ep.get("method") or "GET").upper()
        path = str(ep.get("path") or "")
        key = path_pattern_key(path)
        b = buckets.setdefault(
            mod,
            {
                "module": mod,
                "endpoint_count": 0,
                "healthy": 0,
                "problematic": 0,
                "unseen": 0,
                "methods": defaultdict(int),
                "endpoints": [],
            },
        )
        b["endpoint_count"] += 1
        b["methods"][method] += 1
        b["endpoints"].append(ep)
        st = status_map.get((method, key), "unseen")
        b[st] = int(b.get(st) or 0) + 1

    out = []
    for mod, b in sorted(buckets.items(), key=lambda x: (-x[1]["endpoint_count"], x[0])):
        caps = _capability_phrases(b["endpoints"])
        out.append(
            {
                "module": mod,
                "endpoint_count": b["endpoint_count"],
                "healthy": b["healthy"],
                "problematic": b["problematic"],
                "unseen": b["unseen"],
                "methods": dict(b["methods"]),
                "capabilities": caps,
                "pass_rate": round(
                    b["healthy"] / max(b["endpoint_count"], 1),
                    4,
                ),
            }
        )
    return out


def _probe_metrics_from_calls(
    calls: list[dict[str, Any]],
    *,
    doc_keys: set[tuple[str, str]] | None = None,
    index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """从近期调用中提取 sandbox/probe 探活指标（仅统计目录内接口，排除预置噪声）。"""
    probe_calls = [
        c
        for c in calls
        if str(c.get("source") or "") in ("sandbox", "probe")
    ]
    if not probe_calls:
        probe_calls = list(calls)

    matched: list[dict[str, Any]] = []
    for c in probe_calls:
        method = str(c.get("method") or "GET").upper()
        key = str(c.get("path_key") or path_pattern_key(str(c.get("path") or "")))
        if doc_keys is not None and (method, key) not in doc_keys:
            continue
        matched.append(c)
    if not matched:
        matched = probe_calls

    # 每个 method+path_key 取最近一次（避免预置+正式重复计数失真）
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for c in matched:
        method = str(c.get("method") or "GET").upper()
        key = str(c.get("path_key") or path_pattern_key(str(c.get("path") or "")))
        latest[(method, key)] = c
    uniq = list(latest.values())

    ok_n = sum(1 for c in uniq if c.get("ok", True))
    fail_n = len(uniq) - ok_n
    lats: list[float] = []
    for c in uniq:
        try:
            lats.append(float(c.get("latency_ms") or 0))
        except Exception:
            pass

    # 方法分布：以文档目录为准（更专业）
    methods: dict[str, int] = defaultdict(int)
    for ep in (index or {}).get("endpoints") or []:
        methods[str(ep.get("method") or "GET").upper()] += 1
    if not methods:
        for c in uniq:
            methods[str(c.get("method") or "?").upper()] += 1

    kinds = sorted(
        {
            str(c.get("sandbox_kind") or "")
            for c in matched
            if c.get("sandbox_kind")
        }
    )
    return {
        "probe_calls": len(uniq),
        "ok": ok_n,
        "failed": fail_n,
        "p50_ms": round(_percentile(lats, 50) or 0, 1) if lats else None,
        "p95_ms": round(_percentile(lats, 95) or 0, 1) if lats else None,
        "max_ms": round(max(lats), 1) if lats else None,
        "methods": dict(methods),
        "sandbox_kinds": kinds,
    }


def _compose_health_report_markdown(
    *,
    index: dict[str, Any],
    summary: dict[str, Any],
    modules: list[dict[str, Any]],
    probe_metrics: dict[str, Any],
    problematic: list[dict[str, Any]],
    docs_display: str,
) -> str:
    total = int(
        summary.get("endpoint_total")
        or index.get("endpoint_count")
        or sum(int(m.get("endpoint_count") or 0) for m in modules)
    )
    healthy = int(summary.get("healthy") or 0)
    bad = int(summary.get("problematic") or 0)
    unseen = int(summary.get("unseen") or 0)
    probed_ok = int(probe_metrics.get("ok") or healthy)
    probed_fail = int(probe_metrics.get("failed") or 0)
    # 探活通过数：优先用 probe 成功次数对应的目录覆盖；展示用 healthy 与 probe 对齐
    pass_n = healthy if healthy else probed_ok
    fail_show = bad if bad else probed_fail

    sandbox_note = "沙箱（未触碰生产环境）"
    kinds = probe_metrics.get("sandbox_kinds") or []
    if "remote_url" in kinds:
        import os

        sb = (os.getenv("API_PROBE_SANDBOX_URL") or "http://127.0.0.1:8001").rstrip("/")
        sandbox_note = f"沙箱 `{sb}`（未触碰生产环境）"
    elif "local_mock" in kinds:
        sandbox_note = "沙箱 `local_mock` 进程内模拟（未触碰生产环境）"

    lines = [
        "## 接口文档测试结论",
        "",
        f"**文档来源**：`{docs_display}`，共 **{total} 个接口**",
        "",
        f"**探活环境**：{sandbox_note}",
        "",
        "### 结果总览",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 接口总数 | {total} |",
        f"| ✅ 探活通过 / 健康 | **{pass_n}** |",
        f"| ❌ 失败 / 问题接口 | **{fail_show}** |",
        f"| 未见调用 | {unseen} |",
    ]
    if probe_metrics.get("p95_ms") is not None:
        lines.append(
            f"| 延迟 P50 / P95 | {probe_metrics.get('p50_ms')}ms / **{probe_metrics.get('p95_ms')}ms** |"
        )
    if probe_metrics.get("methods"):
        method_s = "、".join(f"{k}×{v}" for k, v in sorted(probe_metrics["methods"].items()))
        lines.append(f"| 文档方法分布 | {method_s} |")

    lines.extend(["", "### 业务模块覆盖", ""])
    if modules:
        for m in modules:
            lines.append(
                f"- **{m['module']}**（{m['endpoint_count']} 个）— {m.get('capabilities') or '相关接口'}；"
                f"健康 {m.get('healthy', 0)} / 问题 {m.get('problematic', 0)} / 未见 {m.get('unseen', 0)}"
            )
    else:
        lines.append("- （无模块标签）")

    lines.extend(["", "### 结论", ""])
    if fail_show == 0 and unseen == 0 and total > 0:
        mod_names = "、".join(m["module"] for m in modules[:8]) or "文档所列模块"
        lines.append(
            f"全部 **{total} 个接口在沙箱环境均探活通过**，无失败、无超时、无异常。"
            f"覆盖业务模块包括：{mod_names}。"
        )
        lines.append("")
        lines.append(
            "所有接口响应正常，文档与沙箱实测一致，未发现不可用或异常接口。"
            "本结论基于沙箱探活证据，不代表生产网关全量流量健康。"
        )
    elif fail_show == 0 and unseen > 0:
        lines.append(
            f"目录共 {total} 个接口：健康 **{pass_n}**，未见调用 **{unseen}**，问题 **0**。"
            "未见调用表示时间窗内无出站/探活证据，不等于接口不可用；如需全覆盖请确认已全量探活。"
        )
    else:
        lines.append(
            f"目录共 {total} 个接口：健康 **{pass_n}**，问题 **{fail_show}**，未见 **{unseen}**。"
            "请优先排查下方问题接口（依据 status/error/延迟，勿用 path 参数名差异臆断）。"
        )
        if problematic:
            lines.extend(["", "#### 问题接口", ""])
            for p in problematic[:12]:
                lines.append(
                    f"- `{p.get('method')} {p.get('path') or p.get('path_key')}` — "
                    f"{p.get('reason') or ''}（调用 {p.get('calls')}，失败 {p.get('failures')}）"
                )

    lines.append("")
    return "\n".join(lines)


def _compact_probe_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """压缩探活返回，并附带按模块/方法的通过统计。"""
    if not isinstance(raw, dict):
        return {"error": "invalid probe result"}
    if raw.get("error"):
        return raw
    results = list(raw.get("results") or [])
    failed = [r for r in results if not r.get("ok")]
    ok_sample = [r for r in results if r.get("ok")][:5]
    lats: list[float] = []
    methods: dict[str, int] = defaultdict(int)
    for r in results:
        methods[str(r.get("method") or "?").upper()] += 1
        try:
            lats.append(float(r.get("latency_ms") or 0))
        except Exception:
            pass

    # 按目录 tag 归模块（用 catalog_path）
    index = load_index() or {}
    path_tag: dict[str, str] = {}
    for ep in index.get("endpoints") or []:
        path_tag[str(ep.get("path") or "")] = (
            str((ep.get("tags") or ["未分类"])[0]) if (ep.get("tags") or ["未分类"]) else "未分类"
        )
    by_mod: dict[str, dict[str, int]] = defaultdict(lambda: {"ok": 0, "failed": 0})
    for r in results:
        cp = str(r.get("catalog_path") or r.get("path") or "")
        mod = path_tag.get(cp) or "未分类"
        if r.get("ok"):
            by_mod[mod]["ok"] += 1
        else:
            by_mod[mod]["failed"] += 1

    def _slim(r: dict[str, Any]) -> dict[str, Any]:
        return {
            "method": r.get("method"),
            "path": r.get("catalog_path") or r.get("path"),
            "probe_path": r.get("path"),
            "status": r.get("status"),
            "ok": r.get("ok"),
            "error": r.get("error"),
            "latency_ms": r.get("latency_ms"),
        }

    out = {k: v for k, v in raw.items() if k != "results"}
    out["failed_sample"] = [_slim(r) for r in failed[:20]]
    out["ok_sample"] = [_slim(r) for r in ok_sample]
    out["failed_count"] = len(failed)
    out["by_module"] = [
        {"module": k, "ok": v["ok"], "failed": v["failed"], "total": v["ok"] + v["failed"]}
        for k, v in sorted(by_mod.items(), key=lambda x: -((x[1]["ok"] + x[1]["failed"])))
    ]
    out["latency"] = {
        "p50_ms": round(_percentile(lats, 50) or 0, 1) if lats else None,
        "p95_ms": round(_percentile(lats, 95) or 0, 1) if lats else None,
        "max_ms": round(max(lats), 1) if lats else None,
    }
    out["methods"] = dict(methods)
    out["results_omitted"] = True
    out["next"] = "summarize_api_doc_vs_logs → rank_problematic_apis → render_api_health_report"
    out["note"] = (
        str(raw.get("note") or "")
        + " 详细 results 已省略；请继续 summarize / rank / render_api_health_report。"
    ).strip()
    return out


def _parse_since(since: str | None, lookback_days: int) -> float:
    if since and str(since).strip():
        s = str(since).strip().replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).timestamp()
            except ValueError:
                continue
    return default_since_ts(lookback_days)


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    arr = sorted(values)
    if len(arr) == 1:
        return float(arr[0])
    k = (len(arr) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(arr) - 1)
    if f == c:
        return float(arr[f])
    return float(arr[f] + (arr[c] - arr[f]) * (k - f))
