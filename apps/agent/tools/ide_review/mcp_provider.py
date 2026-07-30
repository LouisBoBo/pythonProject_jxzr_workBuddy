"""可选 live：通过本机 MCP stdio 拉取工具结果并规范为 findings。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from tools.ide_review.mcp_client import (
    McpStdioClient,
    McpStdioError,
    default_mcp_command_args,
)
from tools.ide_review.paths import rel_posix


def mcp_review_files(
    repo_root: Path,
    files: list[Path],
    prompt: str = "",
) -> dict[str, Any]:
    cmd, args = default_mcp_command_args()
    timeout = float(os.getenv("IDE_REVIEW_MCP_TIMEOUT_SEC", "45") or "45")
    preferred = (
        os.getenv("IDE_REVIEW_MCP_TOOL") or "code_checker"
    ).strip() or "code_checker"

    try:
        with McpStdioClient(cmd, args, cwd=str(repo_root), timeout_sec=timeout) as client:
            tools = client.list_tools()
            names = [
                str(t.get("name") or "")
                for t in tools
                if isinstance(t, dict) and t.get("name")
            ]
            tool_name = preferred if preferred in names else (names[0] if names else "")
            if not tool_name:
                return _skip(
                    repo_root,
                    files,
                    reason=f"MCP 未暴露任何 tool（command={cmd} {' '.join(args)}）",
                    stderr=client.stderr_tail(),
                )

            # 不同 MCP 参数不一；尽量传常见字段，失败则空参重试
            rels = [rel_posix(repo_root, p) for p in files]
            call_args_candidates: list[dict[str, Any]] = [
                {"paths": rels, "prompt": prompt},
                {"path": rels[0] if rels else "", "prompt": prompt},
                {},
            ]
            last_err: str | None = None
            result: Any = None
            for call_args in call_args_candidates:
                try:
                    result = client.call_tool(tool_name, call_args)
                    last_err = None
                    break
                except McpStdioError as e:
                    last_err = str(e)
            if last_err and result is None:
                return _skip(
                    repo_root,
                    files,
                    reason=f"tools/call {tool_name} 失败: {last_err}",
                    stderr=client.stderr_tail(),
                    tools=names,
                )

            findings = _normalize_findings(repo_root, result)
            text = _content_text(result)
            return {
                "status": "ok",
                "provider": "mcp",
                "mcp_tool": tool_name,
                "mcp_tools_available": names,
                "workspace_root": str(repo_root.resolve()),
                "files": rels,
                "findings": findings,
                "diagnostics_count": _count_by_severity(findings),
                "raw_summary": text[:4000] if text else f"MCP tool={tool_name} 已调用",
            }
    except McpStdioError as e:
        return _skip(repo_root, files, reason=str(e))
    except Exception as e:
        return _skip(repo_root, files, reason=f"未预期错误: {e}")


def _skip(
    repo_root: Path,
    files: list[Path],
    *,
    reason: str,
    stderr: str = "",
    tools: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": "skip",
        "provider": "mcp",
        "workspace_root": str(repo_root.resolve()),
        "files": [rel_posix(repo_root, p) for p in files],
        "findings": [],
        "diagnostics_count": {"P0": 0, "P1": 0, "P2": 0},
        "raw_summary": reason,
        "skip_reason": reason,
        "stderr_tail": stderr,
        "mcp_tools_available": tools or [],
    }


def _content_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            return "\n".join(parts)
        return json.dumps(result, ensure_ascii=False)
    return str(result)


def _normalize_findings(repo_root: Path, result: Any) -> list[dict[str, Any]]:
    """尽量从 MCP 返回值抽出结构化 finding；否则落一条 P2 摘要。"""
    text = _content_text(result)
    findings: list[dict[str, Any]] = []

    # 若返回本身是 list[dict]
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and (
                "message" in item or "path" in item or "file" in item
            ):
                findings.append(_coerce_finding(item))
        if findings:
            return findings

    if isinstance(result, dict):
        for key in ("findings", "diagnostics", "issues"):
            blob = result.get(key)
            if isinstance(blob, list):
                for item in blob:
                    if isinstance(item, dict):
                        findings.append(_coerce_finding(item))
                if findings:
                    return findings

    # 尝试 JSON 文本
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            return _normalize_findings(repo_root, parsed)
        except json.JSONDecodeError:
            pass

    if stripped:
        findings.append(
            {
                "severity": "P2",
                "path": "",
                "line": 0,
                "rule": "mcp-raw",
                "message": stripped[:800],
                "suggestion": "对照 MCP 原始输出人工确认；后续可增强结构化解析",
            }
        )
    return findings


def _coerce_finding(item: dict[str, Any]) -> dict[str, Any]:
    sev = str(item.get("severity") or item.get("level") or item.get("severityCode") or "P2")
    if sev.lower() in ("error", "critical", "high"):
        sev = "P0"
    elif sev.lower() in ("warning", "warn", "medium"):
        sev = "P1"
    elif sev.lower() in ("info", "hint", "low"):
        sev = "P2"
    if sev not in ("P0", "P1", "P2"):
        sev = "P2"
    line = item.get("line") or item.get("lineno") or item.get("startLine") or 0
    try:
        line_i = int(line)
    except Exception:
        line_i = 0
    return {
        "severity": sev,
        "path": str(item.get("path") or item.get("file") or item.get("uri") or ""),
        "line": line_i,
        "rule": str(item.get("rule") or item.get("code") or item.get("source") or "mcp"),
        "message": str(item.get("message") or item.get("msg") or item.get("text") or item),
        "suggestion": str(item.get("suggestion") or item.get("fix") or ""),
    }


def _count_by_severity(findings: list[dict[str, Any]]) -> dict[str, int]:
    out = {"P0": 0, "P1": 0, "P2": 0}
    for f in findings:
        sev = str(f.get("severity") or "")
        if sev in out:
            out[sev] += 1
    return out
