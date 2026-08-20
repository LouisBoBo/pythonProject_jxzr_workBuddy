"""可选：调用 workbuddy-analysis-chart MCP（stdio）做图表渲染。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from tools.ide_review.mcp_client import McpStdioClient, McpStdioError


def default_chart_mcp_command_args() -> tuple[str, list[str]]:
    """默认：同解释器 -m tools.query_tool.chart_mcp_server。"""
    override = (os.getenv("ANALYSIS_CHART_MCP_COMMAND") or "").strip()
    if override:
        parts = override.split()
        return parts[0], parts[1:]
    agent_root = Path(__file__).resolve().parents[2]
    return sys.executable, ["-m", "tools.query_tool.chart_mcp_server"]


def call_chart_mcp(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    cmd, args = default_chart_mcp_command_args()
    timeout = float(os.getenv("ANALYSIS_CHART_MCP_TIMEOUT_SEC", "20") or "20")
    agent_root = Path(__file__).resolve().parents[2]
    env_pythonpath = os.environ.get("PYTHONPATH", "")
    # 保证子进程能 import tools.*
    merged_pp = os.pathsep.join(
        p for p in [str(agent_root), env_pythonpath] if p
    )
    old = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = merged_pp
    try:
        with McpStdioClient(cmd, args, cwd=str(agent_root), timeout_sec=timeout) as client:
            result = client.call_tool(tool_name, arguments)
    except McpStdioError as e:
        return {"_mcp_error": str(e)}
    finally:
        if old is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = old

    # 解析 MCP content text / structuredContent
    if isinstance(result, dict):
        sc = result.get("structuredContent")
        if isinstance(sc, dict):
            return sc
        content = result.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = str(block.get("text") or "")
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        pass
        return result if "option" in result else {"_mcp_error": "MCP 返回无法解析", "raw": str(result)[:200]}
    return {"_mcp_error": f"意外返回类型: {type(result).__name__}"}
