"""确定性 mock 审核：无 LLM、无 MCP，供 M0 冒烟与开关关闭时的开发联调。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.ide_review.paths import rel_posix

# (severity, rule, pattern, message, suggestion)
_RULES: list[tuple[str, str, re.Pattern[str], str, str]] = [
    (
        "P0",
        "dangerous-eval",
        re.compile(r"\beval\s*\("),
        "出现 eval()，存在任意代码执行风险",
        "改为安全解析或明确白名单逻辑，避免 eval",
    ),
    (
        "P1",
        "bare-except",
        re.compile(r"except\s*:"),
        "裸 except 会吞掉所有异常，排障困难",
        "改为 except Exception 或更具体的异常类型",
    ),
    (
        "P1",
        "token-in-url-query",
        re.compile(
            r"(params\.get\(\s*['\"]access_token['\"]|params\.get\(\s*['\"]token['\"]|"
            r"searchParams\.get\(\s*['\"]access_token['\"]|"
            r"URLSearchParams|[?&]access_token=)"
        ),
        "疑似从 URL query 读取 token，存在泄露面（日志/referrer）",
        "尽快写入会话存储并 replaceState 去掉 query；勿把完整 URL 外传",
    ),
    (
        "P2",
        "todo-fixme",
        re.compile(r"\b(TODO|FIXME)\b"),
        "存在 TODO/FIXME 标记，需确认是否遗留风险",
        "关闭前确认并清理或登记跟踪",
    ),
]


def mock_review_files(
    repo_root: Path,
    files: list[Path],
    prompt: str = "",
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            findings.append(
                {
                    "severity": "P1",
                    "path": rel_posix(repo_root, path),
                    "line": 0,
                    "rule": "read-error",
                    "message": f"无法读取文件: {e}",
                    "suggestion": "确认路径与权限",
                }
            )
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines, start=1):
            for severity, rule, pattern, message, suggestion in _RULES:
                if pattern.search(line):
                    findings.append(
                        {
                            "severity": severity,
                            "path": rel_posix(repo_root, path),
                            "line": i,
                            "rule": rule,
                            "message": message,
                            "suggestion": suggestion,
                        }
                    )

    prompt_note = (prompt or "").strip()
    summary = (
        f"mock 审核完成：{len(files)} 个文件，{len(findings)} 条 finding"
        + (f"；提示词已记录（{len(prompt_note)} 字）" if prompt_note else "")
    )
    return {
        "status": "ok",
        "provider": "mock",
        "workspace_root": str(repo_root.resolve()),
        "files": [rel_posix(repo_root, p) for p in files],
        "findings": findings,
        "diagnostics_count": _count_by_severity(findings),
        "raw_summary": summary,
    }


def _count_by_severity(findings: list[dict[str, Any]]) -> dict[str, int]:
    out = {"P0": 0, "P1": 0, "P2": 0}
    for f in findings:
        sev = str(f.get("severity") or "")
        if sev in out:
            out[sev] += 1
    return out
