"""当 Bridge 未带回 file_contents，但 workspace 与 API 同机可读时补齐源码。

适用于本机开发演示（WorkBuddy 与 VS Code 在同一台电脑）。
远程多租户部署时路径通常不存在，本函数会静默跳过。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.ide_review.local_files import read_workspace_files

# 轻量安全/质量规则（与扩展兜底对齐），用于补齐旧扩展空 findings 的情况
_CONTENT_RULES: list[tuple[str, str, re.Pattern[str], str, str]] = [
    (
        "P0",
        "java-sql-string-concat",
        re.compile(
            r"(createStatement\s*\(|\.execute(Query|Update)?\s*\(\s*[\"'][^\"']*[\"']\s*\+|"
            r"Statement\.execute|[\"']\s*SELECT\b[^\"']*[\"']\s*\+)",
            re.I,
        ),
        "疑似 SQL 字符串拼接，存在注入风险",
        "改用 PreparedStatement 参数绑定，禁止拼接用户输入",
    ),
    (
        "P0",
        "java-runtime-exec",
        re.compile(r"Runtime\.getRuntime\s*\(\s*\)\s*\.exec\s*\(|ProcessBuilder\s*\("),
        "出现 Runtime.exec / ProcessBuilder，存在命令注入风险",
        "避免拼接外部输入；使用白名单参数或安全 API",
    ),
    (
        "P1",
        "java-print-stack-trace",
        re.compile(r"\.printStackTrace\s*\("),
        "printStackTrace 可能泄露内部信息到日志/控制台",
        "使用统一日志框架记录异常",
    ),
    (
        "P1",
        "java-object-input-stream",
        re.compile(r"new\s+ObjectInputStream\s*\("),
        "反序列化 ObjectInputStream 存在远程代码执行历史风险",
        "避免反序列化不可信数据；改用安全格式（JSON 等）",
    ),
    (
        "P1",
        "hardcoded-secret",
        re.compile(
            r"(password|passwd|secret|api[_-]?key)\s*=\s*[\"'][^\"']{4,}[\"']",
            re.I,
        ),
        "疑似硬编码口令/密钥",
        "改为环境变量或密钥管理",
    ),
    (
        "P0",
        "dangerous-eval",
        re.compile(r"\beval\s*\("),
        "出现 eval()，存在任意代码执行风险",
        "改为安全解析，避免 eval",
    ),
    (
        "P2",
        "todo-fixme",
        re.compile(r"\b(TODO|FIXME|XXX)\b"),
        "存在 TODO/FIXME 标记，需确认是否遗留风险",
        "关闭前确认并清理或登记跟踪",
    ),
]


def fill_local_file_contents(result: dict[str, Any]) -> dict[str, Any]:
    """若 file_contents 为空且 workspace_root 在本机可读，则补读 files 列表。"""
    contents = result.get("file_contents")
    if isinstance(contents, list) and contents:
        return result

    root_raw = str(result.get("workspace_root") or "").strip()
    if not root_raw:
        return result
    root = Path(root_raw).expanduser()
    try:
        if not root.is_dir():
            return result
    except OSError:
        return result

    paths = result.get("files") if isinstance(result.get("files"), list) else []
    paths = [str(p) for p in paths if p]
    if not paths:
        return result

    packed = read_workspace_files(root, paths)
    items = packed.get("file_contents") or []
    if not items:
        out = dict(result)
        errs = list(result.get("errors") or [])
        errs.extend(packed.get("errors") or [])
        if errs:
            out["errors"] = errs
        out["local_fill"] = "failed"
        return out

    out = dict(result)
    out["file_contents"] = items
    out["local_fill"] = "ok"
    out["local_fill_note"] = (
        "file_contents 由 API 同机补读（Bridge 未带回源码时的兜底）。"
        "正式多机部署仍应依赖扩展 ≥0.3.2 回传。"
    )
    raw = str(out.get("raw_summary") or "")
    out["raw_summary"] = (
        raw + f"；同机补读 {len(items)} 个文件内容"
        if raw
        else f"同机补读 {len(items)} 个文件内容"
    )
    # 清掉「必须升级才能审」的误导；已有正文可审
    out.pop("upgrade_hint", None)
    return out


def augment_findings_from_contents(result: dict[str, Any]) -> dict[str, Any]:
    """对 file_contents 跑轻量规则，合并进 findings（不覆盖已有）。"""
    contents = result.get("file_contents")
    if not isinstance(contents, list) or not contents:
        return result

    existing = result.get("findings") if isinstance(result.get("findings"), list) else []
    seen = {
        f"{f.get('severity')}|{f.get('path')}|{f.get('line')}|{f.get('rule')}"
        for f in existing
        if isinstance(f, dict)
    }
    extra: list[dict[str, Any]] = []
    for item in contents:
        if not isinstance(item, dict):
            continue
        rel = str(item.get("path") or "")
        text = str(item.get("content") or "")
        if not rel or not text:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            for severity, rule, pattern, message, suggestion in _CONTENT_RULES:
                if not pattern.search(line):
                    continue
                key = f"{severity}|{rel}|{i}|{rule}"
                if key in seen:
                    continue
                seen.add(key)
                extra.append(
                    {
                        "severity": severity,
                        "path": rel,
                        "line": i,
                        "rule": rule,
                        "message": message,
                        "suggestion": suggestion,
                    }
                )

    if not extra:
        return result

    out = dict(result)
    merged = list(existing) + extra
    out["findings"] = merged
    counts = {"P0": 0, "P1": 0, "P2": 0}
    for f in merged:
        sev = str(f.get("severity") or "")
        if sev in counts:
            counts[sev] += 1
    out["diagnostics_count"] = counts
    out["review_empty"] = False
    sources = list(out.get("sources") or [])
    if "server-content-rules" not in sources:
        sources.append("server-content-rules")
    out["sources"] = sources
    out["hint"] = (
        "请基于 findings 与 file_contents 撰写专业报告；勿再调用服务端 read_file，勿让用户贴代码。"
    )
    return out


def enrich_bridge_result(result: dict[str, Any]) -> dict[str, Any]:
    """补源码 + 规则 findings，供 Agent 工具出口统一调用。"""
    out = fill_local_file_contents(dict(result))
    out = augment_findings_from_contents(out)
    return out
